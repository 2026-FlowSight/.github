'use strict';
/*
 * FlowSight – vyhľadávací dashboard (DEV13 / SCRUM-26)
 *
 * Dva režimy:
 *  - Ukážkové dáta (predvolené): nič sa neposiela, výsledky sú pevné záznamy z projektového datasetu
 *    data/crops a data/frames (RoundaboutHD, nie Pezinok). Časy, kamery a skóre sú vymyslené.
 *  - API: po zadaní adresy v paneli „Pre vývojárov“ (alebo ?api=… v URL) sa obrázok posiela na
 *    POST {api}/api/search ako multipart/form-data. Kontrakt je NÁVRH na dohodu s backendom (SCRUM-24).
 */

const $ = (id) => document.getElementById(id);

const CONFIG = {
  topK: 3,
  maxBytes: 10 * 1024 * 1024,
  types: ['image/jpeg', 'image/png', 'image/webp'],
  targetMs: 2000,       // Definition of Done: výsledky do 2 s
  requestTimeoutMs: 15000,
  demoLatencyMs: 420,   // iba aby bol vidieť stav načítavania
  storageKey: 'flowsight.dev13.apiUrl',
};

// Spoločný zoznam kamier s mapou (data/cameras.js); záloha, ak sa súbor nenačíta.
const CAMERAS = window.FLOWSIGHT_CAMERAS ?? [
  { id: 'msp-25', name: 'Kamera 25 – Za hradbami', area: 'Juh' },
  { id: 'msp-5', name: 'Kamera 5 – Mladoboleslavská', area: 'Centrum' },
  { id: 'msp-21', name: 'Kamera 21 – Trnavská Tabak', area: 'Muškát' },
];
const cameraName = (id) => CAMERAS.find((c) => c.id === id)?.name ?? String(id ?? '—');

/* ---------- Ukážkové dáta ---------- */
const HOUR = 3600e3;
const ago = (hours) => new Date(Date.now() - hours * HOUR).toISOString();
const rec = (file, camera, hoursAgo, score) => ({ id: file.slice(0, 8), image: `assets/records/${file}`, camera, time: ago(hoursAgo), score });

// Prvý výsledok v každej sade je naozaj to isté vozidlo z iného záberu datasetu.
const DEMO = [
  {
    id: 'q-dodavka', label: 'Biela dodávka s rebríkmi', image: 'assets/query/92a67969-b69a-497e-9027-6406389581d2.jpg',
    results: [
      rec('7cd82cd2-6b4c-47a3-a043-89939be894b9.jpg', 'msp-21', 1.3, 0.93),
      rec('1b916e01-9f85-489c-93ff-041bdfc74649.jpg', 'msp-25', 19.5, 0.81),
      rec('b1e24a5b-54da-4f48-98a8-3322e97d83ce.jpg', 'msp-5', 74, 0.77),
    ],
  },
  {
    id: 'q-suv', label: 'Strieborné SUV', image: 'assets/query/2b9cd1d6-bdb1-4afa-9994-12fc5a5232d6.jpg',
    results: [
      rec('5b220606-965a-4505-9112-9b043a772a68.jpg', 'msp-5', 0.6, 0.91),
      rec('d6cf536e-f592-4060-baf4-055b19d17a3c.jpg', 'msp-25', 27, 0.84),
      rec('9f9c3ce1-28f0-4e09-aa44-ce078969fe18.jpg', 'msp-21', 50, 0.76),
    ],
  },
  {
    id: 'q-servis', label: 'Servisné nákladné vozidlo', image: 'assets/query/8307c3e7-cb29-491c-bbda-9ee8e2cc1804.jpg',
    results: [
      rec('a5cc9185-2da8-4bbb-94b4-658594554902.jpg', 'msp-25', 2.2, 0.95),
      rec('c35e9162-0575-47be-8b8c-16a092f0b8b2.jpg', 'msp-5', 8, 0.71),
      rec('f0368b01-a2dc-47e0-bbd9-95e7df7a530b.jpg', 'msp-21', 30, 0.68),
    ],
  },
  {
    id: 'q-sedan', label: 'Biely sedan', image: 'assets/query/0d4f8675-66de-4df1-b74e-70a3be076d80.jpg',
    results: [
      rec('58fa6645-e014-4956-b873-e17e6793627a.jpg', 'msp-5', 3.5, 0.83),
      rec('5012a50d-b7fa-4e22-b077-ea4d5c37c22f.jpg', 'msp-25', 22, 0.74),
      rec('7c3822c1-0d68-4ef1-b752-9e2b2f849938.jpg', 'msp-21', 100, 0.71),
    ],
  },
];

/* ---------- Stav ---------- */
const state = {
  query: null,        // { name, url, file?: File, demoId?: string }
  objectUrl: null,
  generation: 0,      // ochrana pred pretekmi požiadaviek
  fileToken: 0,       // ochrana pred pretekmi pri overovaní nahratých súborov
  controller: null,
  busy: false,
  validating: false,
  lastResults: [],
  shownKey: null,     // filtre, ku ktorým patria zobrazené výsledky (null = nič nezobrazené)
  apiStatus: null,    // null = neoverené, 'ok' = odpovedalo, 'down' = neodpovedalo
};

/* ---------- Pomocné funkcie ---------- */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...children);
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
const fmtTime = new Intl.DateTimeFormat('sk-SK', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const fmtDate = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'numeric', year: 'numeric' });
const fmtSeconds = (ms) => (ms / 1000).toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtScore = (s) => s.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function relativeDay(date) {
  const start = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((start(new Date()) - start(date)) / (24 * HOUR));
  if (diff === 0) return 'dnes';
  if (diff === 1) return 'včera';
  return fmtDate.format(date);
}
// Čas záznamu: ISO dátum a čas, alebo iba „HH:MM:SS“ (tak ho dnes ukladá ReID pipeline, bez dátumu).
function when(value) {
  if (!value) return { time: '—', day: 'čas neznámy', iso: null };
  const clock = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(String(value).trim());
  if (clock) {
    const [, h, m, sec = '00'] = clock;
    return { time: `${h.padStart(2, '0')}:${m}:${sec}`, day: 'dátum neznámy', iso: null };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { time: '—', day: 'čas neznámy', iso: null };
  return { time: fmtTime.format(date), day: relativeDay(date), iso: date.toISOString() };
}
function apiBase() {
  return ($('api-url').value || '').trim().replace(/\/+$/, '');
}
function isDemo() { return !apiBase(); }
function announce(message) { $('status').textContent = message; }

/* ---------- Režim (ukážka / API) ---------- */
// „API odpovedá“ ukážeme až po platnej odpovedi; dovtedy je to len zvolený režim.
function updateMode() {
  const pill = $('mode-pill');
  const demo = isDemo();
  const s = state.apiStatus;
  pill.dataset.mode = demo ? 'demo' : s === 'ok' ? 'api' : s === 'down' ? 'down' : 'pending';
  $('mode-label').textContent = demo ? 'Ukážkové dáta' : s === 'ok' ? 'API odpovedá' : s === 'down' ? 'API nedostupné' : 'Režim API';
  pill.title = demo ? 'Výsledky sú pevné ukážkové záznamy.'
    : s === 'ok' ? `${apiBase()} pri poslednom hľadaní vrátilo platnú odpoveď.`
    : s === 'down' ? `${apiBase()} pri poslednom hľadaní neodpovedalo.`
    : `${apiBase()} – spojenie sa overí pri prvom vyhľadávaní.`;
  $('simulate-error').disabled = !demo;
}
function setApiStatus(value) {
  if (isDemo() || state.apiStatus === value) return;
  state.apiStatus = value;
  updateMode();
}

/* ---------- Filtre ---------- */
// Kamier je veľa (41), preto sa filtruje podľa častí mesta. Z mapy sa dá prísť s jednou kamerou (?camera=msp-5).
const AREAS = [...new Set(CAMERAS.map((c) => c.area ?? 'Ostatné'))];
let onlyCamera = null;

function readFilters() {
  const range = document.querySelector('input[name="range"]:checked').value;
  const areas = new Set([...document.querySelectorAll('#camera-list input:checked')].map((i) => i.value));
  const cameras = onlyCamera
    ? [onlyCamera]
    : CAMERAS.filter((c) => areas.has(c.area ?? 'Ostatné')).map((c) => c.id);
  const now = new Date();
  let from = null;
  if (range === '24h') from = new Date(now - 24 * HOUR);
  if (range === '7d') from = new Date(now - 7 * 24 * HOUR);
  if (range === 'today') from = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return { range, from, cameras, areas: [...areas], allCameras: !onlyCamera && cameras.length === CAMERAS.length };
}
function renderOnlyCamera() {
  const box = $('only-camera');
  const cam = CAMERAS.find((c) => c.id === onlyCamera);
  box.hidden = !cam;
  for (const i of document.querySelectorAll('#camera-list input')) i.disabled = Boolean(cam);
  if (!cam) return;
  box.replaceChildren(
    el('span', {}, icon('camera'), el('span', { text: cam.name })),
    el('button', { type: 'button', class: 'icon-button', 'aria-label': 'Hľadať na všetkých kamerách', title: 'Hľadať na všetkých kamerách', onclick: () => { onlyCamera = null; renderOnlyCamera(); onFiltersChanged(); } }, icon('close')));
}
const filterKey = (f) => `${f.range}|${[...f.cameras].sort().join(',')}`;

// Výsledky musia vždy zodpovedať filtrom: rozbehnuté hľadanie sa spustí znova s novými filtrami,
// hotové výsledky sa označia ako neaktuálne (návrat k pôvodným filtrom označenie zruší).
function onFiltersChanged() {
  updateFilterSummary();
  const filters = readFilters();
  if (state.busy) {
    cancelPending();
    if (filters.cameras.length) runSearch();
    else showIdle(Boolean(state.query), 'Vyberte aspoň jednu časť mesta.');
    return;
  }
  markStale(state.shownKey !== null && filterKey(filters) !== state.shownKey);
}
function markStale(stale) {
  $('stale-note').hidden = !stale;
  $('result-list').classList.toggle('is-stale', stale);
  $('state-message').classList.toggle('is-stale', stale);
}
function updateFilterSummary() {
  const f = readFilters();
  const rangeText = document.querySelector('input[name="range"]:checked + span').textContent.toLowerCase();
  const camText = onlyCamera
    ? cameraName(onlyCamera)
    : f.allCameras ? 'všetky kamery' : f.cameras.length === 0 ? 'žiadna kamera' : `${f.cameras.length} z ${CAMERAS.length} kamier`;
  const text = `${camText}, ${f.range === 'all' ? 'kedykoľvek' : rangeText}`;
  $('filter-summary').textContent = text.charAt(0).toUpperCase() + text.slice(1);
  refreshSearchButton();
}

/* ---------- Výber fotografie ---------- */
function revokePreview() {
  if (state.objectUrl) { URL.revokeObjectURL(state.objectUrl); state.objectUrl = null; }
}
function uploadError(message = '') {
  $('upload-error').textContent = message;
  $('upload-error').hidden = !message;
}
function refreshSearchButton() {
  const noCamera = readFilters().cameras.length === 0;
  $('search-button').disabled = state.busy || state.validating || !state.query || noCamera;
  $('search-label').textContent = state.busy ? 'Vyhľadávam…' : 'Vyhľadať vozidlo';
}
function markGallery(demoId) {
  for (const btn of document.querySelectorAll('.gallery-item')) {
    btn.setAttribute('aria-pressed', String(btn.dataset.id === demoId));
  }
}
function showQuery(query) {
  state.query = query;
  $('query-image').src = query.url;
  $('query-image').alt = `Hľadané vozidlo – ${query.name}`;
  $('query-image').hidden = false;
  $('upload-prompt').hidden = true;
  $('drop-zone').classList.add('has-image');
  $('file-row').hidden = false;
  $('file-name').textContent = query.name;
  markGallery(query.demoId ?? null);
  refreshSearchButton();
}
function clearQueryView() {
  $('query-image').hidden = true;
  $('query-image').removeAttribute('src');
  $('upload-prompt').hidden = false;
  $('drop-zone').classList.remove('has-image');
  $('file-row').hidden = true;
  markGallery(null);
}
function cancelPending() {
  state.generation += 1;
  state.controller?.abort();
  state.controller = null;
  setBusy(false);
}
function resetQuery() {
  cancelPending();
  state.fileToken += 1;
  state.validating = false;
  revokePreview();
  state.query = null;
  $('file').value = '';
  clearQueryView();
  uploadError();
  showIdle();
  refreshSearchButton();
}

// Nový súbor najprv overíme. Pôvodná fotografia, jej výsledky aj rozbehnuté hľadanie zostanú,
// kým nie je isté, že nový súbor je použiteľný – odmietnutý súbor teda nič nepokazí.
async function acceptFile(file) {
  const token = ++state.fileToken;
  uploadError();
  const fail = (message) => {
    if (token !== state.fileToken) return;
    state.validating = false;
    $('file').value = '';
    uploadError(state.query ? `${message} Ponechali sme pôvodnú fotografiu.` : message);
    refreshSearchButton();
  };
  if (!file) return fail('Vyberte jednu fotografiu.');
  const typeOk = CONFIG.types.includes(file.type) || (!file.type && /\.(jpe?g|png|webp)$/i.test(file.name));
  if (!typeOk) return fail('Tento formát nepodporujeme. Použite fotografiu JPG, PNG alebo WebP.');
  if (!file.size) return fail('Súbor je prázdny. Vyberte inú fotografiu.');
  if (file.size > CONFIG.maxBytes) return fail('Fotografia má viac ako 10 MB. Zmenšite ju alebo vyberte inú.');

  state.validating = true;
  refreshSearchButton();
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    if (token !== state.fileToken) { URL.revokeObjectURL(url); return; }
    if (!img.naturalWidth) throw new Error('empty image');
    cancelPending();
    revokePreview();
    state.objectUrl = url;
    state.validating = false;
    $('file').value = '';
    showQuery({ name: file.name, url, file });
    showIdle(true);
  } catch {
    URL.revokeObjectURL(url);
    fail('Súbor sa nedá otvoriť ako obrázok. Vyberte inú fotografiu.');
  }
}

function chooseDemo(item) {
  cancelPending();
  state.fileToken += 1;
  state.validating = false;
  revokePreview();
  $('file').value = '';
  uploadError();
  showQuery({ name: item.label, url: item.image, demoId: item.id });
  showIdle(true);
}

/* ---------- Stavy panela výsledkov ---------- */
function setBusy(value) {
  state.busy = value;
  document.querySelector('.results').setAttribute('aria-busy', String(value));
  $('drop-zone').classList.toggle('is-scanning', value);
  $('file').disabled = value;
  refreshSearchButton();
}
function hideAllStates() {
  for (const id of ['state-idle', 'skeleton', 'state-message', 'result-list', 'result-note', 'timing']) $(id).hidden = true;
  state.shownKey = null;
  markStale(false);
}
function showIdle(hasQuery = false, sub = null) {
  hideAllStates();
  $('state-idle').hidden = false;
  $('try-button').hidden = hasQuery;
  $('results-sub').textContent = sub ?? (hasQuery ? 'Fotografia je pripravená. Spustite vyhľadávanie.' : 'Zatiaľ ste nič nehľadali.');
  $('results-title').textContent = 'Výsledky';
}
function showMessage({ title, text, action, onAction, error = false }) {
  hideAllStates();
  $('state-message').hidden = false;
  $('state-message').classList.toggle('is-error', error);
  $('message-title').textContent = title;
  $('message-text').textContent = text;
  const btn = $('message-action');
  btn.textContent = action;
  btn.onclick = onAction;
}
function showTiming(ms, demo, missing = 0) {
  const chip = $('timing');
  const slow = ms > CONFIG.targetMs;
  const missingText = missing ? ` · ${missing === 1 ? '1 záber chýba' : `${missing} zábery chýbajú`}` : '';
  chip.replaceChildren(icon('clock'), document.createTextNode(`${fmtSeconds(ms)} s${demo ? ' · simulácia' : ''}${missingText}`));
  chip.classList.toggle('is-slow', slow || missing > 0);
  chip.title = missing
    ? `Čas nezahŕňa ${missing === 1 ? 'záber, ktorý sa nenačítal' : 'zábery, ktoré sa nenačítali'} – meranie nie je úplné.`
    : slow
      ? `Nad cieľom ${CONFIG.targetMs / 1000} s (od odoslania po načítanie obrázkov).`
      : `V rámci cieľa ${CONFIG.targetMs / 1000} s (od odoslania po načítanie obrázkov).`;
  chip.hidden = false;
}

/* ---------- Vyhľadávanie ---------- */
class SearchError extends Error {
  constructor(kind, message) { super(message); this.kind = kind; }
}

async function searchDemo(query, filters, signal) {
  await new Promise((resolve, reject) => {
    const t = setTimeout(resolve, CONFIG.demoLatencyMs);
    signal.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('aborted', 'AbortError')); });
  });
  if ($('simulate-error').checked) throw new SearchError('server', 'Server vrátil chybu 503.');
  // Vlastná fotografia sa v ukážke neanalyzuje – použije sa prvá sada.
  const set = DEMO.find((d) => d.id === query.demoId) ?? DEMO[0];
  return set.results
    .filter((r) => filters.cameras.includes(r.camera))
    .filter((r) => !filters.from || new Date(r.time) >= filters.from)
    .map((r) => ({ ...r, cameraLabel: cameraName(r.camera) }));
}

async function searchApi(query, filters, signal) {
  let blob = query.file;
  if (!blob) {
    const res = await fetch(query.url, { signal });
    if (!res.ok) throw new SearchError('request', 'Ukážkovú fotografiu sa nepodarilo načítať.');
    blob = await res.blob();
  }
  const form = new FormData();
  form.append('image', blob, query.file?.name ?? 'query.jpg');
  form.append('top_k', String(CONFIG.topK));
  if (!filters.allCameras) for (const c of filters.cameras) form.append('camera', c);
  if (filters.from) form.append('from', filters.from.toISOString());

  const base = apiBase();
  let res;
  try {
    res = await fetch(`${base}/api/search`, { method: 'POST', body: form, signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    setApiStatus('down');
    throw new SearchError('network', `Server ${base} neodpovedá alebo nepovolil prístup (CORS).`);
  }
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail ?? j.message).catch(() => null);
    throw new SearchError(res.status >= 500 ? 'server' : 'request', `Server vrátil chybu ${res.status}${detail ? `: ${detail}` : ''}.`);
  }
  const data = await res.json().catch(() => { throw new SearchError('contract', 'Odpoveď servera nie je platný JSON.'); });
  // Prázdny zoznam je „bez zhody“. Odpoveď bez zoznamu je chyba – inak by sme hlásili, že sa vozidlo nenašlo.
  const list = Array.isArray(data) ? data
    : Array.isArray(data?.results) ? data.results
    : Array.isArray(data?.matches) ? data.matches
    : null;
  if (!list) throw new SearchError('contract', 'V odpovedi servera chýba zoznam výsledkov („results“).');
  list.forEach((r, i) => {
    if (!r || typeof r !== 'object' || Array.isArray(r)) throw new SearchError('contract', `Výsledok ${i + 1} v odpovedi servera nie je objekt.`);
    if (r.score != null && typeof r.score !== 'number') throw new SearchError('contract', `Výsledok ${i + 1} má skóre, ktoré nie je číslo.`);
  });
  setApiStatus('ok');
  const absolute = (u) => (u ? new URL(u, `${base}/`).href : '');
  const mapped = list.map((r, i) => {
    const payload = r.payload ?? {};
    const camera = r.camera ?? r.camera_id ?? payload.camera ?? payload.camera_id;
    return {
      // ReID pipeline (rd-research/02): jedno auto = original_id, každý pohľad (slot) je samostatný bod v Qdrante.
      vehicle: r.original_id ?? payload.original_id ?? null,
      id: String(r.original_id ?? payload.original_id ?? r.id ?? payload.id ?? i + 1),
      // frame_path / best_frame_path sú relatívne cesty (frames/…), API ich musí servírovať ako statické súbory.
      image: absolute(r.image_url ?? r.image ?? payload.image_url ?? payload.frame_url ?? payload.crop_url
        ?? payload.frame_path ?? payload.best_frame_path ?? payload.reid_crop_path),
      time: r.timestamp ?? r.time ?? payload.timestamp ?? null,
      camera,
      cameraLabel: r.camera_name ?? payload.camera_name ?? cameraName(camera),
      score: typeof r.score === 'number' ? r.score : null,
    };
  });
  // To isté auto môže prísť viackrát (spredu, zboku, zozadu) – necháme jeho najlepší pohľad.
  // Zhoda platí, ak sedí aspoň jeden pohľad (max-pooling z R&D 02).
  const best = new Map();
  for (const r of mapped) {
    const key = r.vehicle ?? `#${r.id}`;
    const prev = best.get(key);
    if (!prev || (r.score ?? -Infinity) > (prev.score ?? -Infinity)) best.set(key, r);
  }
  return [...best.values()]
    .sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity))
    .slice(0, CONFIG.topK);
}

// 'ok' = načítaný, 'missing' = server neposlal adresu, 'error' = obrázok sa nedá načítať.
// Zrušenie (aj timeout) nie je úspech – promise skončí chybou AbortError.
function loadImage(src, signal) {
  return new Promise((resolve, reject) => {
    if (!src) return resolve('missing');
    const aborted = () => new DOMException('aborted', 'AbortError');
    if (signal.aborted) return reject(aborted());
    const img = new Image();
    const onAbort = () => { img.onload = img.onerror = null; img.removeAttribute('src'); reject(aborted()); };
    const settle = (status) => () => { signal.removeEventListener('abort', onAbort); resolve(status); };
    img.onload = settle('ok');
    img.onerror = settle('error');
    signal.addEventListener('abort', onAbort, { once: true });
    img.src = src;
  });
}

async function runSearch() {
  if (!state.query || state.busy || state.validating) return;
  const filters = readFilters();
  if (!filters.cameras.length) return;
  cancelPending();
  const current = state.generation;
  const controller = new AbortController();
  state.controller = controller;
  const timeout = setTimeout(() => controller.abort('timeout'), CONFIG.requestTimeoutMs);
  const demo = isDemo();
  let phase = 'request';

  hideAllStates();
  $('skeleton').hidden = false;
  $('results-title').textContent = 'Vyhľadávam…';
  $('results-sub').textContent = demo ? 'Ukážkové dáta – fotografia sa nikam neposiela.' : `Posielam fotografiu na ${apiBase()}.`;
  announce('Vyhľadávam podobné vozidlá.');
  setBusy(true);
  const started = performance.now();

  try {
    const results = demo
      ? await searchDemo(state.query, filters, controller.signal)
      : await searchApi(state.query, filters, controller.signal);
    // Meriame až po načítanie obrázkov – to je čas, ktorý vidí používateľ.
    phase = 'images';
    const statuses = await Promise.all(results.map((r) => loadImage(r.image, controller.signal)));
    if (current !== state.generation) return;
    results.forEach((r, i) => { r.imageStatus = statuses[i]; });
    const elapsed = performance.now() - started;
    setBusy(false);
    renderResults(results, filters, elapsed, demo);
  } catch (err) {
    if (current !== state.generation) return;
    setBusy(false);
    const timedOut = controller.signal.reason === 'timeout';
    if (err.name === 'AbortError' && !timedOut) return;
    if (timedOut && phase === 'request') setApiStatus('down');
    const seconds = (CONFIG.requestTimeoutMs / 1000).toLocaleString('sk-SK');
    const message = timedOut && phase === 'images'
      ? { title: 'Zábery sa nenačítali včas', text: `Server našiel výsledky, ale ich obrázky sa nenačítali do ${seconds} s. Skontrolujte, či sú adresy obrázkov dostupné.` }
      : timedOut
        ? { title: 'Server neodpovedal včas', text: `Odpoveď neprišla do ${seconds} s. Skontrolujte, či API beží, a skúste to znova.` }
        : err.kind === 'contract'
          ? { title: 'Odpoveď servera sa nedá spracovať', text: `${err.message} Nejde o výsledok „bez zhody“ – vozidlo sa nehľadalo správne. Treba skontrolovať kontrakt API.` }
          : { title: 'Vyhľadávanie sa nepodarilo', text: `${err.message ?? 'Neznáma chyba.'} Skúste vyhľadávanie zopakovať.` };
    showMessage({ error: true, ...message, action: 'Skúsiť znova', onAction: runSearch });
    $('results-title').textContent = 'Výsledky';
    $('results-sub').textContent = 'Posledné vyhľadávanie skončilo chybou.';
    announce('Vyhľadávanie sa nepodarilo.');
  } finally {
    clearTimeout(timeout);
    if (state.controller === controller) state.controller = null;
  }
}

function renderResults(results, filters, elapsed, demo) {
  state.lastResults = results;
  const missing = results.filter((r) => r.imageStatus !== 'ok').length;
  if (!results.length) {
    const narrowed = filters.range !== 'all' || !filters.allCameras;
    showMessage({
      title: 'Žiadne podobné vozidlo',
      text: narrowed
        ? 'Vo vybranom období a na vybraných kamerách sa nič nenašlo. Skúste rozšíriť filtre.'
        : 'V databáze sa nenašiel podobný záznam. Skúste ostrejší záber vozidla.',
      action: narrowed ? 'Zrušiť filtre a hľadať znova' : 'Vybrať inú fotografiu',
      onAction: narrowed ? () => { resetFilters(); runSearch(); } : () => $('file').click(),
    });
    showTiming(elapsed, demo);
    $('results-title').textContent = 'Bez zhody';
    $('results-sub').textContent = '0 záznamov';
    state.shownKey = filterKey(filters);
    announce('Nenašli sa žiadne podobné vozidlá.');
    return;
  }

  const list = $('result-list');
  list.replaceChildren(...results.map((r, i) => resultCard(r, i)));
  hideAllStates();
  showTiming(elapsed, demo, missing);
  list.hidden = false;
  state.shownKey = filterKey(filters);
  const n = results.length;
  $('results-title').textContent = n === 1 ? 'Najbližšia zhoda' : `${n} najbližšie zhody`;
  $('results-sub').textContent = 'Zoradené podľa skóre podobnosti od modelu (0–1). Skóre nie je pravdepodobnosť, že ide o to isté vozidlo.';
  if (demo) {
    $('result-note').textContent = state.query.demoId
      ? 'Ukážkové dáta: zábery sú z projektového datasetu (nie z kamier Pezinka). V každej ukážkovej sade je jeden záber toho istého vozidla z iného miesta. Priradenie ku kamerám, čas a podobnosť sú vymyslené.'
      : 'Ukážkové dáta: vlastná fotografia sa neanalyzuje, zobrazujú sa pevné výsledky. Na skutočné hľadanie zadajte adresu API v paneli Pre vývojárov.';
    $('result-note').hidden = false;
  }
  announce(`Hotovo. ${n === 1 ? 'Našiel sa 1 záznam' : `Našli sa ${n} záznamy`}${missing ? `, ${missing} bez záberu` : ''}.`);
}

function resultCard(r, index) {
  const w = when(r.time);
  const hasImage = r.imageStatus === 'ok';
  const rank = el('span', { class: 'rank', text: String(index + 1), 'aria-hidden': 'true' });
  const media = hasImage
    ? el('button', { type: 'button', class: 'result-media', 'aria-label': `Porovnať záznam ${index + 1} s hľadaným vozidlom`, onclick: () => openCompare(r, index) },
      el('img', { src: r.image, alt: `Záznam ${index + 1}, ${r.cameraLabel}` }), rank)
    : el('div', { class: 'result-media is-missing' }, rank,
      el('span', { class: 'media-missing' }, icon('alert'),
        el('span', { text: r.imageStatus === 'missing' ? 'Server neposlal záber' : 'Záber sa nepodarilo načítať' })));

  const time = el('p', { class: 'result-time' },
    el('time', { ...(w.iso ? { datetime: w.iso } : {}), text: w.time }),
    el('span', { class: 'result-date', text: w.day }));
  const camera = el('p', { class: 'result-camera' }, icon('camera'), el('span', { text: r.cameraLabel }));
  const body = el('div', { class: 'result-body' }, time, camera);

  if (typeof r.score === 'number') {
    const pct = Math.max(0, Math.min(1, r.score)) * 100;
    const bar = el('span', { class: 'score-bar' }, el('i', { style: `width:${pct.toFixed(0)}%` }));
    body.append(el('div', { class: 'score', title: 'Skóre modelu: kosínusová podobnosť embeddingov (0–1). Vyššie = podobnejší záber, nie pravdepodobnosť zhody.' },
      el('span', { text: 'Skóre podobnosti' }), bar, el('b', { text: fmtScore(r.score) })));
  }
  if (hasImage) body.append(el('button', { type: 'button', class: 'compare-button', onclick: () => openCompare(r, index) }, icon('compare'), el('span', { text: 'Porovnať so záberom' })));
  return el('li', { class: 'result' }, media, body);
}

/* ---------- Porovnanie ---------- */
function openCompare(r, index) {
  if (!state.query) return;
  const w = when(r.time);
  $('compare-title').textContent = `Porovnanie so záznamom ${index + 1}`;
  $('compare-query').src = state.query.url;
  $('compare-query').alt = 'Hľadané vozidlo';
  $('compare-record').src = r.image;
  $('compare-record').alt = `Záznam ${index + 1} z kamery ${r.cameraLabel}`;
  $('compare-record-caption').textContent = `Záznam ${index + 1}`;
  const rows = [
    ['Čas', w.time === '—' ? '—' : `${w.time}, ${w.day}`],
    ['Kamera', r.cameraLabel],
    ['Skóre podobnosti', typeof r.score === 'number' ? `${fmtScore(r.score)} (skóre modelu, nie pravdepodobnosť)` : '—'],
    ['ID záznamu', r.id],
  ];
  $('compare-meta').replaceChildren(...rows.flatMap(([k, v]) => [el('div', {}, el('dt', { text: k }), el('dd', { text: v }))]));
  $('compare').showModal();
}

/* ---------- Inicializácia ---------- */
function resetFilters() {
  document.querySelector('input[name="range"][value="all"]').checked = true;
  for (const i of document.querySelectorAll('#camera-list input')) i.checked = true;
  onlyCamera = null;
  renderOnlyCamera();
  updateFilterSummary();
}

function init() {
  $('gallery').replaceChildren(...DEMO.map((item) =>
    el('button', { type: 'button', class: 'gallery-item', 'data-id': item.id, 'aria-pressed': 'false', 'aria-label': item.label, title: item.label, onclick: () => chooseDemo(item) },
      el('img', { src: item.image, alt: '' }))));

  $('camera-list').replaceChildren(...AREAS.map((area) => {
    const count = CAMERAS.filter((c) => (c.area ?? 'Ostatné') === area).length;
    return el('label', { class: 'check' }, el('input', { type: 'checkbox', value: area, checked: '' }),
      el('span', { text: area }), el('span', { class: 'check-count', text: String(count) }));
  }));

  // Adresa API: ?api=… má prednosť, inak posledná uložená hodnota.
  const fromUrl = new URLSearchParams(location.search).get('api');
  let saved = '';
  try { saved = localStorage.getItem(CONFIG.storageKey) ?? ''; } catch { /* súkromné okno */ }
  $('api-url').value = fromUrl ?? saved;
  $('api-url').addEventListener('change', () => {
    try { localStorage.setItem(CONFIG.storageKey, apiBase()); } catch { /* ignore */ }
    cancelPending();
    state.apiStatus = null;
    updateMode();
    showIdle(Boolean(state.query));
  });
  updateMode();

  $('file').addEventListener('change', (e) => { if (e.target.files.length) acceptFile(e.target.files[0]); });
  $('remove').addEventListener('click', resetQuery);
  $('try-button').addEventListener('click', () => { chooseDemo(DEMO[0]); runSearch(); });
  $('query-form').addEventListener('submit', (e) => { e.preventDefault(); runSearch(); });
  $('query-form').addEventListener('change', (e) => { if (e.target.closest('#filters')) onFiltersChanged(); });
  $('stale-rerun').addEventListener('click', runSearch);
  $('close-compare').addEventListener('click', () => $('compare').close());
  $('compare').addEventListener('click', (e) => {
    // Klik na pozadie mimo okna zatvorí porovnanie.
    const b = $('compare').getBoundingClientRect();
    if (e.target === $('compare') && (e.clientX < b.left || e.clientX > b.right || e.clientY < b.top || e.clientY > b.bottom)) $('compare').close();
  });

  const drop = $('drop-zone');
  for (const type of ['dragenter', 'dragover']) drop.addEventListener(type, (e) => { e.preventDefault(); drop.classList.add('is-dragging'); });
  for (const type of ['dragleave', 'drop']) drop.addEventListener(type, (e) => { e.preventDefault(); drop.classList.remove('is-dragging'); });
  drop.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length !== 1) { uploadError('Presuňte naraz iba jednu fotografiu.'); return; }
    acceptFile(files[0]);
  });
  window.addEventListener('pagehide', revokePreview);

  // Príchod z mapy: ?camera=msp-5 zúži hľadanie na jednu kameru.
  const fromMap = new URLSearchParams(location.search).get('camera');
  if (fromMap && CAMERAS.some((c) => c.id === fromMap)) {
    onlyCamera = fromMap;
    $('filters').open = true;
  }
  renderOnlyCamera();

  updateFilterSummary();
  showIdle(false);
}

init();
