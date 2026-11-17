'use strict';
/*
 * FlowSight – mapa Pezinka (DEV12, napojené na vyhľadávanie DEV13).
 * Vrstvy mesta sú skutočné (gis.pezinok.sk), polohy kamier sú ukážkové (data/cameras.js).
 */
(function () {
  const $ = (id) => document.getElementById(id);
  const cameras = window.FLOWSIGHT_CAMERAS ?? [];
  const layersData = window.PEZINOK_LAYERS ?? {};

  if (!window.L) {
    $('map-error').textContent = 'Knižnica mapy (Leaflet) sa nenačítala. Skontrolujte pripojenie na internet.';
    $('map-error').hidden = false;
    return;
  }

  const map = L.map('map', { zoomControl: true, attributionControl: true });
  // Štandardné dlaždice OpenStreetMap – na vývoj OK, pre ostrú prevádzku treba vlastný tile server
  // alebo platenú službu (pravidlá: https://operations.osmfoundation.org/policies/tiles/).
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · kamery: <a href="https://www.pezinok.sk/stranka/kamerovy-system">MsP Pezinok</a> · vrstvy: <a href="https://gis.pezinok.sk">Mesto Pezinok</a>',
  }).addTo(map);
  let tileErrors = 0;
  tiles.on('tileerror', () => { if (++tileErrors === 6) $('map-error').hidden = false; });
  tiles.on('tileload', () => { tileErrors = 0; $('map-error').hidden = true; });

  /* ---------- Pomocné ---------- */
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const svgIcon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  // Približná plocha polygónu v m² (stačí na popis, nie na meranie).
  function areaM2(feature) {
    const g = feature.geometry;
    const ring = g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0];
    const lat0 = ring[0][1] * Math.PI / 180;
    const kx = 111320 * Math.cos(lat0), ky = 110540;
    let a = 0;
    for (let i = 0; i < ring.length - 1; i++) {
      a += ring[i][0] * kx * ring[i + 1][1] * ky - ring[i + 1][0] * kx * ring[i][1] * ky;
    }
    return Math.abs(a / 2);
  }
  function cone(heading, spread = 70, r = 56) {
    const pt = (deg) => {
      const rad = deg * Math.PI / 180;
      return `${(60 + r * Math.sin(rad)).toFixed(1)},${(60 - r * Math.cos(rad)).toFixed(1)}`;
    };
    return `<svg class="cam-cone" viewBox="0 0 120 120"><path d="M60,60 L${pt(heading - spread / 2)} A${r},${r} 0 0 1 ${pt(heading + spread / 2)} Z"/></svg>`;
  }

  /* ---------- Vrstvy mesta ---------- */
  const boundary = L.geoJSON(layersData.hranica, {
    style: { color: '#13233a', weight: 2, dashArray: '6 6', fill: false },
    interactive: false,
  });

  const zones = L.geoJSON(layersData.parkovacieZony, {
    style: { color: '#c58a06', weight: 1.5, dashArray: '5 4', fillColor: '#f0b429', fillOpacity: 0.12 },
    onEachFeature: (f, layer) => {
      const p = f.properties ?? {};
      layer.bindPopup(`<p class="popup-title">Parkovacia zóna</p>
        <p class="popup-sub">${esc(p.etapa ?? '—')}</p>
        <p class="popup-sub">Spustenie: ${esc(p.spustenie_od ?? 'neuvedené')}</p>`);
    },
  });

  const lots = L.geoJSON(layersData.odstavnePlochy, {
    style: { color: '#1e8a5f', weight: 1.5, fillColor: '#1e8a5f', fillOpacity: 0.28 },
    onEachFeature: (f, layer) => {
      const m2 = Math.round(areaM2(f) / 10) * 10;
      layer.bindPopup(`<p class="popup-title">Odstavná plocha</p>
        <p class="popup-sub">Približne ${m2.toLocaleString('sk-SK')} m²</p>
        <p class="popup-sub">Obsadenosť doplní API, keď budú kamery nad parkoviskami.</p>`);
    },
  });

  /* ---------- Kamery ---------- */
  const PRECISION = {
    'križovatka': 'Odhadovaná poloha podľa križovatky',
    adresa: 'Odhadovaná poloha podľa adresy',
    budova: 'Odhadovaná poloha podľa budovy',
    'približne': 'Približná poloha, len oblasť',
  };
  const markers = new Map();
  const cameraLayer = L.layerGroup();
  for (const cam of cameras) {
    const icon = L.divIcon({
      className: `cam-marker${cam.type === 'statická' ? ' is-static' : ''}`,
      html: `${typeof cam.heading === 'number' ? cone(cam.heading) : ''}<span class="cam-dot">${esc(cam.no ?? '')}</span>`,
      iconSize: [0, 0],
    });
    const marker = L.marker([cam.lat, cam.lng], { icon, title: cam.name, keyboard: true, riseOnHover: true });
    // Žiadna poloha nie je potvrdená od MsP – všetky sú dopočítané z popisu v PDF a OpenStreetMap.
    const precision = PRECISION[cam.precision] ?? PRECISION['približne'];
    marker.bindPopup(`<p class="popup-title">${esc(cam.name)}</p>
      <p class="popup-sub">${esc(cam.street ?? '')}</p>
      <p class="popup-meta">${esc(cam.area ?? '')} · ${cam.type === 'statická' ? 'statická kamera' : 'otočná kamera'}</p>
      ${cam.demo ? '<span class="popup-tag">Ukážková poloha</span>' : `<span class="popup-tag${cam.precision === 'približne' ? ' is-rough' : ''}" title="Súradnice sú odhadnuté z opisu Mestskej polície a OpenStreetMap, nie sú overené na mieste.">${precision}</span>`}
      <div class="popup-actions">
        <a href="../DEV13-db-search-frontend/index.html?camera=${encodeURIComponent(cam.id)}">${svgIcon('search')}Hľadať vozidlo</a>
        <span title="Živý obraz z Milestone doplníme neskôr">Živý obraz</span>
      </div>`, { minWidth: 240 });
    marker.on('popupopen', () => setActive(cam.id));
    marker.on('popupclose', () => setActive(null));
    marker.addTo(cameraLayer);
    markers.set(cam.id, marker);
  }

  function setActive(id) {
    for (const [camId, marker] of markers) marker.getElement()?.classList.toggle('is-active', camId === id);
    for (const btn of document.querySelectorAll('.camera-focus')) btn.classList.toggle('is-active', btn.dataset.id === id);
  }

  // Zoznam kamier zoskupený podľa častí mesta (ako v dokumente MsP).
  $('cam-count').textContent = `${cameras.length}`;
  const areas = [...new Set(cameras.map((c) => c.area ?? 'Ostatné'))];
  $('camera-list').replaceChildren(...areas.map((area, index) => {
    const inArea = cameras.filter((c) => (c.area ?? 'Ostatné') === area);
    const group = document.createElement('li');
    group.className = 'camera-group';
    const details = document.createElement('details');
    if (index === 0) details.open = true;
    details.innerHTML = `<summary><span>${esc(area)}</span><span class="count">${inArea.length}</span></summary>`;
    const list = document.createElement('ul');
    list.className = 'camera-sublist';
    for (const cam of inArea) {
      const li = document.createElement('li');
      li.className = 'camera-row';
      li.innerHTML = `<button type="button" class="camera-focus" data-id="${esc(cam.id)}"><span class="cam-no">${esc(cam.no ?? '')}</span><span><strong>${esc(cam.name.replace(/^Kamera \S+ – /, ''))}</strong><small>${esc(cam.street ?? '')}</small></span></button>
        <a class="camera-search" href="../DEV13-db-search-frontend/index.html?camera=${encodeURIComponent(cam.id)}" aria-label="Hľadať vozidlo na kamere ${esc(cam.name)}" title="Hľadať vozidlo na tejto kamere">${svgIcon('search')}</a>`;
      li.querySelector('button').addEventListener('click', () => {
        const marker = markers.get(cam.id);
        if (!map.hasLayer(cameraLayer)) { cameraLayer.addTo(map); syncCheckbox('cameras', true); }
        map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 17), { duration: 0.6 });
        marker.openPopup();
      });
      list.append(li);
    }
    details.append(list);
    group.append(details);
    return group;
  }));

  /* ---------- Filtre kamier ---------- */
  // Fasetové filtre: nič nezaškrtnuté = všetky. V rámci jednej fazety platí ALEBO, medzi fazetami A ZÁROVEŇ.
  // Počty pri voľbách sa prepočítavajú podľa ostatných filtrov, voľby s nulou sa vypnú.
  const fold = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const placeOf = (cam) => (cam.site === 'areál' ? 'areal' : cam.mount === 'budova' ? 'budova' : 'stlp');
  const PLACES = [
    ['stlp', 'Na stĺpe pri ceste'],
    ['budova', 'Na budove pri ceste'],
    ['areal', 'V areáli (škola, ihrisko, dvor)'],
  ];
  const TYPES = [['all', 'Všetky'], ['otočná', 'Otočné'], ['statická', 'Statické']];
  const areaOf = (cam) => cam.area ?? 'Ostatné';
  const haystack = new Map(cameras.map((c) => [c.id, fold(`${c.no} ${c.name} ${c.street} ${areaOf(c)}`)]));

  const state = { q: '', type: 'all', place: new Set(), area: new Set() };
  const tests = {
    q: (c) => !state.q || state.q.split(/\s+/).every((w) => haystack.get(c.id).includes(w)),
    type: (c) => state.type === 'all' || c.type === state.type,
    place: (c) => !state.place.size || state.place.has(placeOf(c)),
    area: (c) => !state.area.size || state.area.has(areaOf(c)),
  };
  // Kamery vyhovujúce všetkým filtrom okrem `skip` – z toho sa počítajú čísla pri voľbách danej fazety.
  const matching = (skip) => cameras.filter((c) => Object.entries(tests).every(([k, t]) => k === skip || t(c)));

  function option(name, value, label) {
    const el = document.createElement('label');
    el.className = 'facet-option';
    el.innerHTML = `<input type="checkbox" name="${name}" value="${esc(value)}"><span class="facet-label">${esc(label)}</span><span class="facet-count"></span>`;
    el.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? state[name].add(value) : state[name].delete(value);
      applyCameraFilters();
    });
    return el;
  }
  $('facet-place').replaceChildren(...PLACES.map(([v, l]) => option('place', v, l)));
  $('facet-area').replaceChildren(...areas.map((a) => option('area', a, a)));
  $('facet-type').replaceChildren(...TYPES.map(([v, l]) => {
    const el = document.createElement('label');
    el.innerHTML = `<input type="radio" name="cam-type" value="${esc(v)}"${v === 'all' ? ' checked' : ''}><span>${esc(l)} <b class="facet-count"></b></span>`;
    el.querySelector('input').addEventListener('change', () => { state.type = v; applyCameraFilters(); });
    return el;
  }));

  let typing;
  $('cam-query').addEventListener('input', (e) => {
    clearTimeout(typing);
    typing = setTimeout(() => { state.q = fold(e.target.value.trim()); applyCameraFilters(); }, 120);
  });

  function clearFilter(key, value) {
    if (key === 'q') { state.q = ''; $('cam-query').value = ''; }
    else if (key === 'type') state.type = 'all';
    else if (value === undefined) state[key].clear();
    else state[key].delete(value);
  }
  function clearAll() { for (const key of Object.keys(state)) clearFilter(key); applyCameraFilters(); }
  for (const btn of document.querySelectorAll('[data-clear]')) btn.addEventListener('click', clearAll);

  function syncControls() {
    for (const input of document.querySelectorAll('#facet-type input')) input.checked = input.value === state.type;
    for (const key of ['place', 'area']) {
      const counts = new Map();
      for (const c of matching(key)) {
        const v = key === 'place' ? placeOf(c) : areaOf(c);
        counts.set(v, (counts.get(v) ?? 0) + 1);
      }
      for (const input of document.querySelectorAll(`#facet-${key} input`)) {
        const n = counts.get(input.value) ?? 0;
        input.checked = state[key].has(input.value);
        input.disabled = n === 0 && !input.checked;
        input.closest('.facet-option').querySelector('.facet-count').textContent = String(n);
      }
    }
    const typeBase = matching('type');
    for (const input of document.querySelectorAll('#facet-type input')) {
      const n = input.value === 'all' ? typeBase.length : typeBase.filter((c) => c.type === input.value).length;
      input.closest('label').querySelector('.facet-count').textContent = String(n);
      input.disabled = n === 0 && !input.checked;
    }
    $('facet-area-summary').textContent = state.area.size === 0 ? 'všetky'
      : state.area.size === 1 ? [...state.area][0] : `${state.area.size} vybrané`;
  }

  function renderActive() {
    const chips = [];
    const add = (text, key, value) => chips.push({ text, key, value });
    if (state.q) add(`„${$('cam-query').value.trim()}“`, 'q');
    if (state.type !== 'all') add(TYPES.find(([v]) => v === state.type)[1], 'type');
    for (const v of state.place) add(PLACES.find(([p]) => p === v)[1], 'place', v);
    for (const v of state.area) add(v, 'area', v);
    const box = $('active-filters');
    box.hidden = chips.length === 0;
    box.replaceChildren(...chips.map(({ text, key, value }) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'active-chip';
      b.setAttribute('aria-label', `Zrušiť filter ${text}`);
      b.innerHTML = `<span>${esc(text)}</span><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m7 7 10 10M7 17 17 7"/></svg>`;
      b.addEventListener('click', () => { clearFilter(key, value); applyCameraFilters(); });
      return b;
    }));
    if (chips.length > 1) {
      const all = document.createElement('button');
      all.type = 'button';
      all.className = 'link-button';
      all.textContent = 'Vymazať všetko';
      all.addEventListener('click', clearAll);
      box.append(all);
    }
    return chips.length;
  }

  function applyCameraFilters() {
    const visible = new Set(matching(null).map((c) => c.id));
    for (const cam of cameras) {
      const marker = markers.get(cam.id);
      const show = visible.has(cam.id);
      if (show) { if (!cameraLayer.hasLayer(marker)) marker.addTo(cameraLayer); }
      else { if (marker.isPopupOpen()) marker.closePopup(); cameraLayer.removeLayer(marker); }
      const row = document.querySelector(`.camera-focus[data-id="${CSS.escape(cam.id)}"]`)?.closest('.camera-row');
      if (row) row.hidden = !show;
    }
    const filtered = renderActive() > 0;
    for (const group of document.querySelectorAll('.camera-group')) {
      const n = group.querySelectorAll('.camera-row:not([hidden])').length;
      group.hidden = n === 0;
      group.querySelector('summary .count').textContent = String(n);
      // Pri filtrovaní ukáž výsledky rovno, bez ďalšieho klikania na skupiny.
      if (filtered && n > 0 && visible.size <= 15) group.querySelector('details').open = true;
    }
    syncControls();
    $('cam-count').textContent = filtered ? `${visible.size} z ${cameras.length}` : `${cameras.length}`;
    $('cam-empty').hidden = visible.size > 0;
    $('camera-list').hidden = visible.size === 0;
  }
  applyCameraFilters();

  /* ---------- Prepínanie vrstiev ---------- */
  const registry = { boundary, zones, lots, cameras: cameraLayer };
  function syncCheckbox(name, value) {
    const box = document.querySelector(`input[data-layer="${name}"]`);
    if (box) box.checked = value;
  }
  for (const box of document.querySelectorAll('input[data-layer]')) {
    const layer = registry[box.dataset.layer];
    if (box.checked) layer.addTo(map);
    box.addEventListener('change', () => (box.checked ? layer.addTo(map) : map.removeLayer(layer)));
  }

  /* ---------- Výrez ---------- */
  // Hranica obce zahŕňa aj vinohrady a les, preto začíname na meste (zóny + kamery).
  // Odľahlé kamery (Zumberská, Grinava) do úvodného výrezu nezahŕňame, aby mapa nebola príliš oddialená.
  const OUTLYING = new Set(['Nájomné byty Zumberská', 'Grinava']);
  const town = L.latLngBounds([]);
  if (layersData.parkovacieZony) town.extend(L.geoJSON(layersData.parkovacieZony).getBounds());
  for (const cam of cameras) if (!OUTLYING.has(cam.area)) town.extend([cam.lat, cam.lng]);
  const fitTown = () => {
    map.invalidateSize();
    if (town.isValid()) map.fitBounds(town, { padding: [16, 16] });
    else map.setView([48.2876, 17.2668], 14);
  };
  fitTown();
  // Kontajner mapy dostane konečnú veľkosť až po rozložení stránky.
  requestAnimationFrame(fitTown);
  if (layersData.hranica) map.setMaxBounds(L.geoJSON(layersData.hranica).getBounds().pad(0.3));
  map.setMinZoom(12);

  const focus = new URLSearchParams(location.search).get('camera');
  if (focus && markers.has(focus)) {
    const btn = document.querySelector(`.camera-focus[data-id="${CSS.escape(focus)}"]`);
    if (btn) { btn.closest('details').open = true; setTimeout(() => btn.click(), 300); }
  }
})();
