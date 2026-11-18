"""Načítanie nastavení a konfiguračných súborov (kamery, parkoviská)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    qdrant_url: str | None
    qdrant_path: Path | None
    collection_reid: str
    collection_dashboard: str
    vector_size: int
    media_dir: Path
    cameras_file: Path
    parking_file: Path
    cors_origins: list[str]
    default_top_k: int
    max_top_k: int
    max_upload_mb: int
    timezone: ZoneInfo
    raw: dict = field(repr=False, default_factory=dict)


def _resolve(p: str | None) -> Path | None:
    if not p:
        return None
    path = Path(p).expanduser()
    return path if path.is_absolute() else (ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    cfg_path = Path(os.environ.get("FLOWSIGHT_SETTINGS", ROOT / "config" / "settings.yaml"))
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    q = raw.get("qdrant", {})
    search = raw.get("search", {})
    env = os.environ.get
    url = env("FLOWSIGHT_QDRANT_URL", q.get("url"))
    path = env("FLOWSIGHT_QDRANT_PATH", q.get("path"))
    return Settings(
        qdrant_url=url or None,
        # url má prednosť pred lokálnym súborom
        qdrant_path=None if url else _resolve(path),
        collection_reid=q.get("collection_reid", "vehicles_reid"),
        collection_dashboard=q.get("collection_dashboard", "vehicles_dashboard"),
        vector_size=int(q.get("vector_size", 512)),
        media_dir=_resolve(env("FLOWSIGHT_MEDIA_DIR", raw.get("media_dir", "../../data"))),
        cameras_file=_resolve(raw.get("config_files", {}).get("cameras", "config/cameras.yaml")),
        parking_file=_resolve(raw.get("config_files", {}).get("parking", "config/parking.yaml")),
        cors_origins=list(raw.get("cors_origins", ["*"])),
        default_top_k=int(search.get("default_top_k", 3)),
        max_top_k=int(search.get("max_top_k", 20)),
        max_upload_mb=int(search.get("max_upload_mb", 10)),
        timezone=ZoneInfo(raw.get("timezone", "Europe/Bratislava")),
        raw=raw,
    )


def _load_list(path: Path, key: str) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get(key, [])
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"{path.name}: duplicitné id {dup}")
    for i in items:
        if not (-90 <= float(i["lat"]) <= 90 and -180 <= float(i["lng"]) <= 180):
            raise ValueError(f"{path.name}: {i['id']} má neplatné súradnice")
    return items


@lru_cache
def load_cameras() -> list[dict]:
    return _load_list(get_settings().cameras_file, "cameras")


@lru_cache
def load_parking() -> list[dict]:
    return _load_list(get_settings().parking_file, "parking")
