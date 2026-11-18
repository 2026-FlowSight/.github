'use strict';
/*
 * FlowSight – mapa mesta Pezinok (DEV12).
 * Vrstvy: kamery (klikateľné), parkoviská s obsadenosťou, hranica mesta.
 * Polohy kamier a parkovísk sú z konfiguračných súborov DEV11 (config/cameras.yaml, config/parking.yaml),
 * ktoré posiela API (/api/cameras, /api/parking). Hranica mesta je z gis.pezinok.sk (data/pezinok-layers.js).
 */
(function () {
  const $ = (id) => document.getElementById(id);
  const API = window.FlowSightAPI;
  const GIS = window.PEZINOK_LAYERS ?? {};
  const PARKING_REFRESH_MS = 30_000;
  const CAMERA_REFRESH_MS = 60_000;
  const STALE_MS = 10 * 60_000;
  const MOBILE = matchMedia('(max-width: 820px)');
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const fold = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const fmtTime = (d) => d.toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' });
  const STATUS_LABEL = { online: 'Online', warning: 'Podozrivé', offline: 'Offline', unknown: 'Stav neznámy' };
  const LEVEL_LABEL = { free: 'Voľné', busy: 'Takmer plné', full: 'Plné', none: 'Bez údajov' };
  const LEVEL_COLOR = { free: '#16a34a', busy: '#f59e0b', full: '#dc2626', none: '#1d6fe5' };
  const OUTLYING = new Set(['Nájomné byty Zumberská']); // ďaleko na severe – nezahŕňame do úvodného výrezu

  if (!window.L) {
    showBanner('Knižnica mapy sa nenačítala. Skontrolujte pripojenie na internet.', true);
    return;
  }

  /* ================= Mapa a podklad ================= */
  // Celé úrovne priblíženia – pri zlomkových sú medzi dlaždicami viditeľné švy.
  const map = L.map('map', { zoomControl: false, zoomSnap: 1, minZoom: 12, maxZoom: 19 });
  L.control.scale({ position: 'bottomleft', imperial: false, maxWidth: 120 }).addTo(map);
  map.attributionControl.setPrefix(false);

  const ATTR_DATA = 'Dáta: MsP a Mesto Pezinok';
  const OSM = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  // Stadia „Alidade Smooth“ – svetlý, pokojný podklad ako vo vizualizácii. Na localhoste ide bez kľúča,
  // na verejnej doméne treba bezplatný účet Stadia Maps (doména sa pridá v ich konzole).
  const BASEMAPS = [
    { url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', opts: { maxZoom: 20,
      attribution: `© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> ${OSM} · ${ATTR_DATA}` } },
    // Záloha: OSM Humanitarian (openstreetmap.fr)
    { url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', opts: { maxZoom: 19, subdomains: 'abc',
      attribution: `${OSM}, štýl HOT (openstreetmap.fr) · ${ATTR_DATA}` } },
  ];
  let tiles;
  function useBasemap(i) {
    if (tiles) map.removeLayer(tiles);
    let errors = 0;
    tiles = L.tileLayer(BASEMAPS[i].url, BASEMAPS[i].opts).addTo(map);
    tiles.on('tileload', () => { errors = 0; });
    tiles.on('tileerror', () => {
      if (++errors === 3 && i + 1 < BASEMAPS.length) {
        useBasemap(i + 1);
        showBanner('Podklad mapy je nedostupný, použitý záložný.');
      }
    });
  }
  useBasemap(0);

  map.createPane('mask').style.zIndex = 350;
  map.createPane('lots').style.zIndex = 410;
  map.createPane('badges').style.zIndex = 590; // pod kamerami (600), aby kamery vždy bolo vidieť

  /* ---------- Hranica mesta + stlmenie okolia ---------- */
  const boundaryRings = (GIS.hranica?.features ?? []).flatMap((f) =>
    f.geometry.type === 'Polygon' ? [f.geometry.coordinates[0]] : f.geometry.coordinates.map((p) => p[0]));
  const toLatLngs = (ring) => ring.map(([lng, lat]) => [lat, lng]);
  const boundaryLayer = L.layerGroup();
  if (boundaryRings.length) {
    const world = [[85, -180], [85, 180], [-85, 180], [-85, -180]];
    L.polygon([world, ...boundaryRings.map(toLatLngs)], {
      pane: 'mask', stroke: false, fillColor: '#ffffff', fillOpacity: 0.45, interactive: false,
    }).addTo(boundaryLayer);
    L.polygon(boundaryRings.map(toLatLngs), {
      pane: 'mask', color: '#475569', weight: 2, opacity: 0.7, dashArray: '6 6', fill: false, interactive: false,
    }).addTo(boundaryLayer);
  }
  const boundaryBounds = boundaryRings.length ? L.latLngBounds(boundaryRings.flatMap(toLatLngs)) : null;
  if (boundaryBounds) {
    map.setMaxBounds(boundaryBounds.pad(0.25));
    map.options.maxBoundsViscosity = 0.8;
  }

  /* ================= Stav ================= */
  let cameras = [];
  let lots = [];
  const camById = new Map();
  const lotById = new Map();
  const camMarkers = new Map();
  const lotLayers = new Map(); // id -> { poly, badge }
  const filter = { q: '', status: new Set(), level: new Set() };
  let selected = null; // { kind: 'camera' | 'lot', id }
  let tab = 'cameras';
  let live = { cameras: false, parking: false };
  let lastOk = null;
  let parkingUpdatedAt = null;
  let autoFit = true;

  // Hodnoty z API idú do tried a textov – povolíme iba známe (ochrana pred podvrhnutým API).
  const statusOf = (c) => (c.status in STATUS_LABEL ? c.status : 'unknown');
  const levelOf = (p) => (p.occupied != null && p.level in LEVEL_LABEL ? p.level : 'none');
  const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const shortName = (c) => c.name.replace(/^Kamera \S+ – /, '');
  const isSel = (kind, id) => selected?.kind === kind && selected.id === id;

  /* ================= Kamery ================= */
  const cameraLayer = L.markerClusterGroup
    ? L.markerClusterGroup({
      maxClusterRadius: 44, disableClusteringAtZoom: 16, spiderfyOnMaxZoom: true, showCoverageOnHover: false,
      iconCreateFunction(cluster) {
        const sts = cluster.getAllChildMarkers().map((m) => m.options.status);
        const worst = sts.includes('offline') ? 'offline' : sts.includes('warning') ? 'warning' : sts.includes('online') ? 'online' : 'unknown';
        return L.divIcon({ className: `cluster is-${worst}`, html: `${icon('camera')}<b>${sts.length}</b>`, iconSize: [44, 30] });
      },
    })
    : L.layerGroup();
  // Zhluk: popis pre čítačky + ovládanie klávesnicou
  cameraLayer.on?.('animationend', () => { labelClusters(); declutterBadges(); });
  function labelClusters() {
    for (const el of map.getContainer().querySelectorAll('.cluster')) {
      el.setAttribute('aria-label', `${el.textContent.trim()} kamier – priblížiť`);
      el.title = `${el.textContent.trim()} kamier – kliknutím priblížite`;
    }
  }

  const PIN = '<svg viewBox="0 0 32 40"><path class="pin-shape" d="M16 38.5S3.5 25.8 3.5 15.5a12.5 12.5 0 0 1 25 0C28.5 25.8 16 38.5 16 38.5z"/></svg>';
  function camIcon(c) {
    const cls = ['pin', `is-${statusOf(c)}`, c.precision === 'približne' ? 'is-rough' : '', isSel('camera', c.id) ? 'is-selected' : ''];
    return L.divIcon({
      className: cls.filter(Boolean).join(' '), iconSize: [0, 0],
      html: `<span class="pin-body">${PIN}<svg class="pin-glyph"><use href="#i-camera"/></svg></span><span class="pin-no">${esc(c.no)}</span>`,
    });
  }
  const camLabel = (c) => `Kamera ${c.no} – ${shortName(c)}, ${STATUS_LABEL[statusOf(c)]}`;

  // Klávesnica: Leaflet značky sú fokusovateľné, ale Enter ich neaktivuje – doplníme to.
  function makeAccessible(el, label, onActivate) {
    if (!el) return;
    el.setAttribute('aria-label', label);
    el.setAttribute('role', 'button');
    if (el.dataset.kb) return;
    el.dataset.kb = '1';
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate(); }
    });
  }

  function buildCameras() {
    cameraLayer.clearLayers();
    camMarkers.clear();
    for (const c of cameras) {
      const m = L.marker([c.lat, c.lng], { icon: camIcon(c), status: statusOf(c), keyboard: true, riseOnHover: true, title: '' });
      m.bindTooltip(() => esc(camById.get(c.id).name), { className: 'tip', direction: 'top', offset: [0, -44], opacity: 1 });
      m.on('click', () => select('camera', c.id, { from: 'map' }));
      m.on('add', () => makeAccessible(m.getElement(), camLabel(camById.get(c.id)), () => select('camera', c.id, { from: 'map' })));
      m.on('mouseover', () => hoverRow('camera', c.id, true));
      m.on('mouseout', () => hoverRow('camera', c.id, false));
      camMarkers.set(c.id, m);
    }
  }

  /** Stav kamery sa zmenil – nová ikona (výber riešime triedou, aby sa ikona pri kliknutí nemenila). */
  function refreshCamIcon(id) {
    const c = camById.get(id), m = camMarkers.get(id);
    if (!c || !m) return;
    m.options.status = statusOf(c);
    m.setIcon(camIcon(c));
    makeAccessible(m.getElement(), camLabel(c), () => select('camera', id, { from: 'map' }));
    cameraLayer.refreshClusters?.(m);
  }

  const camMatches = (c) => {
    if (filter.status.size && !filter.status.has(statusOf(c))) return false;
    if (!filter.q) return true;
    const hay = fold(`${c.no} ${c.name} ${c.street} ${c.area}`);
    return filter.q.split(/\s+/).every((w) => hay.includes(w));
  };
  const lotMatches = (p) => {
    if (filter.level.size && !filter.level.has(levelOf(p))) return false;
    return !filter.q || filter.q.split(/\s+/).every((w) => fold(`${p.name} ${p.street}`).includes(w));
  };

  let shownCams = '';
  function applyCameraFilter(force = false) {
    // Filter platí pre zoznam aj mapu. Vybraná kamera ostane viditeľná, kým je vybraná.
    const keep = cameras.filter((c) => camMatches(c) || isSel('camera', c.id));
    const key = keep.map((c) => c.id).join();
    if (force || key !== shownCams) {
      shownCams = key;
      cameraLayer.clearLayers();
      const ms = keep.map((c) => camMarkers.get(c.id));
      if (cameraLayer.addLayers) cameraLayer.addLayers(ms); else ms.forEach((m) => m.addTo(cameraLayer));
      labelClusters();
    }
    renderCameraList();
  }

  /* ================= Parkoviská ================= */
  function lotIcon(p) {
    const lvl = levelOf(p);
    // Formát ako vo vizualizácii: obsadené/kapacita. Plné parkovisko ukáže jasne „Plné“.
    const text = lvl === 'none' ? `${num(p.capacity)} miest` : lvl === 'full' ? 'Plné' : `${num(p.occupied)}/${num(p.capacity)}`;
    return L.divIcon({
      className: `lot is-${lvl}${isSel('lot', p.id) ? ' is-selected' : ''}`, iconSize: [0, 0],
      html: `<span class="lot-badge"><span class="lot-p">P</span><span class="lot-t">${esc(text)}</span></span>`,
    });
  }
  const lotLabel = (p) => (levelOf(p) === 'none'
    ? `${p.name}, ${num(p.capacity)} miest`
    : `${p.name}: obsadené ${num(p.occupied)} z ${num(p.capacity)}, voľných ${num(p.free)}`);
  function lotStyle(p, hover = false) {
    const col = LEVEL_COLOR[levelOf(p)];
    const sel = isSel('lot', p.id);
    const dim = !lotMatches(p) && !sel;
    return {
      pane: 'lots', color: sel ? '#1d6fe5' : col, weight: sel ? 3.5 : 2.5, opacity: dim ? 0.25 : 1,
      fillColor: col, fillOpacity: dim ? 0.05 : hover ? 0.45 : 0.3,
    };
  }
  const parkingLayer = L.layerGroup();
  function buildParking() {
    parkingLayer.clearLayers();
    lotLayers.clear();
    for (const p of lots) {
      // bubblingMouseEvents: false – klik na plochu nesmie prebublať na mapu (tá výber ruší)
      const opts = { ...lotStyle(p), bubblingMouseEvents: false };
      const poly = p.polygon?.length >= 3 ? L.polygon(p.polygon, opts) : L.circle([p.lat, p.lng], { radius: 30, ...opts });
      const badge = L.marker([p.lat, p.lng], { icon: lotIcon(p), pane: 'badges', keyboard: true, title: '' });
      for (const l of [poly, badge]) {
        l.on('click', () => select('lot', p.id, { from: 'map' }));
        l.on('mouseover', () => { hoverRow('lot', p.id, true); poly.setStyle(lotStyle(lotById.get(p.id), true)); });
        l.on('mouseout', () => { hoverRow('lot', p.id, false); poly.setStyle(lotStyle(lotById.get(p.id))); });
      }
      badge.on('add', () => makeAccessible(badge.getElement(), lotLabel(lotById.get(p.id)), () => select('lot', p.id, { from: 'map' })));
      badge.bindTooltip(() => esc(lotLabel(lotById.get(p.id))), { className: 'tip', direction: 'top', offset: [0, -34], opacity: 1 });
      poly.addTo(parkingLayer);
      badge.addTo(parkingLayer);
      lotLayers.set(p.id, { poly, badge });
    }
  }
  function refreshLot(id, iconToo = true) {
    const p = lotById.get(id), l = lotLayers.get(id);
    if (!p || !l) return;
    l.poly.setStyle(lotStyle(p));
    if (iconToo) {
      l.badge.setIcon(lotIcon(p));
      makeAccessible(l.badge.getElement(), lotLabel(p), () => select('lot', id, { from: 'map' }));
    }
  }
  function applyParkingFilter() {
    for (const p of lots) {
      refreshLot(p.id, false);
      lotLayers.get(p.id)?.badge.getElement()?.classList.toggle('is-dim', !lotMatches(p) && !isSel('lot', p.id));
    }
    declutterBadges();
    renderParkingList();
  }

  /* ---------- Odznaky parkovísk sa nesmú prekrývať ---------- */
  // Každý odznak skúsi 4 polohy okolo parkoviska (hore, dole, vpravo, vľavo) a vyberie prvú, kde neprekrýva
  // kameru, zhluk ani iný odznak. Keď nikde nie je miesto, zmenší sa na „P“; keď ani to, schová sa
  // (farebná plocha parkoviska ostane viditeľná a klikateľná, čísla sú v tooltipe a v detaile).
  const POSITIONS = ['pos-t', 'pos-b', 'pos-r', 'pos-l'];
  function declutterBadges() {
    if (!map.hasLayer(parkingLayer)) return;
    const shrink = (r) => ({ left: r.left + 1, right: r.right - 1, top: r.top + 1, bottom: r.bottom - 1 });
    const placed = [...map.getContainer().querySelectorAll('.pin-body, .cluster')]
      .map((el) => el.getBoundingClientRect()).filter((r) => r.width).map(shrink);
    const overlaps = (a) => placed.some((b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top);
    const order = [...lots].sort((a, b) => isSel('lot', b.id) - isSel('lot', a.id)
      || lotMatches(b) - lotMatches(a) || num(b.capacity) - num(a.capacity));
    for (const p of order) {
      const el = lotLayers.get(p.id)?.badge.getElement();
      if (!el) continue;
      el.classList.remove('is-mini', 'is-hidden', ...POSITIONS);
      const badge = el.firstElementChild;
      const tryAll = () => {
        for (const pos of POSITIONS) {
          el.classList.add(pos);
          const r = badge.getBoundingClientRect();
          if (!overlaps(r)) return r;
          el.classList.remove(pos);
        }
        return null;
      };
      let r = tryAll();
      if (!r && isSel('lot', p.id)) { el.classList.add('pos-t'); r = badge.getBoundingClientRect(); }
      if (!r) { el.classList.add('is-mini'); r = tryAll(); }
      if (!r) { el.classList.add('is-hidden', 'pos-t'); continue; }
      placed.push(r);
    }
  }
  map.on('zoomend moveend', () => requestAnimationFrame(declutterBadges));

  /* ================= Výber + detail ================= */
  // closeOnClick: false – zatváranie riešime sami, inak by klik na už vybranú značku výber zrušil.
  const popup = L.popup({ className: 'callout', closeButton: false, closeOnClick: false, autoClose: false,
    autoPanPadding: [28, 28], maxWidth: 320, minWidth: 280 });

  function cameraCard(c) {
    const st = statusOf(c);
    const note = st === 'offline' || st === 'warning' ? c.status_note : null;
    return `<div class="co cam is-${st}">
      <div class="co-head"><span class="co-ico">${icon('camera')}</span>
        <div class="co-title"><b>${esc(c.name)}</b><span>${esc(c.street ?? '')}</span></div>
        <button class="co-close" data-close aria-label="Zavrieť">${icon('x')}</button></div>
      <div class="co-facts">
        <span class="tag is-status"><i class="dot is-${st}"></i>${STATUS_LABEL[st]}</span>
        <span class="tag">${c.type === 'statická' ? 'Statická' : 'Otočná'}</span>
        <span class="tag">${esc(c.area ?? '')}</span>
      </div>
      ${note ? `<p class="co-note is-${st}">${esc(note)}</p>` : ''}
      ${c.precision === 'približne' ? '<p class="co-note is-rough">Poloha je približná – v zozname mestskej polície je uvedená len oblasť.</p>' : ''}
      <div class="co-actions">
        <a class="btn btn-primary" href="${esc(API.searchUrl(c.id))}">${icon('search')}Hľadať vozidlo</a>
        <button class="btn" disabled title="Živý prenos zatiaľ nie je dostupný">${icon('play')}Živý prenos</button>
      </div></div>`;
  }

  function lotCard(p) {
    const lvl = levelOf(p);
    const has = lvl !== 'none';
    const pct = has ? Math.round(num(p.ratio) * 100) : 0;
    const stale = has && parkingUpdatedAt && Date.now() - parkingUpdatedAt > STALE_MS;
    const watch = (p.cameras ?? []).map((id) => camById.get(id)).filter(Boolean);
    return `<div class="co lot-co is-${lvl}">
      <div class="co-head"><span class="co-ico">${icon('parking')}</span>
        <div class="co-title"><b>${esc(p.name)}</b><span>${esc(p.street ?? '')}</span></div>
        <button class="co-close" data-close aria-label="Zavrieť">${icon('x')}</button></div>
      ${has ? `<div class="co-big"><b>${num(p.free)}</b><span>voľných miest</span></div>
        <div class="co-bar" role="img" aria-label="Obsadené ${pct} %"><i style="width:${pct}%"></i></div>
        <div class="co-meta"><span><b>${num(p.occupied)}</b> z ${num(p.capacity)} obsadených · ${LEVEL_LABEL[lvl]}</span>
          ${parkingUpdatedAt ? `<span class="${stale ? 'is-stale' : ''}">${stale ? 'Údaje z' : 'Aktualizované'} ${fmtTime(new Date(parkingUpdatedAt))}</span>` : ''}</div>`
      : `<div class="co-big"><b>${num(p.capacity)}</b><span>miest</span></div><div class="co-meta"><span>Obsadenosť sa zobrazí, keď pobeží API.</span></div>`}
      ${watch.length ? `<div class="co-cams"><p>Sledujú ho kamery</p><div>${watch.map((c) =>
        `<button class="cam-chip" data-camera="${esc(c.id)}"><i class="dot is-${statusOf(c)}"></i><b>${esc(c.no)}</b>${esc(shortName(c))}</button>`).join('')}</div></div>` : ''}
    </div>`;
  }

  function openCard() {
    if (!selected) return;
    let latlng, html, offset;
    if (selected.kind === 'camera') {
      const c = camById.get(selected.id), m = camMarkers.get(selected.id);
      if (!c || !m) return;
      [latlng, html, offset] = [m.getLatLng(), cameraCard(c), [0, -44]];
    } else {
      const p = lotById.get(selected.id);
      if (!p) return;
      [latlng, html, offset] = [L.latLng(p.lat, p.lng), lotCard(p), [0, -34]];
    }
    popup.options.offset = offset;
    popup.setLatLng(latlng).setContent(html);
    if (!map.hasLayer(popup)) popup.openOn(map);
    else popup.update();
  }

  // Ovládanie karty – delegované, takže funguje aj po výmene obsahu (iná kamera, obnova dát).
  map.getContainer().addEventListener('click', (e) => {
    if (!e.target.closest('.callout')) return;
    if (e.target.closest('[data-close]')) { clearSelection(); return; }
    const chip = e.target.closest('[data-camera]');
    if (chip) select('camera', chip.dataset.camera, { from: 'list' });
  });
  popup.on('add', () => {
    const el = popup.getElement();
    if (el) { L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el); }
  });

  // Stav „vybraná“ je priamo v ikone – zhlukovací plugin ikonu pri prekreslení vytvára nanovo.
  function setSelectedClass(kind, id) {
    if (kind === 'camera') refreshCamIcon(id);
    else { refreshLot(id); declutterBadges(); }
  }

  function select(kind, id, { from = 'list' } = {}) {
    if ((kind === 'camera' && !camById.has(id)) || (kind === 'lot' && !lotById.has(id))) return;
    autoFit = false;
    const prev = selected;
    selected = { kind, id };
    const token = selected;
    if (prev && !(prev.kind === kind && prev.id === id)) setSelectedClass(prev.kind, prev.id);
    if (prev?.kind === 'camera' && prev.id !== id) applyCameraFilter();
    if (MOBILE.matches && from === 'list') document.querySelector('.mapbox').scrollIntoView({ block: 'start', behavior: REDUCED.matches ? 'auto' : 'smooth' });

    if (kind === 'camera') {
      setLayer('cameras', true);
      const m = camMarkers.get(id);
      if (!cameraLayer.hasLayer(m)) applyCameraFilter();
      setSelectedClass('camera', id);
      const show = () => {
        if (selected !== token) return; // medzitým vybral niečo iné
        openCard();
        if (from === 'list') map.panInside(m.getLatLng(), { padding: [60, 60] });
      };
      // Kamera je v zhluku – priblížime na úroveň bez zhlukov (16), nezávisle od animácií pluginu
      if (!m.getElement()) {
        map.setView(m.getLatLng(), Math.max(map.getZoom(), 16), { animate: false });
        setTimeout(show, 350);
      } else show();
    } else {
      setLayer('parking', true);
      setSelectedClass('lot', id);
      openCard();
      const p = lotById.get(id);
      if (from === 'list') map.panInside([p.lat, p.lng], { padding: [80, 80] });
      declutterBadges();
    }
    setTab(kind === 'camera' ? 'cameras' : 'parking');
    markSelectedRows(true);
    syncUrl();
  }

  function clearSelection() {
    const prev = selected;
    if (!prev) return;
    selected = null;
    setSelectedClass(prev.kind, prev.id);
    if (map.hasLayer(popup)) map.closePopup(popup);
    if (prev.kind === 'camera') applyCameraFilter(); // vybraná kamera mohla byť zobrazená mimo filtra
    else applyParkingFilter();
    markSelectedRows(false);
    syncUrl();
  }
  map.on('click', clearSelection);

  function syncUrl() {
    const u = new URL(location.href);
    for (const k of ['camera', 'kamera', 'parkovisko']) u.searchParams.delete(k);
    if (selected?.kind === 'camera') u.searchParams.set('camera', selected.id);
    if (selected?.kind === 'lot') u.searchParams.set('parkovisko', selected.id);
    history.replaceState(null, '', u);
  }

  /* ================= Bočný panel ================= */
  function setTab(name) {
    tab = name;
    for (const b of document.querySelectorAll('[role="tab"]')) {
      const on = b.dataset.tab === name;
      b.setAttribute('aria-selected', String(on));
      b.tabIndex = on ? 0 : -1;
    }
    $('panel-cameras').hidden = name !== 'cameras';
    $('panel-parking').hidden = name !== 'parking';
  }
  for (const b of document.querySelectorAll('[role="tab"]')) {
    b.addEventListener('click', () => setTab(b.dataset.tab));
    b.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        const next = b.dataset.tab === 'cameras' ? 'parking' : 'cameras';
        setTab(next);
        $(`tab-${next}`).focus();
      }
    });
  }

  /** Prekreslí zoznam a vráti fokus na riadok, na ktorom bol (obnova dát nesmie zhodiť fokus). */
  function renderList(list, html) {
    const active = document.activeElement?.closest?.('.row');
    const key = active && list.contains(active) ? `${active.dataset.kind}|${active.dataset.id}` : null;
    const scroll = list.scrollTop;
    list.innerHTML = html;
    list.scrollTop = scroll;
    if (key) {
      const [k, id] = key.split('|');
      rowEl(k, id)?.focus({ preventScroll: true });
    }
    markSelectedRows(false);
  }

  const emptySearch = () => `<li class="empty">Pre „${esc($('q').value.trim())}“ sme nič nenašli.<br><button class="link" data-clear-search>Zrušiť hľadanie</button></li>`;

  function renderCameraList() {
    const list = $('list-cameras');
    const shown = cameras.filter(camMatches);
    $('tc-cameras').textContent = filter.q || filter.status.size ? `${shown.length}/${cameras.length}` : cameras.length || '–';
    if (!cameras.length) return renderList(list, '<li class="empty">V konfigurácii nie sú žiadne kamery.</li>');
    if (!shown.length) return renderList(list, filter.q ? emptySearch() : '<li class="empty">Žiadna kamera v tomto stave.</li>');
    const groups = new Map();
    for (const c of shown) {
      const a = c.area ?? 'Ostatné';
      if (!groups.has(a)) groups.set(a, []);
      groups.get(a).push(c);
    }
    const byNo = (a, b) => (parseInt(a.no, 10) || 999) - (parseInt(b.no, 10) || 999) || String(a.no).localeCompare(String(b.no));
    let html = '';
    for (const [area, cs] of groups) {
      html += `<li class="group" aria-hidden="true"><span>${esc(area)}</span><span>${cs.length}</span></li>`;
      for (const c of cs.sort(byNo)) {
        const st = statusOf(c);
        const sub = (st === 'offline' || st === 'warning') && c.status_note
          ? `<span class="row-sub is-${st}">${esc(c.status_note)}</span>`
          : `<span class="row-sub">${esc(c.street ?? '')}</span>`;
        html += `<li><button class="row" data-kind="camera" data-id="${esc(c.id)}" aria-label="${esc(camLabel(c))}">
          <span class="cam-no">${esc(c.no)}<i class="dot is-${st}"></i></span>
          <span class="row-main"><span class="row-title">${esc(shortName(c))}</span>${sub}</span></button></li>`;
      }
    }
    renderList(list, html);
  }

  function renderParkingList() {
    const list = $('list-parking');
    let shown = lots.filter(lotMatches);
    $('tc-parking').textContent = filter.q || filter.level.size ? `${shown.length}/${lots.length}` : lots.length || '–';
    if (!lots.length) return renderList(list, '<li class="empty">V konfigurácii nie sú žiadne parkoviská.</li>');
    if (!shown.length) return renderList(list, filter.q ? emptySearch() : '<li class="empty">Žiadne parkovisko v tomto stave.</li>');
    const byName = (a, b) => a.name.localeCompare(b.name, 'sk');
    shown = [...shown].sort($('park-sort').value === 'name' || !live.parking ? byName : (a, b) => num(b.free) - num(a.free) || byName(a, b));
    renderList(list, shown.map((p) => {
      const lvl = levelOf(p);
      const has = lvl !== 'none';
      const pct = Math.round(num(p.ratio) * 100);
      return `<li><button class="row" data-kind="lot" data-id="${esc(p.id)}" aria-label="${esc(lotLabel(p))}">
        <span class="p-badge is-${lvl}">P</span>
        <span class="row-main"><span class="row-title">${esc(p.name.replace(/^Parkovisko /, ''))}</span>
          <span class="row-sub">${has ? `<b>${num(p.free)}</b> voľných · obsadené ${num(p.occupied)}/${num(p.capacity)}` : `${num(p.capacity)} miest · ${esc(p.street ?? '')}`}</span></span>
        ${has ? `<span class="occ" aria-hidden="true"><span class="occ-bar is-${lvl}"><i style="width:${pct}%"></i></span></span>` : ''}
      </button></li>`;
    }).join(''));
  }
  $('park-sort').addEventListener('change', renderParkingList);

  for (const listId of ['list-cameras', 'list-parking']) {
    const list = $(listId);
    list.addEventListener('click', (e) => {
      if (e.target.closest('[data-clear-search]')) { $('q').value = ''; setQuery(''); $('q').focus(); return; }
      const row = e.target.closest('.row');
      if (row) select(row.dataset.kind, row.dataset.id, { from: 'list' });
    });
    list.addEventListener('mouseover', (e) => { const r = e.target.closest('.row'); if (r) hoverMarker(r.dataset.kind, r.dataset.id, true); });
    list.addEventListener('mouseout', (e) => { const r = e.target.closest('.row'); if (r) hoverMarker(r.dataset.kind, r.dataset.id, false); });
    list.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      const rows = [...list.querySelectorAll('.row')];
      const i = rows.indexOf(document.activeElement);
      const next = rows[Math.max(0, Math.min(rows.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))];
      if (next) { e.preventDefault(); next.focus(); }
    });
  }

  function rowEl(kind, id) { return document.querySelector(`.row[data-kind="${kind}"][data-id="${CSS.escape(id)}"]`); }
  function hoverRow(kind, id, on) { rowEl(kind, id)?.classList.toggle('is-hover', on); } // zoznam pritom neposúvame
  function hoverMarker(kind, id, on) {
    if (kind === 'camera') camMarkers.get(id)?.getElement()?.classList.toggle('is-hover', on);
    else {
      const l = lotLayers.get(id), p = lotById.get(id);
      if (!l || !p) return;
      l.badge.getElement()?.classList.toggle('is-hover', on);
      l.poly.setStyle(lotStyle(p, on));
    }
  }
  function markSelectedRows(scroll) {
    for (const r of document.querySelectorAll('.row.is-selected')) r.classList.remove('is-selected');
    if (!selected) return;
    const r = rowEl(selected.kind, selected.id);
    if (!r) return;
    r.classList.add('is-selected');
    r.setAttribute('aria-current', 'true');
    if (scroll && !MOBILE.matches) r.scrollIntoView({ block: 'nearest', behavior: REDUCED.matches ? 'auto' : 'smooth' });
  }

  /* ---------- Hľadanie ---------- */
  let typing;
  function setQuery(v) {
    filter.q = fold(v.trim());
    applyCameraFilter();
    applyParkingFilter();
    if (!filter.q) return;
    const camHits = cameras.filter(camMatches);
    const lotHits = lots.filter(lotMatches);
    // Prepni na záložku, kde niečo je
    if (!camHits.length && lotHits.length) setTab('parking');
    else if (camHits.length && !lotHits.length) setTab('cameras');
    // Ukáž nájdené na mape
    const b = L.latLngBounds([...camHits.map((c) => [c.lat, c.lng]), ...lotHits.map((p) => [p.lat, p.lng])]);
    if (b.isValid() && camHits.length + lotHits.length <= 12) {
      autoFit = false;
      map.flyToBounds(b, { padding: [70, 70], maxZoom: 17, duration: REDUCED.matches ? 0 : 0.5 });
    }
  }
  $('q').addEventListener('input', (e) => { clearTimeout(typing); typing = setTimeout(() => setQuery(e.target.value), 180); });
  $('q').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      clearTimeout(typing);
      setQuery(e.target.value);
      document.querySelector(`#list-${tab} .row`)?.click();
    } else if (e.key === 'Escape') {
      e.stopPropagation(); // nezatvárať pritom vybranú kameru
      e.target.value = ''; setQuery(''); e.target.blur();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault(); document.querySelector(`#list-${tab} .row`)?.focus();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !e.target.closest('input, select, textarea')) { e.preventDefault(); $('q').focus(); }
    if (e.key === 'Escape' && e.target !== $('q')) clearSelection();
  });

  /* ---------- Filtre stavu (kamery) a obsadenosti (parkoviská) ---------- */
  for (const chip of document.querySelectorAll('.chip[data-status]')) {
    chip.addEventListener('click', () => {
      const v = chip.dataset.status;
      filter.status.has(v) ? filter.status.delete(v) : filter.status.add(v);
      chip.setAttribute('aria-pressed', String(filter.status.has(v)));
      applyCameraFilter();
    });
  }
  for (const chip of document.querySelectorAll('.chip[data-level]')) {
    chip.addEventListener('click', () => {
      const v = chip.dataset.level;
      filter.level.has(v) ? filter.level.delete(v) : filter.level.add(v);
      chip.setAttribute('aria-pressed', String(filter.level.has(v)));
      applyParkingFilter();
    });
  }
  function renderCounts() {
    for (const chip of document.querySelectorAll('.chip[data-status]')) {
      chip.querySelector('b').textContent = live.cameras ? cameras.filter((c) => statusOf(c) === chip.dataset.status).length : '–';
      chip.disabled = !live.cameras;
    }
    for (const chip of document.querySelectorAll('.chip[data-level]')) {
      chip.querySelector('b').textContent = live.parking ? lots.filter((p) => levelOf(p) === chip.dataset.level).length : '–';
      chip.disabled = !live.parking;
    }
    const free = lots.reduce((s, p) => s + num(p.free), 0);
    $('park-summary').innerHTML = live.parking ? `<b>${free}</b> voľných miest` : `${lots.reduce((s, p) => s + num(p.capacity), 0)} miest spolu`;
    $('park-updated').textContent = parkingUpdatedAt ? `Aktualizované ${fmtTime(new Date(parkingUpdatedAt))}` : '';
  }

  /* ---------- Vrstvy ---------- */
  const registry = { cameras: cameraLayer, parking: parkingLayer, boundary: boundaryLayer };
  function setLayer(name, on) {
    const layer = registry[name];
    if (on && !map.hasLayer(layer)) layer.addTo(map);
    if (!on && map.hasLayer(layer)) map.removeLayer(layer);
    const box = document.querySelector(`.switch[data-layer="${name}"]`);
    if (box) box.checked = on;
    document.querySelector(`.hidden-note[data-for="${name}"]`)?.toggleAttribute('hidden', on);
    if (!on && selected && ((name === 'cameras' && selected.kind === 'camera') || (name === 'parking' && selected.kind === 'lot'))) clearSelection();
    if (on && name === 'parking') applyParkingFilter();
    if (on && name === 'cameras') labelClusters();
    requestAnimationFrame(declutterBadges);
  }
  for (const box of document.querySelectorAll('.switch')) box.addEventListener('change', () => setLayer(box.dataset.layer, box.checked));
  for (const b of document.querySelectorAll('[data-show]')) b.addEventListener('click', () => setLayer(b.dataset.show, true));

  /* ---------- Zoom-závislé zobrazenie ---------- */
  function syncZoomClasses() {
    const z = map.getZoom();
    map.getContainer().classList.toggle('show-numbers', z >= 17);
    map.getContainer().classList.toggle('compact', z <= 13);
  }
  map.on('zoomend', syncZoomClasses);

  /* ---------- Ovládanie mapy ---------- */
  // Úvodný výrez = mestské jadro (do ~1,3 km od stredu kamier) – tam je väčšina kamier a parkovísk
  // a mapa je dosť priblížená na čitateľné odznaky. „Celý Pezinok“ ukáže všetko.
  function coreBounds() {
    const pts = cameras.filter((c) => !OUTLYING.has(c.area)).map((c) => L.latLng(c.lat, c.lng));
    if (!pts.length) return null;
    const med = (a) => a.sort((x, y) => x - y)[Math.floor(a.length / 2)];
    const center = L.latLng(med(pts.map((p) => p.lat)), med(pts.map((p) => p.lng)));
    const b = L.latLngBounds([]);
    for (const p of [...pts, ...lots.map((l) => L.latLng(l.lat, l.lng))]) if (center.distanceTo(p) < 1300) b.extend(p);
    return b.isValid() ? b : null;
  }
  function allBounds() {
    const b = L.latLngBounds([]);
    for (const c of cameras) b.extend([c.lat, c.lng]);
    for (const p of lots) b.extend([p.lat, p.lng]);
    return b.isValid() ? b : boundaryBounds;
  }
  // Rezerva: špendlíky siahajú ~45 px nad bod, odznaky ~40 px; vpravo sú tlačidlá
  const PAD = { paddingTopLeft: [40, 56], paddingBottomRight: [64, 24] };
  function fitTown(animate) {
    const b = coreBounds() ?? allBounds();
    if (b) map.fitBounds(b, { ...PAD, animate });
    else map.setView([48.2876, 17.2668], 15);
  }
  function fitAll() {
    const b = allBounds();
    if (b) map.flyToBounds(b, { ...PAD, duration: REDUCED.matches ? 0 : 0.5 });
  }
  $('zoom-in').addEventListener('click', () => { autoFit = false; map.zoomIn(); });
  $('zoom-out').addEventListener('click', () => { autoFit = false; map.zoomOut(); });
  $('fit').addEventListener('click', () => { autoFit = false; fitAll(); });
  for (const ev of ['mousedown', 'wheel', 'touchstart', 'keydown']) map.getContainer().addEventListener(ev, () => { autoFit = false; }, { passive: true });
  new ResizeObserver(() => { map.invalidateSize(); if (autoFit && (cameras.length || lots.length)) fitTown(false); }).observe($('map'));

  /* ================= Dáta ================= */
  function showBanner(html, error = false) {
    const b = $('banner');
    b.innerHTML = html;
    b.classList.toggle('is-error', error);
    b.hidden = !html;
  }

  let freshState = '';
  function setFresh() {
    const el = $('fresh');
    let state, text;
    if (!live.cameras && !live.parking) { state = 'config'; text = 'Bez API – polohy z konfigurácie'; }
    else if (!lastOk) { state = 'down'; text = 'Spojenie prerušené'; }
    else if (Date.now() - lastOk > 2 * 60_000) { state = 'old'; text = `Dáta z ${fmtTime(new Date(lastOk))}`; }
    else { state = 'ok'; text = `Dáta aktuálne · ${fmtTime(new Date(lastOk))}`; }
    el.dataset.state = state;
    el.querySelector('span').textContent = text;
    // Čítačka obrazovky ohlási iba zmenu stavu, nie každú minútu
    el.setAttribute('aria-live', state !== freshState ? 'polite' : 'off');
    freshState = state;
    el.title = live.cameras || live.parking
      ? `FlowSight API ${API.base}. Stav kamier a obsadenosť parkovísk sú zatiaľ ukážkové.`
      : `API ${API.base} nebeží – kamery a parkoviská sú priamo z config/*.yaml`;
  }
  setInterval(setFresh, 15_000);

  async function loadAll() {
    $('list-cameras').innerHTML = '<li class="skeleton"></li>'.repeat(6);
    let camRes, lotRes;
    try { [camRes, lotRes] = await Promise.all([API.cameras(), API.parking()]); }
    catch {
      showBanner('Údaje o kamerách a parkoviskách sú nedostupné. Spustite API (DEV11): <code>uvicorn app.main:app --port 8000</code> <button class="link" data-retry>Skúsiť znova</button>', true);
      $('list-cameras').innerHTML = '';
      setFresh();
      return;
    }
    showBanner('');
    cameras = camRes.items; lots = lotRes.items;
    live = { cameras: camRes.live, parking: lotRes.live };
    API.live = camRes.live;
    if (live.cameras || live.parking) lastOk = Date.now();
    parkingUpdatedAt = lotRes.updatedAt ? Date.parse(lotRes.updatedAt) : null;
    camById.clear(); lotById.clear();
    cameras.forEach((c) => camById.set(c.id, c));
    lots.forEach((p) => lotById.set(p.id, p));
    $('nav-search').href = API.searchUrl(null);

    buildCameras();
    buildParking();
    for (const box of document.querySelectorAll('.switch')) if (box.checked) registry[box.dataset.layer].addTo(map);
    applyCameraFilter(true);
    renderCounts();
    fitTown(false);
    syncZoomClasses();
    applyParkingFilter();
    setFresh();
    if (!live.cameras) showBanner('API (DEV11) nebeží – polohy sú priamo z konfigurácie, bez stavu kamier a obsadenosti. <button class="link" data-retry>Skúsiť znova</button>');

    // Odkaz priamo na kameru / parkovisko: ?camera=msp-12, ?kamera=12, ?parkovisko=p-7
    const qs = new URLSearchParams(location.search);
    const camParam = qs.get('camera') ?? (qs.get('kamera') ? `msp-${qs.get('kamera')}` : null);
    if (camParam && camById.has(camParam)) select('camera', camParam, { from: 'list' });
    else if (qs.get('parkovisko') && lotById.has(qs.get('parkovisko'))) select('lot', qs.get('parkovisko'), { from: 'list' });

    if (live.parking) setInterval(refreshParking, PARKING_REFRESH_MS);
    if (live.cameras) setInterval(refreshCameras, CAMERA_REFRESH_MS);
  }
  $('banner').addEventListener('click', (e) => { if (e.target.closest('[data-retry]')) location.reload(); });

  async function refreshParking() {
    try {
      const r = await API.getJson('/api/parking');
      parkingUpdatedAt = Date.parse(r.updated_at);
      for (const p of r.parking) {
        const old = lotById.get(p.id);
        if (!old) continue;
        const changed = old.occupied !== p.occupied || old.level !== p.level;
        Object.assign(old, p);
        if (changed) refreshLot(p.id);
      }
      lastOk = Date.now();
      renderCounts();
      applyParkingFilter();
      if (selected?.kind === 'lot') openCard();
    } catch { lastOk = 0; }
    setFresh();
  }
  async function refreshCameras() {
    try {
      const r = await API.getJson('/api/cameras');
      let changed = false;
      for (const c of r.cameras) {
        const old = camById.get(c.id);
        if (!old) continue;
        const st = old.status !== c.status;
        Object.assign(old, c);
        if (st) { refreshCamIcon(c.id); changed = true; }
      }
      lastOk = Date.now();
      if (changed) { renderCounts(); applyCameraFilter(true); }
      if (selected?.kind === 'camera' && changed) openCard();
    } catch { lastOk = 0; }
    setFresh();
  }

  map.setView([48.2876, 17.2668], 14);
  loadAll();
})();
