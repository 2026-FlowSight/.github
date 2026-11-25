"""
Test prototypu na krátkom reálnom videu parkoviska + porovnanie s ručne overenou pravdou.

python demo_eval.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
       --gt ../data/parking_lot_1/gt.json --model ../../../models/yolov8n.pt \
       --imgsz 960 --t-off 30 --out ../vysledky/video_960px_t30

Výstup (priečinok --out):
  series.csv      čas, skutočný počet, počet bez pamäte, počet s pamäťou
  metrics.json    presnosť miest, priemerná chyba počtu, ...
  slots.csv       stav každého miesta v čase (pre obrázky)
  detections.json obdĺžniky z YOLO (s --reuse sa YOLO znova nespúšťa)
"""
import argparse
import csv
import json
import os

import cv2
from ultralytics import YOLO

from occupancy_core import SlotConfig, SlotTracker
from parking_occupancy import VEHICLE_CLASSES, make_patch_fn
WARMUP = 10.0  # prvých 10 s sa nehodnotí (pamäť sa ešte len naplní)


def gt_state(gt, sid, t):
    if sid in gt["always_free"]:
        return False
    if sid in gt["intervals"]:
        return any(a <= t < b for a, b in gt["intervals"][sid])
    return gt["default"] == "occupied"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--zones", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--out", default="vysledky")
    ap.add_argument("--reuse", action="store_true", help="použi uložené detections.json (bez YOLO)")
    ap.add_argument("--t-off", type=float, default=30.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    zones = json.load(open(a.zones))
    gt = json.load(open(a.gt))
    cap = cv2.VideoCapture(a.video)
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(3)), int(cap.get(4))
    step = max(1, round(fps * a.every))
    cached = None
    if a.reuse and os.path.exists(f"{a.out}/detections.json"):
        cached = {round(d["t"], 3): d["boxes"] for d in json.load(open(f"{a.out}/detections.json"))}
    model = None if cached else YOLO(a.model)

    mem = SlotTracker(zones["slots"], (h, w), SlotConfig(t_off=a.t_off))
    ids = [s.id for s in mem.slots]

    series, slot_rows, dets_all = [], [], []
    for k in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, frame = cap.read()
        if not ok:
            break
        t = k / fps
        if cached is not None:
            boxes = cached[round(t, 3)]
        else:
            boxes = model.predict(frame, imgsz=a.imgsz, conf=0.25, classes=sorted(VEHICLE_CLASSES), verbose=False)[0].boxes.xyxy.tolist()
        dets = [{"xyxy": b, "score": 1.0, "class": 2} for b in boxes]
        dets_all.append({"t": t, "boxes": [[round(v, 1) for v in d["xyxy"]] for d in dets]})

        naive_state = mem.instant(dets)  # bez pamäte: len to, čo YOLO vidí teraz
        mem.update(t, dets, patch_fn=make_patch_fn(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        mem_state = {s.id: s.occupied for s in mem.slots}
        gt_s = {i: gt_state(gt, i, t) for i in ids}
        series.append({"t": t, "gt": sum(gt_s.values()), "naive": sum(naive_state.values()),
                       "memory": sum(mem_state.values()), "n_det": len(dets)})
        for i in ids:
            slot_rows.append({"t": t, "slot": i, "gt": int(gt_s[i]), "naive": int(naive_state[i]),
                              "memory": int(mem_state[i]), "state": next(s.state.value for s in mem.slots if s.id == i)})

    def metrics(key):
        rows = [r for r in slot_rows if r["t"] >= WARMUP]
        ser = [r for r in series if r["t"] >= WARMUP]
        tp = sum(r[key] and r["gt"] for r in rows)
        fp = sum(r[key] and not r["gt"] for r in rows)
        fn = sum((not r[key]) and r["gt"] for r in rows)
        errs = [r[key] - r["gt"] for r in ser]
        flips = sum(1 for i in ids for p, q in zip([r for r in slot_rows if r["slot"] == i],
                                                    [r for r in slot_rows if r["slot"] == i][1:]) if p[key] != q[key])
        return {
            "presnost_miest": sum(r[key] == r["gt"] for r in rows) / len(rows),
            "f1_obsadene": 2 * tp / max(1, 2 * tp + fp + fn),
            "mae_pocet": sum(abs(e) for e in errs) / len(errs),
            "presne_trafene": sum(e == 0 for e in errs) / len(errs),
            "chyba_max_1": sum(abs(e) <= 1 for e in errs) / len(errs),
            "min_pocet": min(r[key] for r in ser), "max_pocet": max(r[key] for r in ser),
            "zmeny_stavu_miest": flips,
        }

    res = {"model": os.path.basename(a.model), "imgsz": a.imgsz, "every_s": a.every, "t_off": a.t_off, "slots": len(ids),
           "samples": len(series), "gt_min": min(r["gt"] for r in series), "gt_max": max(r["gt"] for r in series),
           "bez_pamate": metrics("naive"), "s_pamatou": metrics("memory"),
           "udalosti": {s.id: [(round(t, 1), a_, b) for t, a_, b in s.events] for s in mem.slots
                        if any(b == "FREE" for _, _, b in s.events) or s.id in gt["intervals"]}}
    json.dump(res, open(f"{a.out}/metrics.json", "w"), indent=1, ensure_ascii=False)
    json.dump(dets_all, open(f"{a.out}/detections.json", "w"))
    for name, rows in (("series", series), ("slots", slot_rows)):
        with open(f"{a.out}/{name}.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    print(json.dumps({k: res[k] for k in ("model", "imgsz", "bez_pamate", "s_pamatou")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
