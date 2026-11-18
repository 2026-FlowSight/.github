"""FlowSight API (DEV11).

Spustenie (z priečinka DEV11-FastAPI-server):
    uvicorn app.main:app --reload --port 8000
Swagger: http://127.0.0.1:8000/docs   ·   Mapa (DEV12): http://127.0.0.1:8000/dashboard/DEV12-interactive-map/mapa.html
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import mock
from .config import ROOT, get_settings, load_cameras, load_parking
from .embedder import EmbedError, embedder
from .schemas import CamerasResponse, ParkingResponse, SearchResponse, StatsResponse
from .store import QdrantStore, StoreUnavailable

log = logging.getLogger("flowsight")
settings = get_settings()
store = QdrantStore(settings)

TAGS = [
    {"name": "Mapa", "description": "Kamery a parkoviská so súradnicami pre mapu (DEV12)."},
    {"name": "Štatistiky", "description": "Čísla pre kartičky a grafy dashboardu."},
    {"name": "Vyhľadávanie", "description": "Hľadanie vozidla podľa fotky v Qdrante (DEV13)."},
    {"name": "Systém", "description": "Stav API a databázy."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    st = store.status()
    if st["ok"]:
        log.info("Qdrant OK (%s): %s", st["target"], st["collections"])
    else:
        log.warning("Qdrant nedostupný – štatistiky pôjdu z mock dát. %s", st["error"])
    yield
    store.close()


app = FastAPI(
    title="FlowSight API",
    version="0.1.0",
    summary="Most medzi Qdrant databázou a dashboardom mesta Pezinok (DEV11).",
    description=(
        "Kamery a parkoviská sa čítajú z konfiguračných súborov `config/*.yaml`, vozidlá a štatistiky z Qdrantu.\n\n"
        "Čo je zatiaľ **mock** (v odpovedi je to vždy uvedené v poli `source`): stav kamier (čaká na Milestone/Axis), "
        "obsadenosť parkovísk (čaká na DEV03). Prevod fotky na vektor je **placeholder** do DEV16 (farebný histogram)."
    ),
    openapi_tags=TAGS,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

# Zábery z Qdrantu (frame_path = "frames/xxx.jpg") → /media/frames/xxx.jpg
if settings.media_dir and settings.media_dir.exists():
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
# Celý dev-dashboard (mapa DEV12, vyhľadávanie DEV13) z tej istej adresy → netreba riešiť CORS ani druhý server
DASHBOARD_DIR = ROOT.parent
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")


# ---------- pomocné ----------
def now() -> datetime:
    return datetime.now(settings.timezone)


def camera_names() -> dict[str, str]:
    return {c["id"]: c["name"] for c in load_cameras()}


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/")):
        return path
    return f"/media/{Path(path).as_posix().lstrip('./')}"


def parse_since(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(422, f"Parameter `from` nie je ISO dátum a čas: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=settings.timezone)
    return dt.timestamp()


def data_anchor() -> datetime:
    """Ku ktorému času počítame „dnes“: posledný záznam v DB (pri živej pipeline = teraz, pri demo DB čas seedovania)."""
    t = now()
    latest = store.latest_ts()
    return t if latest is None or latest >= t.timestamp() else datetime.fromtimestamp(latest, settings.timezone)


def today_counts_by_camera() -> tuple[dict[str, int], bool]:
    """Prejazdy dnes podľa kamery. Druhá hodnota = či sú dáta z Qdrantu."""
    if not store.available():
        return {}, False
    anchor = data_anchor()
    start = anchor.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    counts: dict[str, int] = {}
    for s in store.sightings(start):
        if s.camera and s.ts <= anchor.timestamp():
            counts[s.camera] = counts.get(s.camera, 0) + 1
    return counts, True


def level_of(ratio: float) -> str:
    return "free" if ratio < 0.6 else "busy" if ratio < 0.85 else "full"


def parking_snapshot(at: datetime) -> list[dict]:
    lots = []
    for lot in load_parking():
        occ = mock.parking_occupancy(lot, at)
        ratio = occ / lot["capacity"]
        lots.append({**lot, "occupied": occ, "free": lot["capacity"] - occ, "ratio": round(ratio, 3), "level": level_of(ratio)})
    return lots


def parking_summary(lots: list[dict]) -> dict:
    cap = sum(l["capacity"] for l in lots)
    occ = sum(l["occupied"] for l in lots)
    levels = {}
    for lvl in ("free", "busy", "full"):
        sel = [l for l in lots if l["level"] == lvl]
        spaces = sum(l["capacity"] for l in sel)
        levels[lvl] = {"lots": len(sel), "spaces": spaces, "share": round(spaces / cap, 3) if cap else 0}
    return {"lots": len(lots), "capacity": cap, "occupied": occ, "free": cap - occ,
            "ratio": round(occ / cap, 3) if cap else 0, "levels": levels}


# ---------- endpointy ----------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/api/health", tags=["Systém"], summary="Beží API? Je dostupný Qdrant?")
def health():
    return {
        "status": "ok",
        "time": now().isoformat(timespec="seconds"),
        "qdrant": store.status(),
        "config": {"cameras": len(load_cameras()), "parking": len(load_parking())},
        "embedder": embedder.name,
    }


@app.get("/api/cameras", response_model=CamerasResponse, tags=["Mapa"],
         summary="Zoznam kamier s GPS súradnicami")
def list_cameras(
    status: Annotated[str | None, Query(description="Filter podľa stavu: online / warning / offline")] = None,
    area: Annotated[str | None, Query(description="Filter podľa časti mesta, napr. Centrum")] = None,
):
    """Kamery sú z `config/cameras.yaml`, počet áut dnes z Qdrantu, stav kamery je zatiaľ mock."""
    counts, from_qdrant = today_counts_by_camera()
    cams = []
    for c in load_cameras():
        st, note = mock.camera_status(c["id"])
        cams.append({**c, "status": st, "status_note": note, "vehicles_today": counts.get(c["id"], 0)})
    summary = {k: sum(1 for c in cams if c["status"] == k) for k in ("online", "warning", "offline")}
    if status:
        cams = [c for c in cams if c["status"] == status]
    if area:
        cams = [c for c in cams if (c.get("area") or "").lower() == area.lower()]
    return {
        "count": len(cams),
        "summary": summary,
        "source": {"cameras": "config", "status": "mock", "vehicles_today": "qdrant" if from_qdrant else "mock"},
        "cameras": cams,
    }


@app.get("/api/cameras/{camera_id}", tags=["Mapa"], summary="Detail jednej kamery")
def get_camera(camera_id: str):
    for c in list_cameras()["cameras"]:
        if c["id"] == camera_id:
            return c
    raise HTTPException(404, f"Kamera {camera_id} neexistuje (pozri config/cameras.yaml).")


@app.get("/api/parking", response_model=ParkingResponse, tags=["Mapa"],
         summary="Parkoviská s GPS súradnicami a obsadenosťou")
def list_parking():
    """Polohy a kapacity sú z `config/parking.yaml`. Obsadenosť je mock (mení sa podľa dennej doby) do DEV03."""
    t = now()
    lots = parking_snapshot(t)
    return {"updated_at": t.isoformat(timespec="seconds"), "source": {"parking": "config", "occupancy": "mock"},
            "summary": parking_summary(lots), "parking": lots}


@app.get("/api/stats", response_model=StatsResponse, tags=["Štatistiky"],
         summary="Koľko áut sme dnes videli – čísla pre grafy")
def stats():
    """Prejazdy áut z Qdrantu (kolekcia `vehicles_reid`): dnes, za poslednú hodinu, po hodinách a po kamerách.

    Čísla sa počítajú ku času posledného záznamu v DB (pole `as_of`) – pri živej pipeline je to „teraz“,
    pri demo databáze čas, kedy bola naplnená."""
    t = now()
    cams = load_cameras()
    names = {c["id"]: c["name"] for c in cams}
    status_counts = {k: 0 for k in ("online", "warning", "offline")}
    for c in cams:
        status_counts[mock.camera_status(c["id"])[0]] += 1
    lots = parking_snapshot(t)

    hour0 = t.replace(minute=0, second=0, microsecond=0)
    if store.available():
        anchor = data_anchor()
        hour0 = anchor.replace(minute=0, second=0, microsecond=0)
        a = anchor.timestamp()
        day0 = anchor.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        rows = store.sightings(min(day0 - 86400, a - 48 * 3600))

        def count(lo: float, hi: float) -> int:
            return sum(1 for s in rows if lo <= s.ts < hi)

        today_rows = [s for s in rows if day0 <= s.ts <= a]
        detections = len(today_rows)
        yesterday = count(day0 - 86400, a - 86400)
        last_hour, prev_hour = count(a - 3600, a + 1), count(a - 7200, a - 3600)
        starts = [hour0 - timedelta(hours=23 - i) for i in range(24)]
        hourly = [count(s.timestamp(), (s + timedelta(hours=1)).timestamp()) for s in starts]
        by_cam: dict[str, int] = {}
        for s in today_rows:
            if s.camera:
                by_cam[s.camera] = by_cam.get(s.camera, 0) + 1
        today = {
            "detections": detections,
            "detections_change_pct": round(100 * (detections - yesterday) / yesterday, 1) if yesterday else None,
            "unique_vehicles": len({s.original_id for s in today_rows if s.original_id}),
            "in_frame_now": len({s.original_id for s in rows if a - 300 <= s.ts <= a}),
            "last_hour": last_hour,
            "last_hour_change_pct": round(100 * (last_hour - prev_hour) / prev_hour, 1) if prev_hour else None,
        }
        source, as_of = "qdrant", anchor
    else:
        starts = [hour0 - timedelta(hours=23 - i) for i in range(24)]
        hourly = mock.hourly_counts(starts)
        today_n = sum(h for s, h in zip(starts, hourly) if s.date() == t.date())
        today = {"detections": today_n, "detections_change_pct": None, "unique_vehicles": None,
                 "in_frame_now": round(hourly[-1] / 12), "last_hour": hourly[-1], "last_hour_change_pct": None}
        by_cam, source, as_of = {}, "mock", t

    return {
        "as_of": as_of.isoformat(timespec="seconds"),
        "source": source,
        "today": today,
        "hourly": [{"start": s.isoformat(timespec="minutes"), "label": s.strftime("%H:%M"), "count": n}
                   for s, n in zip(starts, hourly)],
        "by_camera": sorted(({"camera": k, "name": names.get(k, k), "count": v} for k, v in by_cam.items()),
                            key=lambda r: -r["count"]),
        "cameras": status_counts,
        "parking": parking_summary(lots),
    }


@app.get("/api/vehicles/recent", tags=["Vyhľadávanie"], summary="Posledné prejazdy áut (galéria, panel na mape)")
def recent_vehicles(
    limit: Annotated[int, Query(ge=1, le=50)] = 6,
    camera: Annotated[str | None, Query(description="Iba z jednej kamery")] = None,
):
    """Najnovšie prejazdy z Qdrantu s odkazom na záber. Každé auto iba raz (jeho posledný prejazd)."""
    try:
        pts = store.recent(limit * 6 if not camera else 500)
    except StoreUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    names = camera_names()
    seen, out = set(), []
    for p in pts:
        pl = p.payload or {}
        if camera and pl.get("camera") != camera:
            continue
        vid = pl.get("original_id") or str(p.id)
        if vid in seen:
            continue
        seen.add(vid)
        out.append({"id": str(p.id), "original_id": vid, "camera": pl.get("camera"), "camera_name": names.get(pl.get("camera")),
                    "timestamp": pl.get("timestamp"), "image_url": media_url(pl.get("frame_path") or pl.get("best_frame_path"))})
        if len(out) == limit:
            break
    return {"count": len(out), "vehicles": out}


def _run_search(vector, top_k: int, cameras: list[str] | None, since: float | None, exclude: str | None = None) -> dict:
    top_k = max(1, min(top_k, settings.max_top_k))
    t0 = time.perf_counter()
    try:
        points = store.search(vector, top_k, cameras or None, since, exclude)
    except StoreUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    names = camera_names()
    results = []
    for p in points:
        pl = dict(p.payload or {})
        img = pl.get("frame_path") or pl.get("best_frame_path") or pl.get("reid_crop_path")
        results.append({"id": str(p.id), "score": round(float(p.score), 4), "image_url": media_url(img),
                        "camera_name": names.get(pl.get("camera")), "payload": pl})
    return {"results": results, "count": len(results), "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "embedder": embedder.name, "collection": settings.collection_reid,
            "filters": {"top_k": top_k, "camera": cameras or [], "from": since}}


@app.post("/api/search", response_model=SearchResponse, tags=["Vyhľadávanie"],
          summary="Nájdi auto podľa nahratej fotky (Top-K z Qdrantu)")
async def search_by_image(
    image: Annotated[UploadFile, File(description="Fotka auta (JPG/PNG/WebP, max 10 MB)")],
    top_k: Annotated[int, Form(description="Koľko výsledkov vrátiť")] = 3,
    camera: Annotated[list[str] | None, Form(description="Id kamery, môže byť viackrát; prázdne = všetky")] = None,
    from_: Annotated[str | None, Form(alias="from", description="ISO čas, od kedy hľadať")] = None,
):
    """Frontend (DEV13) pošle fotku ako multipart. Server ju prevedie na vektor, opýta sa Qdrantu
    a vráti najpodobnejšie autá – každé auto iba raz, s jeho najlepším pohľadom.

    ⚠️ Prevod na vektor je placeholder do DEV16 (farebný histogram) – nájde autá podobnej farby."""
    data = await image.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Fotka je väčšia ako {settings.max_upload_mb} MB.")
    if not data:
        raise HTTPException(422, "Prázdny súbor.")
    try:
        vec = embedder.embed_bytes(data)
    except EmbedError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _run_search(vec, top_k, camera, parse_since(from_))


@app.get("/api/search", response_model=SearchResponse, tags=["Vyhľadávanie"],
         summary="Nájdi autá podobné vozidlu, ktoré už je v databáze")
def search_by_vehicle(
    vehicle_id: Annotated[str, Query(description="original_id vozidla z Qdrantu")],
    top_k: Annotated[int, Query(ge=1, le=20)] = 3,
    camera: Annotated[list[str] | None, Query(description="Id kamery, môže byť viackrát")] = None,
    from_: Annotated[str | None, Query(alias="from", description="ISO čas, od kedy hľadať")] = None,
):
    """Napr. operátor klikne na auto v galérii a chce vidieť podobné autá (kandidátov na to isté auto,
    ktoré ReID nespojil). Samotné zadané vozidlo sa vo výsledkoch nevracia.
    Použije sa vektor uložený v Qdrante, takže tu netreba DEV16."""
    try:
        found = store.vector_of_vehicle(vehicle_id)
    except StoreUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if not found:
        raise HTTPException(404, f"Vozidlo {vehicle_id} v Qdrante nie je.")
    vec, _ = found
    return _run_search(vec, top_k, camera, parse_since(from_), exclude=vehicle_id)
