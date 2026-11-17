'use strict';
/*
 * FlowSight – modul Udalosti (ukážka). Udalosti sú z data/events.js, stav sa drží len v pamäti stránky.
 * Neskôr ich má posielať backend (detekcie zo spracovania videa a udalosti z kamier Axis).
 */
(function () {
  const $ = (id) => document.getElementById(id);
  const MIN = 60e3;
  const loadedAt = Date.now();
  const cameras = new Map((window.FLOWSIGHT_CAMERAS ?? []).map((c) => [c.id, c]));
  const events = (window.FLOWSIGHT_EVENTS ?? []).map((e) => ({
    ...e,
    at: new Date(loadedAt - e.minutesAgo * MIN),
    history: e.history.map((h) => ({ at: new Date(loadedAt - h.minutesAgo * MIN), text: h.text })),
  })).sort((a, b) => b.at - a.at);

  /* ---------- Pomocné ---------- */
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    }
    node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
    return node;
  }
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS(svg.namespaceURI, 'use');
    use.setAttribute('href', `#i-${name}`);
    svg.setAttribute('aria-hidden', 'true');
    svg.append(use);
    return svg;
  }
  const fmtTime = new Intl.DateTimeFormat('sk-SK', { hour: '2-digit', minute: '2-digit' });
  const fmtDay = new Intl.DateTimeFormat('sk-SK', { weekday: 'long', day: 'numeric', month: 'long' });
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  function dayLabel(d) {
    const diff = Math.round((startOfDay(new Date()) - startOfDay(d)) / (24 * 60 * MIN));
    return diff === 0 ? 'Dnes' : diff === 1 ? 'Včera' : fmtDay.format(d);
  }
  function ago(d) {
    const m = Math.round((Date.now() - d) / MIN);
    if (m < 1) return 'práve teraz';
    if (m < 60) return `pred ${m} min`;
    if (m < 12 * 60) return `pred ${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ''}`;
    return `${dayLabel(d).toLowerCase()} ${fmtTime.format(d)}`;
  }
  const camera = (id) => cameras.get(id) ?? { id, name: id, area: '', street: '' };
  const shortCam = (id) => camera(id).name.replace(/^Kamera (\S+) – /, '$1 · ');
  const fmtConf = (c) => c.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  /* ---------- Filtre ---------- */
  const STATUS_TABS = [
    ['open', 'Otvorené', (e) => e.status !== 'vyriešená'],
    ['vyriešená', 'Vyriešené', (e) => e.status === 'vyriešená'],
    ['all', 'Všetky', () => true],
  ];
  const TYPES = [...new Set(events.map((e) => e.type))];
  const params = new URLSearchParams(location.search);
  const view = { status: 'open', types: new Set(), selected: params.get('event') };

  const statusTest = (key) => STATUS_TABS.find(([k]) => k === key)[2];
  const typeTest = (e) => !view.types.size || view.types.has(e.type);
  const visible = () => events.filter((e) => statusTest(view.status)(e) && typeTest(e));

  function renderFilters() {
    $('status-tabs').replaceChildren(...STATUS_TABS.map(([key, label, test]) => {
      const n = events.filter((e) => test(e) && typeTest(e)).length;
      const isNew = key === 'open' ? events.filter((e) => e.status === 'nová' && typeTest(e)).length : 0;
      return el('label', {},
        el('input', { type: 'radio', name: 'status', value: key, checked: view.status === key, onchange: () => { view.status = key; render(true); } }),
        el('span', {}, `${label} `, el('b', { text: String(n) }), isNew ? el('i', { class: 'new-dot', title: `${isNew} nové` }) : null));
    }));
    const base = events.filter(statusTest(view.status));
    $('type-filter').replaceChildren(...TYPES.map((type) => {
      const n = base.filter((e) => e.type === type).length;
      const on = view.types.has(type);
      return el('button', {
        type: 'button', class: 'type-chip', 'aria-pressed': String(on), disabled: !n && !on,
        onclick: () => { on ? view.types.delete(type) : view.types.add(type); render(true); },
      }, el('span', { text: type }), el('b', { text: String(n) }));
    }));
  }

  /* ---------- Zoznam ---------- */
  function media(e, cls) {
    const box = el('span', { class: `${cls} sev-${sevKey(e)}` });
    if (!e.image) { box.classList.add('is-empty'); box.append(icon(e.type === 'Kamera bez obrazu' ? 'camera' : 'alert')); return box; }
    const img = el('img', { src: e.image, alt: '', loading: 'lazy' });
    img.addEventListener('error', () => { img.remove(); box.classList.add('is-empty'); box.append(icon('alert')); }, { once: true });
    box.append(img);
    return box;
  }
  const sevKey = (e) => ({ 'kritická': 'crit', varovanie: 'warn', info: 'info' }[e.severity]);
  const statusBadge = (e) => el('span', { class: `status status-${e.status === 'nová' ? 'new' : e.status === 'rieši sa' ? 'active' : 'done'}`, text: e.status === 'nová' ? 'Nová' : e.status === 'rieši sa' ? 'Rieši sa' : 'Vyriešená' });

  function renderFeed(list) {
    const items = [];
    let lastDay = null;
    for (const e of list) {
      const day = dayLabel(e.at);
      if (day !== lastDay) { items.push(el('li', { class: 'feed-day', text: day })); lastDay = day; }
      items.push(el('li', { class: 'feed-row' },
        el('button', {
          type: 'button', class: `feed-item sev-${sevKey(e)}${e.status === 'nová' ? ' is-new' : ''}`, 'data-id': e.id,
          'aria-current': e.id === view.selected ? 'true' : null,
          onclick: () => select(e.id, true),
        },
        media(e, 'feed-thumb'),
        el('span', { class: 'feed-text' },
          el('span', { class: 'feed-title' }, el('strong', { text: e.type }), e.status !== 'nová' ? statusBadge(e) : null),
          el('span', { class: 'feed-meta' }, icon('camera'), el('span', { text: shortCam(e.camera) })),
          el('span', { class: 'feed-time' }, el('time', { datetime: e.at.toISOString(), text: ago(e.at) })),
        ))));
    }
    $('feed').replaceChildren(...items);
    $('feed-empty').hidden = list.length > 0;
    if (!list.length) {
      $('feed-empty-text').textContent = view.status === 'open' && !view.types.size
        ? 'Všetko je vyriešené. Nová udalosť sa objaví hore v zozname.'
        : 'Filtrom nevyhovuje žiadna udalosť.';
    }
  }

  /* ---------- Detail ---------- */
  function renderDetail() {
    const e = events.find((x) => x.id === view.selected);
    const box = $('detail');
    if (!e) {
      box.replaceChildren(el('div', { class: 'detail-empty' }, icon('alert'), el('p', { text: 'Vyberte udalosť zo zoznamu.' })));
      return;
    }
    const cam = camera(e.camera);
    const frame = el('figure', { class: 'detail-frame' });
    if (e.image) {
      const wrap = el('span', { class: 'frame-wrap' });
      const img = el('img', { src: e.image, alt: `Záber z kamery ${cam.name}: ${e.type.toLowerCase()}` });
      img.addEventListener('error', () => { frame.replaceChildren(noImage('Záber sa nepodarilo načítať.')); }, { once: true });
      wrap.append(img);
      if (e.box) {
        const [x, y, w, h] = e.box;
        wrap.append(el('span', { class: `bbox sev-${sevKey(e)}`, style: `left:${x}%;top:${y}%;width:${w}%;height:${h}%` },
          el('span', { class: 'bbox-label', text: `${e.label} ${fmtConf(e.confidence)}` })));
      }
      frame.append(wrap, el('figcaption', {},
        el('span', { class: 'rec' }, el('i'), `${cam.name.replace(/ – .*/, '')} · ${fmtTime.format(e.at)}`),
        e.credit ? el('span', { class: 'credit', text: e.credit }) : null));
    } else {
      frame.append(noImage('Kamera neposiela obraz.'));
    }

    const actions = el('div', { class: 'detail-actions' });
    if (e.status === 'nová') actions.append(el('button', { type: 'button', class: 'primary', onclick: () => setStatus(e, 'rieši sa', 'Prevzal operátor') }, icon('hand'), el('span', { text: 'Prevziať' })));
    if (e.status === 'rieši sa') actions.append(el('button', { type: 'button', class: 'primary', onclick: () => setStatus(e, 'vyriešená', 'Vyriešené operátorom') }, icon('check'), el('span', { text: 'Označiť ako vyriešené' })));
    if (e.status === 'vyriešená') actions.append(el('button', { type: 'button', class: 'secondary', onclick: () => setStatus(e, 'rieši sa', 'Znovu otvorené') }, icon('undo'), el('span', { text: 'Znovu otvoriť' })));
    actions.append(el('a', { class: 'secondary', href: `../DEV12-interactive-map/mapa.html?camera=${encodeURIComponent(e.camera)}` }, icon('pin'), el('span', { text: 'Ukázať na mape' })));
    if (e.vehicle) actions.append(el('a', { class: 'secondary', href: `index.html?camera=${encodeURIComponent(e.camera)}` }, icon('search'), el('span', { text: 'Hľadať vozidlo' })));

    const facts = [
      ['Čas', `${fmtTime.format(e.at)}, ${dayLabel(e.at).toLowerCase()} (${ago(e.at)})`],
      ['Kamera', `${cam.name}${cam.street ? ` – ${cam.street}` : ''}`],
      ['Časť mesta', cam.area || '—'],
      e.label ? ['Detekcia', `${e.label}, istota modelu ${fmtConf(e.confidence)}`] : null,
      ['ID udalosti', e.id],
    ].filter(Boolean);

    box.replaceChildren(
      el('div', { class: 'detail-head' },
        el('div', {},
          el('p', { class: `severity sev-${sevKey(e)}` }, el('i'), el('span', { text: e.severity === 'info' ? 'Informácia' : e.severity === 'kritická' ? 'Kritická' : 'Varovanie' })),
          el('h2', { id: 'detail-title', text: e.type })),
        statusBadge(e)),
      frame,
      el('p', { class: 'detail-text', text: e.text }),
      actions,
      el('dl', { class: 'facts' }, ...facts.map(([k, v]) => el('div', {}, el('dt', { text: k }), el('dd', { text: v })))),
      el('div', { class: 'history' },
        el('h3', { text: 'Priebeh' }),
        el('ol', {}, ...[...e.history].reverse().map((h) => el('li', {},
          el('time', { datetime: h.at.toISOString(), text: fmtTime.format(h.at) }), el('span', { text: h.text }))))),
    );
  }
  function noImage(text) {
    return el('div', { class: 'frame-empty' }, icon('camera'), el('span', { text }));
  }

  function setStatus(e, status, note) {
    e.status = status;
    e.history.push({ at: new Date(), text: note });
    render();
    $('detail').querySelector('.detail-actions button')?.focus();
  }

  function select(id, fromClick = false) {
    view.selected = id;
    const url = new URL(location.href);
    url.searchParams.set('event', id);
    history.replaceState(null, '', url);
    render();
    if (fromClick && matchMedia('(max-width: 960px)').matches) $('detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // filterChanged: používateľ zmenil filter → ak vybraná udalosť zmizla zo zoznamu, ukáž prvú viditeľnú.
  // Po zmene stavu (Prevziať, Vyriešiť) vybraná udalosť zostáva v detaile, aj keď ju filter skryje.
  function render(filterChanged = false) {
    const list = visible();
    const hidden = !list.some((e) => e.id === view.selected);
    if (!view.selected || !events.some((e) => e.id === view.selected) || (filterChanged && hidden)) view.selected = list[0]?.id ?? null;
    renderFilters();
    renderFeed(list);
    renderDetail();
    const open = events.filter((e) => e.status === 'nová').length;
    document.title = `${open ? `(${open}) ` : ''}FlowSight · Udalosti`;
  }

  $('feed-reset').addEventListener('click', () => { view.status = 'all'; view.types.clear(); render(true); });
  // Relatívne časy („pred 5 min“) sa obnovujú každú minútu.
  setInterval(() => { renderFeed(visible()); }, MIN);
  render();
})();
