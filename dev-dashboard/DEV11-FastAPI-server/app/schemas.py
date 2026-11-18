"""Tvary JSON odpovedí – z nich sa generuje aj Swagger dokumentácia (/docs)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["qdrant", "config", "mock"]


class Camera(BaseModel):
    id: str = Field(examples=["msp-12"])
    no: str = Field(description="Číslo kamery podľa MsP Pezinok", examples=["12"])
    name: str = Field(examples=["Kamera 12 – Moyzesova"])
    area: str | None = Field(None, description="Časť mesta", examples=["Centrum"])
    street: str | None = None
    type: str | None = Field(None, description="otočná (PTZ) / statická")
    mount: str | None = None
    site: str | None = Field(None, description="ulica = verejný priestor, areál = škola, dvor...")
    lat: float = Field(examples=[48.2876])
    lng: float = Field(examples=[17.2668])
    precision: str | None = Field(None, description="Ako presne je poloha určená (križovatka / adresa / budova / približne)")
    status: Literal["online", "warning", "offline"] = Field(description="online / warning (podozrivé) / offline")
    status_note: str | None = None
    vehicles_today: int = Field(0, description="Prejazdy áut dnes (z Qdrantu)")


class CamerasResponse(BaseModel):
    count: int
    summary: dict[str, int] = Field(description="Počet kamier podľa stavu")
    source: dict[str, Source] = Field(description="Odkiaľ je ktorá časť dát")
    cameras: list[Camera]


class ParkingLot(BaseModel):
    id: str = Field(examples=["p-7"])
    name: str = Field(examples=["Parkovisko Za hradbami"])
    street: str | None = None
    kind: str | None = Field(None, description="Typ parkoviska (verejné, obchodné centrum, P+R...)")
    capacity: int
    capacity_source: str | None = Field(None, description="Odkiaľ je kapacita (OSM, tlačová správa, odhad z plochy)")
    occupied: int
    free: int
    ratio: float = Field(description="Obsadenosť 0–1")
    level: Literal["free", "busy", "full"] = Field(description="free < 60 %, busy < 85 %, full ≥ 85 %")
    lat: float
    lng: float
    cameras: list[str] = Field(default_factory=list)
    area_m2: int | None = None
    polygon: list[list[float]] = Field(default_factory=list, description="[[lat, lng], ...]")


class ParkingResponse(BaseModel):
    updated_at: str
    source: dict[str, Source]
    summary: dict
    parking: list[ParkingLot]


class HourBucket(BaseModel):
    start: str
    label: str = Field(examples=["14:00"])
    count: int


class CameraCount(BaseModel):
    camera: str
    name: str
    count: int


class StatsResponse(BaseModel):
    as_of: str = Field(description="Ku ktorému času sú čísla")
    source: Source
    today: dict = Field(description="Čísla pre kartičky dashboardu")
    hourly: list[HourBucket] = Field(description="Prejazdy za posledných 24 hodín po hodinách")
    by_camera: list[CameraCount]
    cameras: dict[str, int]
    parking: dict


class SearchPayload(BaseModel):
    model_config = {"extra": "allow"}
    original_id: str | None = None
    frame_path: str | None = None
    timestamp: str | None = None
    camera: str | None = None


class SearchResult(BaseModel):
    id: str
    score: float = Field(description="Kosínusová podobnosť 0–1")
    image_url: str | None = Field(None, description="URL záberu, servíruje ho toto API")
    camera_name: str | None = None
    payload: SearchPayload


class SearchResponse(BaseModel):
    results: list[SearchResult]
    count: int
    took_ms: float
    embedder: str
    collection: str
    filters: dict
