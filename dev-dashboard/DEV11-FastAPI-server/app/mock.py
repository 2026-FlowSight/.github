"""Ukážkové (mock) dáta pre časti, ktoré zatiaľ nemajú zdroj.

- stav kamier      → neskôr health-check z Milestone / Axis (DEV08)
- obsadenosť parkovísk → neskôr počítanie áut na parkovisku (DEV03)
- štatistiky       → iba keď Qdrant nebeží (inak sa počítajú z Qdrantu)

Hodnoty sú deterministické (rovnaký čas = rovnaké čísla), aby sa dashboard pri obnovení „neskákal“,
a menia sa podľa dennej doby ako skutočná doprava.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime

# Rovnaké kamery ako v ukážkových udalostiach DEV13 (data/events.js):
# msp-17 „Kamera bez obrazu“, msp-25 požiar, msp-5 protismer, msp-21 hľadané vozidlo.
OFFLINE = {"msp-17": "Výpadok signálu z Milestone", "msp-29": "Plánovaná údržba"}
WARNING = {"msp-25": "Aktívny poplach: dym", "msp-5": "Aktívny poplach: jazda v protismere",
           "msp-21": "Zhoda s hľadaným vozidlom"}


def _rand(*parts) -> float:
    """Deterministické „náhodné“ číslo 0–1 z ľubovoľných hodnôt."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def traffic_curve(hour: float) -> float:
    """Relatívna intenzita dopravy 0–1 podľa hodiny dňa (ranná a popoludňajšia špička)."""
    morning = math.exp(-((hour - 7.5) ** 2) / 3.0)
    afternoon = math.exp(-((hour - 16.0) ** 2) / 5.0)
    day = 0.45 * math.exp(-((hour - 12.5) ** 2) / 18.0)
    return min(1.0, 0.05 + 0.85 * morning + 0.95 * afternoon + day)


def camera_status(camera_id: str) -> tuple[str, str | None]:
    if camera_id in OFFLINE:
        return "offline", OFFLINE[camera_id]
    if camera_id in WARNING:
        return "warning", WARNING[camera_id]
    return "online", None


def parking_occupancy(lot: dict, now: datetime) -> int:
    """Počet obsadených miest. Mení sa každých 5 minút."""
    hour = now.hour + now.minute / 60
    # Sídliskové parkoviská sú plné v noci, pri obchodoch a v centre cez deň.
    residential = _rand(lot["id"], "type") < 0.5
    base = 0.25 + 0.5 * _rand(lot["id"], "base")
    if residential:
        ratio = base + 0.45 * (1 - traffic_curve(hour)) - 0.1
    else:
        ratio = base + 0.55 * traffic_curve(hour) - 0.15
    bucket = int(now.timestamp() // 300)
    ratio += (_rand(lot["id"], bucket) - 0.5) * 0.08
    ratio = max(0.03, min(1.0, ratio))
    return round(lot["capacity"] * ratio)


def hourly_counts(hour_starts: list[datetime], scale: int = 95) -> list[int]:
    """Náhradný priebeh prejazdov za hodinu, keď Qdrant nebeží."""
    return [round(scale * traffic_curve(h.hour + 0.5) * (0.9 + 0.2 * _rand("h", h.isoformat()))) for h in hour_starts]
