"""
R&D 08 - jadro logiky obsadenosti parkoviska (bez závislosti na cv2 / YOLO).

Dva režimy:
  1) SlotTracker  - parkovisko s vyznačenými miestami (polygón na každé miesto).
                    Každé miesto má stavový automat FREE -> ARRIVING -> OCCUPIED -> LEAVING -> FREE.
  2) ParkedMemory - parkovisko bez vyznačených miest (jedna veľká zóna).
                    Pamätá si "zaparkované objekty" aj keď ich YOLO na chvíľu stratí.

Detekcia = dict {"xyxy": [x1, y1, x2, y2], "score": float, "class": int}
Čas t = sekundy od začiatku videa (float).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


# ---------------------------------------------------------------- geometria

def polygon_mask(polygon, shape):
    """Vráti (mask, (x0, y0)) - bool maska polygónu orezaná na jeho bbox."""
    pts = np.asarray(polygon, dtype=np.float64)
    x0, y0 = np.floor(pts.min(axis=0)).astype(int)
    x1, y1 = np.ceil(pts.max(axis=0)).astype(int)
    h, w = shape
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    ys, xs = np.mgrid[y0:y1, x0:x1]
    px, py = xs + 0.5, ys + 0.5
    inside = np.zeros(px.shape, dtype=bool)
    n = len(pts)
    for i in range(n):  # ray casting
        xa, ya = pts[i]
        xb, yb = pts[(i + 1) % n]
        cond = (ya > py) != (yb > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xb - xa) * (py - ya) / (yb - ya) + xa
        inside ^= cond & (px < xint)
    return inside, (x0, y0)


def footprint(xyxy, ratio=0.4):
    """Spodná časť bboxu ~ miesto, kde auto stojí na zemi (odolnejšie voči perspektíve)."""
    x1, y1, x2, y2 = xyxy
    return [x1, y2 - (y2 - y1) * ratio, x2, y2]


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def appearance_similarity(a, b):
    """Normalizovaná korelácia dvoch malých grayscale výrezov (-1..1)."""
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    a = a.astype(np.float32).ravel()
    b = b.astype(np.float32).ravel()
    a -= a.mean()
    b -= b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / d) if d > 1e-6 else 1.0


# ---------------------------------------------------------------- režim 1: miesta

class SlotState(str, Enum):
    FREE = "FREE"
    ARRIVING = "ARRIVING"
    OCCUPIED = "OCCUPIED"
    LEAVING = "LEAVING"


@dataclass
class SlotConfig:
    t_on: float = 8.0           # koľko s musí auto stáť, aby bolo miesto OCCUPIED
    t_off: float = 30.0         # koľko s musí auto chýbať, aby bolo miesto FREE
    gap_tol: float = 3.0        # tolerancia výpadku detekcie počas ARRIVING
    occ_overlap: float = 0.30   # podiel plochy miesta pokrytý stopou auta
    occluder_overlap: float = 0.15  # bbox prekrýva miesto, ale stopa nie -> zakrýva
    same_appearance: float = 0.80   # podobnosť s referenciou = auto tam stále je
    appearance_margin: float = 0.10 # o koľko viac sa musí podobať na "s autom" než na "prázdne"
    ref_overlap: float = 0.60       # referenciu "s autom" ukladáme len pri istom pokrytí
    footprint_ratio: float = 0.4


@dataclass
class Slot:
    id: str
    polygon: list
    mask: np.ndarray = None
    origin: tuple = (0, 0)
    state: SlotState = SlotState.FREE
    since: float = 0.0          # čas vstupu do aktuálneho stavu
    last_seen: float = -1e9     # posledná pozitívna detekcia
    occ_ref: np.ndarray = None  # vzhľad miesta s autom (malý grayscale výrez)
    free_ref: np.ndarray = None # vzhľad prázdneho miesta
    events: list = field(default_factory=list)

    @property
    def occupied(self):
        # LEAVING sa stále počíta ako obsadené (auto mohlo byť len zakryté)
        return self.state in (SlotState.OCCUPIED, SlotState.LEAVING)


class SlotTracker:
    def __init__(self, slots, frame_shape, cfg: SlotConfig | None = None):
        self.cfg = cfg or SlotConfig()
        self.shape = frame_shape
        self.slots = []
        self._last_t = None
        for s in slots:
            m, o = polygon_mask(s["polygon"], frame_shape)
            self.slots.append(Slot(id=str(s["id"]), polygon=s["polygon"], mask=m, origin=o))

    def _coverage(self, slot, box):
        """Podiel pixelov miesta pokrytých obdĺžnikom box."""
        x0, y0 = slot.origin
        mh, mw = slot.mask.shape
        bx1 = int(max(0, np.floor(box[0]) - x0))
        by1 = int(max(0, np.floor(box[1]) - y0))
        bx2 = int(min(mw, np.ceil(box[2]) - x0))
        by2 = int(min(mh, np.ceil(box[3]) - y0))
        total = slot.mask.sum()
        if total == 0 or bx2 <= bx1 or by2 <= by1:
            return 0.0
        return float(slot.mask[by1:by2, bx1:bx2].sum() / total)

    def _set(self, slot, state, t):
        if state != slot.state:
            slot.events.append((t, slot.state.value, state.value))
            slot.state, slot.since = state, t

    def update(self, t, detections, patch_fn=None):
        """
        t          - čas v sekundách
        detections - zoznam detekcií vozidiel
        patch_fn   - voliteľná funkcia slot -> malý grayscale výrez miesta (pre test vzhľadu)
        """
        c = self.cfg
        dt = 0.0 if self._last_t is None else t - self._last_t
        self._last_t = t
        for slot in self.slots:
            best_fp, best_box = 0.0, 0.0
            for d in detections:
                best_fp = max(best_fp, self._coverage(slot, footprint(d["xyxy"], c.footprint_ratio)))
                best_box = max(best_box, self._coverage(slot, d["xyxy"]))
            seen = best_fp >= c.occ_overlap
            occluded = (not seen) and best_box >= c.occluder_overlap

            # test vzhľadu: YOLO auto nevidí, ale miesto vyzerá rovnako ako s autom
            same_look = False
            patch = patch_fn(slot) if patch_fn is not None else None
            if not seen and slot.occ_ref is not None and patch is not None:
                s_occ = appearance_similarity(patch, slot.occ_ref)
                s_free = appearance_similarity(patch, slot.free_ref) if slot.free_ref is not None else -1.0
                same_look = s_occ >= c.same_appearance and s_occ - s_free >= c.appearance_margin
            strong = best_fp >= c.ref_overlap  # auto je isto celé na mieste

            if seen:
                slot.last_seen = t

            st = slot.state
            if st == SlotState.FREE:
                if seen:
                    self._set(slot, SlotState.ARRIVING, t)
                elif not occluded and patch is not None and best_box == 0.0:
                    slot.free_ref = patch  # zapamätaj si, ako vyzerá prázdne miesto
            elif st == SlotState.ARRIVING:
                if t - slot.last_seen > c.gap_tol:
                    self._set(slot, SlotState.FREE, t)
                elif t - slot.since >= c.t_on:
                    self._set(slot, SlotState.OCCUPIED, t)
                    if strong and patch is not None:
                        slot.occ_ref = patch
            elif st == SlotState.OCCUPIED:
                if seen or same_look:
                    if strong and patch is not None:
                        slot.occ_ref = patch  # aktualizuj (svetlo, tiene), len keď je auto isto celé na mieste
                elif occluded:
                    pass  # zamrazenie: niečo miesto zakrýva, nič nemeníme
                elif t - slot.last_seen > c.gap_tol:
                    self._set(slot, SlotState.LEAVING, t)
            elif st == SlotState.LEAVING:
                if seen or same_look:
                    self._set(slot, SlotState.OCCUPIED, t)
                elif occluded:
                    slot.since += dt  # zakryté: odpočet t_off sa pozastaví
                elif t - slot.since >= c.t_off:
                    self._set(slot, SlotState.FREE, t)
                    slot.occ_ref = None
        return self.count()

    def instant(self, detections):
        """Stav miest len podľa aktuálnej detekcie, bez pamäte (na porovnanie)."""
        c = self.cfg
        return {s.id: max((self._coverage(s, footprint(d["xyxy"], c.footprint_ratio)) for d in detections),
                          default=0.0) >= c.occ_overlap for s in self.slots}

    def count(self):
        return sum(s.occupied for s in self.slots)

    def states(self):
        return {s.id: s.state.value for s in self.slots}


# ---------------------------------------------------------------- režim 2: zóna bez miest

@dataclass
class ParkedObject:
    oid: int
    box: list
    first_seen: float
    last_seen: float
    hits: int = 1
    confirmed: bool = False


@dataclass
class MemoryConfig:
    t_on: float = 20.0      # stojí aspoň toľko -> zaparkovaný (dlhšie než pri miestach)
    t_hold: float = 60.0    # ako dlho si pamätáme nezobrazené zaparkované auto
    t_tentative: float = 3.0  # nepotvrdený objekt zabudneme rýchlo
    match_iou: float = 0.35
    max_shift: float = 0.25   # max posun stredu (relatívne k šírke boxu), inak je to idúce auto
    box_ema: float = 0.2


class ParkedMemory:
    """Jednoduchý IoU tracker s dlhou pamäťou pre stojace objekty."""

    def __init__(self, zone_polygon, frame_shape, cfg: MemoryConfig | None = None):
        self.cfg = cfg or MemoryConfig()
        self.zone_mask, self.zone_origin = polygon_mask(zone_polygon, frame_shape)
        self.objects: list[ParkedObject] = []
        self._next = 1

    def _in_zone(self, xyxy):
        x1, y1, x2, y2 = xyxy
        cx, cy = int((x1 + x2) / 2) - self.zone_origin[0], int(y2) - 1 - self.zone_origin[1]
        h, w = self.zone_mask.shape
        return 0 <= cx < w and 0 <= cy < h and bool(self.zone_mask[cy, cx])

    def update(self, t, detections):
        c = self.cfg
        dets = [d["xyxy"] for d in detections if self._in_zone(d["xyxy"])]
        # greedy priradenie podľa IoU (pri parkovisku stačí, autá sa takmer nehýbu)
        pairs = sorted(
            ((iou(o.box, d), i, j) for i, o in enumerate(self.objects) for j, d in enumerate(dets)),
            reverse=True,
        )
        used_o, used_d = set(), set()
        for score, i, j in pairs:
            if score < c.match_iou or i in used_o or j in used_d:
                continue
            o, d = self.objects[i], dets[j]
            w = max(1.0, o.box[2] - o.box[0])
            shift = abs((o.box[0] + o.box[2]) / 2 - (d[0] + d[2]) / 2) / w
            if not o.confirmed and shift > c.max_shift:
                # pohybuje sa -> začni odznova merať čas státia
                o.first_seen = t
            o.box = [(1 - c.box_ema) * a + c.box_ema * b for a, b in zip(o.box, d)]
            o.last_seen, o.hits = t, o.hits + 1
            if not o.confirmed and t - o.first_seen >= c.t_on:
                o.confirmed = True
            used_o.add(i)
            used_d.add(j)
        for j, d in enumerate(dets):
            if j not in used_d:
                self.objects.append(ParkedObject(self._next, list(d), t, t))
                self._next += 1
        # zabúdanie: potvrdené autá držíme t_hold, nepotvrdené len t_tentative
        self.objects = [
            o for o in self.objects
            if t - o.last_seen <= (c.t_hold if o.confirmed else c.t_tentative)
        ]
        return self.count()

    def count(self):
        return sum(o.confirmed for o in self.objects)
