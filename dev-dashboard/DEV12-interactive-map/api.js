'use strict';
/*
 * Načítanie kamier a parkovísk pre mapu (DEV12).
 *
 * 1. FlowSight API (DEV11): /api/cameras, /api/parking – súradnice sú z config/*.yaml, k tomu stav a obsadenosť.
 *    Keď stránku servíruje samotné API (…/dashboard/…), adresa sa zistí sama; inak ?api=http://… (zapamätá sa).
 * 2. Keď API nebeží: priamo tie isté konfiguračné súbory DEV11 (bez stavu kamier a obsadenosti).
 */
(function () {
  const STORAGE_KEY = 'flowsight.apiUrl';
  const CONFIG_DIR = '../DEV11-FastAPI-server/config/';

  function resolveBase() {
    const fromUrl = new URLSearchParams(location.search).get('api');
    if (fromUrl) {
      try { localStorage.setItem(STORAGE_KEY, fromUrl); } catch { /* súkromné okno */ }
      return fromUrl.replace(/\/+$/, '');
    }
    if (location.protocol.startsWith('http') && location.pathname.startsWith('/dashboard/')) return location.origin;
    try { const saved = localStorage.getItem(STORAGE_KEY); if (saved) return saved.replace(/\/+$/, ''); } catch { /* ignore */ }
    return 'http://127.0.0.1:8000';
  }
  const base = resolveBase();

  async function getJson(path, timeout = 6000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(`${base}${path}`, { signal: ctrl.signal, headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function readYaml(file, key) {
    if (!window.jsyaml) throw new Error('js-yaml sa nenačítal');
    const res = await fetch(CONFIG_DIR + file);
    if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
    return window.jsyaml.load(await res.text())?.[key] ?? [];
  }

  /** Kamery z API, inak z config/cameras.yaml. Vráti { items, live }. */
  async function cameras() {
    try { return { items: (await getJson('/api/cameras')).cameras, live: true }; }
    catch { return { items: await readYaml('cameras.yaml', 'cameras'), live: false }; }
  }
  /** Parkoviská z API, inak z config/parking.yaml. Vráti { items, live, updatedAt }. */
  async function parking() {
    try {
      const r = await getJson('/api/parking');
      return { items: r.parking, live: true, updatedAt: r.updated_at };
    } catch { return { items: await readYaml('parking.yaml', 'parking'), live: false, updatedAt: null }; }
  }

  window.FlowSightAPI = {
    base,
    getJson,
    cameras,
    parking,
    live: false,
    searchUrl(cameraId) {
      const q = new URLSearchParams();
      if (cameraId) q.set('camera', cameraId);
      if (this.live) q.set('api', base);
      return `../DEV13-db-search-frontend/index.html?${q}`;
    },
  };
})();
