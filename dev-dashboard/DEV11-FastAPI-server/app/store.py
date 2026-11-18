"""Prístup ku Qdrantu: pripojenie, vyhľadávanie, dáta pre štatistiky.

Formát bodov je rovnaký ako v pipeline rd-research/02-multi-view-reid (Ján):
  vehicles_reid      – jeden bod = jeden pohľad na auto
                       payload: original_id, slot, frame_path, reid_crop_path, timestamp, camera, area
  vehicles_dashboard – jeden bod = jedno auto s najlepším záberom (best_frame_path, views)
Navyše API vie využiť `ts` (unix čas). Ak chýba, dopočíta sa z `timestamp`
(ISO dátum a čas, alebo iba „HH:MM:SS“ ako v pipeline – vtedy sa berie dnešný deň).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, time as dtime

import numpy as np
from qdrant_client import QdrantClient, models

from .config import Settings

log = logging.getLogger("flowsight.store")


class StoreUnavailable(RuntimeError):
    pass


@dataclass
class Sighting:
    ts: float
    camera: str | None
    original_id: str | None


def point_ts(payload: dict, tz) -> float | None:
    if isinstance(payload.get("ts"), (int, float)):
        return float(payload["ts"])
    raw = payload.get("timestamp")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            t = dtime.fromisoformat(raw)
        except ValueError:
            return None
        dt = datetime.combine(datetime.now(tz).date(), t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.timestamp()


class QdrantStore:
    def __init__(self, settings: Settings):
        self.s = settings
        self._client: QdrantClient | None = None
        self._error: str | None = None
        self._lock = threading.Lock()

    # ---------- pripojenie ----------
    @property
    def target(self) -> str:
        return self.s.qdrant_url or f"lokálny súbor {self.s.qdrant_path}"

    def client(self) -> QdrantClient:
        with self._lock:
            if self._client is not None:
                return self._client
            try:
                if self.s.qdrant_url:
                    c = QdrantClient(url=self.s.qdrant_url, timeout=5)
                elif self.s.qdrant_path and self.s.qdrant_path.exists():
                    c = QdrantClient(path=str(self.s.qdrant_path))
                else:
                    raise StoreUnavailable(
                        f"Qdrant databáza neexistuje ({self.s.qdrant_path}). Spusti `python scripts/seed_qdrant.py` "
                        "alebo nastav qdrant.url v config/settings.yaml.")
                c.get_collections()  # overí spojenie
            except StoreUnavailable as exc:
                self._error = str(exc)
                raise
            except Exception as exc:  # noqa: BLE001
                self._error = f"Qdrant ({self.target}) nie je dostupný: {exc}"
                raise StoreUnavailable(self._error) from exc
            self._client, self._error = c, None
            return c

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def status(self) -> dict:
        try:
            c = self.client()
        except StoreUnavailable as exc:
            return {"ok": False, "target": self.target, "error": str(exc), "collections": {}}
        cols = {}
        for name in (self.s.collection_reid, self.s.collection_dashboard):
            cols[name] = c.count(name, exact=True).count if c.collection_exists(name) else None
        return {"ok": True, "target": self.target, "error": None, "collections": cols}

    def available(self) -> bool:
        try:
            c = self.client()
            return c.collection_exists(self.s.collection_reid)
        except StoreUnavailable:
            return False

    # ---------- vyhľadávanie ----------
    def search(self, vector: np.ndarray, top_k: int, cameras: list[str] | None, since: float | None,
               exclude_vehicle: str | None = None) -> list[models.ScoredPoint]:
        c = self.client()
        must: list = []
        if cameras:
            must.append(models.FieldCondition(key="camera", match=models.MatchAny(any=cameras)))
        if since is not None:
            must.append(models.FieldCondition(key="ts", range=models.Range(gte=since)))
        must_not = [models.FieldCondition(key="original_id", match=models.MatchValue(value=exclude_vehicle))] if exclude_vehicle else []
        flt = models.Filter(must=must or None, must_not=must_not or None) if (must or must_not) else None
        # Jedno auto má v kolekcii veľa pohľadov/prejazdov – zoskupíme podľa original_id a z každého auta
        # vrátime iba najpodobnejší pohľad, aby Top-3 boli 3 rôzne autá.
        res = c.query_points_groups(self.s.collection_reid, query=vector.tolist(), group_by="original_id",
                                    limit=top_k, group_size=1, query_filter=flt, with_payload=True)
        return [g.hits[0] for g in res.groups if g.hits]

    def vector_of_vehicle(self, vehicle_id: str) -> tuple[np.ndarray, dict] | None:
        c = self.client()
        pts, _ = c.scroll(self.s.collection_reid, limit=1, with_vectors=True, with_payload=True,
                          scroll_filter=models.Filter(must=[models.FieldCondition(
                              key="original_id", match=models.MatchValue(value=vehicle_id))]))
        if not pts:
            return None
        return np.asarray(pts[0].vector, dtype=np.float32), pts[0].payload

    # ---------- štatistiky ----------
    def sightings(self, since: float) -> list[Sighting]:
        """Všetky prejazdy od `since`. Pri veľkej DB by sa to nahradilo `count` dotazmi s indexom na ts."""
        c = self.client()
        out: list[Sighting] = []
        offset = None
        flt = models.Filter(should=[
            models.FieldCondition(key="ts", range=models.Range(gte=since)),
            # body z pôvodnej pipeline nemajú ts – tie berieme všetky a filtrujeme v Pythone
            models.IsEmptyCondition(is_empty=models.PayloadField(key="ts")),
        ])
        while True:
            pts, offset = c.scroll(self.s.collection_reid, limit=1000, offset=offset, scroll_filter=flt,
                                   with_payload=["ts", "timestamp", "camera", "original_id"], with_vectors=False)
            for p in pts:
                ts = point_ts(p.payload, self.s.timezone)
                if ts is not None and ts >= since:
                    out.append(Sighting(ts, p.payload.get("camera"), p.payload.get("original_id")))
            if offset is None:
                break
        return out

    def recent(self, limit: int, until: float | None = None) -> list:
        c = self.client()
        flt = models.Filter(must=[models.FieldCondition(key="ts", range=models.Range(lte=until))]) if until else None
        pts, _ = c.scroll(self.s.collection_reid, limit=limit, with_payload=True, scroll_filter=flt,
                          order_by=models.OrderBy(key="ts", direction=models.Direction.DESC))
        return pts

    def latest_ts(self) -> float | None:
        c = self.client()
        try:
            res = c.scroll(self.s.collection_reid, limit=1, with_payload=["ts"],
                           order_by=models.OrderBy(key="ts", direction=models.Direction.DESC))[0]
            if res:
                return float(res[0].payload["ts"])
        except Exception:  # noqa: BLE001 – order_by vyžaduje index; pri pipeline bez ts nemusí ísť
            pass
        return None
