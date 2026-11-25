"""
Test prototypu na jednom dni z datasetu PKLot (fotky každých ~5 min, každé miesto označené).

Dáta pripraví pklot_download.py. Potom (z priečinka prototyp/):
  python pklot_eval.py --day ../data/pklot/ufpr05_2013-02-22 --model ../../../models/yolov8n.pt \
         --imgsz 1280 --fp-ratio 1.0 --out ../vysledky/pklot_cely_box

  <day>/gt.json  zoznam fotiek: file, ts, spaces[{id, pts (0..1), occ}]
  <day>/img/     fotky
"""
import argparse
import csv
import json
import os
from datetime import datetime

import cv2
from ultralytics import YOLO

from occupancy_core import SlotConfig, SlotTracker
from parking_occupancy import VEHICLE_CLASSES, make_patch_fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--out", default="vysledky_pklot")
    ap.add_argument("--fp-ratio", type=float, default=0.4, help="1.0 = celý obdĺžnik (kamera skoro zhora)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    gt = json.load(open(f"{a.day}/gt.json"))
    first = cv2.imread(f"{a.day}/img/{os.path.basename(gt[0]['file'])}")
    h, w = first.shape[:2]
    slots = [{"id": str(s["id"]), "polygon": [[x * w, y * h] for x, y in s["pts"]]} for s in gt[0]["spaces"]]
    mem = SlotTracker(slots, (h, w), SlotConfig(footprint_ratio=a.fp_ratio))
    model = YOLO(a.model)
    t0 = datetime.fromisoformat(gt[0]["ts"].replace("Z", ""))

    series, rows, dets_all = [], [], []
    for g in gt:
        img = cv2.imread(f"{a.day}/img/{os.path.basename(g['file'])}")
        t = (datetime.fromisoformat(g["ts"].replace("Z", "")) - t0).total_seconds()
        boxes = model.predict(img, imgsz=a.imgsz, conf=a.conf, classes=sorted(VEHICLE_CLASSES),
                              verbose=False)[0].boxes.xyxy.tolist()
        dets = [{"xyxy": b, "score": 1.0, "class": 2} for b in boxes]
        naive = mem.instant(dets)  # bez pamäte: len to, čo YOLO vidí teraz
        mem.update(t, dets, patch_fn=make_patch_fn(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)))
        truth = {str(s["id"]): s["occ"] for s in g["spaces"]}
        memo = {s.id: s.occupied for s in mem.slots}
        clock = g["ts"][11:16]
        series.append({"t": t, "clock": clock, "gt": sum(truth.values()), "naive": sum(naive.values()),
                       "memory": sum(memo.values()), "n_det": len(dets)})
        for s in mem.slots:
            rows.append({"t": t, "slot": s.id, "gt": int(truth[s.id]), "naive": int(naive[s.id]),
                         "memory": int(memo[s.id]), "state": s.state.value})
        dets_all.append({"file": os.path.basename(g["file"]), "t": t, "boxes": [[round(v, 1) for v in b] for b in boxes]})

    def metrics(key):
        tp = sum(r[key] and r["gt"] for r in rows)
        fp = sum(r[key] and not r["gt"] for r in rows)
        fn = sum((not r[key]) and r["gt"] for r in rows)
        errs = [r[key] - r["gt"] for r in series]
        return {"presnost_miest": sum(r[key] == r["gt"] for r in rows) / len(rows),
                "f1_obsadene": 2 * tp / max(1, 2 * tp + fp + fn), "falosne_obsadene": fp, "prehliadnute": fn,
                "mae_pocet": sum(map(abs, errs)) / len(errs), "chyba_max_1": sum(abs(e) <= 1 for e in errs) / len(errs),
                "chyba_max_2": sum(abs(e) <= 2 for e in errs) / len(errs), "priemerna_odchylka": sum(errs) / len(errs)}

    res = {"model": os.path.basename(a.model), "imgsz": a.imgsz, "fp_ratio": a.fp_ratio,
           "fotiek": len(series), "miest": len(slots), "od": series[0]["clock"], "do": series[-1]["clock"],
           "bez_pamate": metrics("naive"), "s_pamatou": metrics("memory")}
    json.dump(res, open(f"{a.out}/metrics.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"slots": slots, "dets": dets_all}, open(f"{a.out}/detections.json", "w"))
    for name, rr in (("series", series), ("slots", rows)):
        with open(f"{a.out}/{name}.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rr[0].keys()))
            wr.writeheader()
            wr.writerows(rr)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
