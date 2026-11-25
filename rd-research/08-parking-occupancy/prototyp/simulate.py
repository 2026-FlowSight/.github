"""
Test na umelých dátach: 3 miesta, 300 s, presne vieme, kedy kde stojí auto.

Čo simulácia obsahuje:
  - YOLO prehliadne každé auto v 25 % snímok,
  - 140.–150. s prejde pred miestami autobus a zakryje ich,
  - 30.–45. s prejde cez parkovisko auto, ktoré nezastaví.

python simulate.py --out ../vysledky/simulacia/series.csv
"""
import argparse
import csv
import json
import os
import random

from occupancy_core import ParkedMemory, SlotTracker

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME = (720, 1280)
CAR_BOX = {"A01": [100, 350, 185, 515], "A02": [185, 350, 280, 515], "A03": [265, 350, 370, 515]}
ZONE = [[50, 300], [450, 300], [450, 560], [50, 560]]
MISS_RATE = 0.25
WARMUP = 10  # prvých 10 s sa nehodnotí


def truth(t):
    """A01 stojí celý čas, A02 od 60. do 200. s, A03 od 120. s do konca."""
    return {"A01": True, "A02": 60 <= t < 200, "A03": t >= 120}


def detections(t, rng):
    dets = [{"xyxy": CAR_BOX[k], "score": 0.8, "class": 2}
            for k, parked in truth(t).items() if parked and rng.random() > MISS_RATE]
    if 140 <= t < 150:  # autobus zakryje miesta: YOLO vidí len autobus
        dets = [{"xyxy": [90, 250, 400, 420], "score": 0.9, "class": 5}]
    if 30 <= t < 45:  # prechádzajúce auto
        x = 300 + 12 * (t - 30)
        dets.append({"xyxy": [x, 320, x + 120, 460], "score": 0.8, "class": 2})
    return dets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sim_series.csv")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    slots = json.load(open(os.path.join(HERE, "zones_example.json"), encoding="utf-8"))["slots"]
    slot_tracker = SlotTracker(slots, FRAME)
    zone_memory = ParkedMemory(ZONE, FRAME)

    rows, err = [], {"naive": 0, "slots": 0, "memory": 0}
    for t in range(300):
        dets = detections(t, rng)
        row = {"t": t, "gt": sum(truth(t).values()),
               "naive": sum(d["class"] == 2 for d in dets),  # počet áut, ktoré YOLO vidí práve teraz
               "slots": slot_tracker.update(t, dets),
               "memory": zone_memory.update(t, dets)}
        rows.append(row)
        if t >= WARMUP:
            for k in err:
                err[k] += abs(row[k] - row["gt"])

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n = len(rows) - WARMUP
    print("Priemerná chyba počtu áut: " + ", ".join(f"{k}={v / n:.2f}" for k, v in err.items()))
    for s in slot_tracker.slots:
        print(s.id, [(t, a_, b) for t, a_, b in s.events])


if __name__ == "__main__":
    main()
