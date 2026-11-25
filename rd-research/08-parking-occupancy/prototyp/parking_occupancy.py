"""
R&D 08 - prototyp: počítanie obsadenosti parkoviska na videu.

Príklad (z priečinka prototyp/):
  python parking_occupancy.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
      --model ../../../models/yolov8n.pt --every 1 --start 14:00:00 \
      --csv occupancy.csv --out annotated.mp4

zones.json - náš formát:
  {"lot_id": "P1", "mode": "slots", "footprint_ratio": 0.4, "slots": [{"id": "A01", "polygon": [[x,y], ...]}, ...]}
  {"lot_id": "P2", "mode": "zone", "capacity": 40, "zone": [[x,y], ...]}
  Akceptuje aj výstup Ultralytics ParkingPtsSelection (zoznam {"points": [...]}).
  footprint_ratio: aká časť obdĺžnika auta (odspodu) sa ráta ako miesto, kde auto stojí.
                   0.4 pre šikmú kameru, 1.0 pre kameru, ktorá pozerá takmer zhora.
"""
import argparse
import csv
import json
from datetime import datetime, timedelta

import cv2
import numpy as np
from ultralytics import YOLO

from occupancy_core import (MemoryConfig, ParkedMemory, SlotConfig, SlotState,
                            SlotTracker)

VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck (COCO)
COLORS = {
    SlotState.FREE: (80, 200, 80),
    SlotState.ARRIVING: (0, 200, 255),
    SlotState.OCCUPIED: (60, 60, 230),
    SlotState.LEAVING: (200, 120, 255),
}


def load_zones(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):  # formát Ultralytics
        data = {"lot_id": "lot", "mode": "slots",
                "slots": [{"id": f"S{i+1:02d}", "polygon": r["points"]} for i, r in enumerate(data)]}
    return data


def detect(model, frame, conf, imgsz):
    r = model.predict(frame, imgsz=imgsz, conf=conf, iou=0.45, verbose=False)[0]
    out = []
    if r.boxes is not None:
        for b in r.boxes:
            cls = int(b.cls[0])
            if cls in VEHICLE_CLASSES:
                out.append({"xyxy": b.xyxy[0].tolist(), "score": float(b.conf[0]), "class": cls})
    return out


def make_patch_fn(gray):
    def patch(slot):
        x0, y0 = slot.origin
        h, w = slot.mask.shape
        crop = gray[y0:y0 + h, x0:x0 + w]
        return cv2.resize(crop, (24, 24), interpolation=cv2.INTER_AREA) if crop.size else None
    return patch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--zones", required=True)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--every", type=float, default=1.0, help="detekcia každých N sekúnd")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--start", default="00:00:00", help="reálny čas začiatku videa HH:MM:SS")
    ap.add_argument("--csv", default="occupancy.csv")
    ap.add_argument("--out", default=None, help="voliteľné anotované video")
    ap.add_argument("--report-every", type=float, default=60.0, help="výpis do konzoly každých N s")
    args = ap.parse_args()

    zones = load_zones(args.zones)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, round(fps * args.every))
    t0 = datetime.strptime(args.start, "%H:%M:%S")
    model = YOLO(args.model, task="detect")

    if zones["mode"] == "slots":
        engine = SlotTracker(zones["slots"], (h, w), SlotConfig(footprint_ratio=zones.get("footprint_ratio", 0.4)))
        capacity = len(zones["slots"])
    else:
        engine = ParkedMemory(zones["zone"], (h, w), MemoryConfig())
        capacity = zones.get("capacity")

    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps / step, (w, h)) if args.out else None
    f_csv = open(args.csv, "w", newline="", encoding="utf-8")
    wr = csv.writer(f_csv)
    wr.writerow(["video_s", "clock", "lot_id", "occupied", "capacity", "free", "n_detections", "slot_states"])

    idx, next_report = 0, 0.0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step:
            idx += 1
            continue
        ok, frame = cap.retrieve()
        t = idx / fps
        idx += 1
        dets = detect(model, frame, args.conf, args.imgsz)

        if isinstance(engine, SlotTracker):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            n = engine.update(t, dets, patch_fn=make_patch_fn(gray))
            states = ";".join(f"{k}={v[0]}" for k, v in engine.states().items())
        else:
            n = engine.update(t, dets)
            states = ""

        clock = (t0 + timedelta(seconds=t)).strftime("%H:%M:%S")
        free = capacity - n if capacity else ""
        wr.writerow([f"{t:.1f}", clock, zones["lot_id"], n, capacity or "", free, len(dets), states])
        if t >= next_report:
            print(f"O {clock} tam bolo {n} áut" + (f" / {capacity} miest" if capacity else ""))
            next_report += args.report_every

        if writer:
            vis = frame.copy()
            if isinstance(engine, SlotTracker):
                for s in engine.slots:
                    cv2.polylines(vis, [np.int32(s.polygon)], True, COLORS[s.state], 2)
            else:
                for o in engine.objects:
                    col = (60, 60, 230) if o.confirmed else (0, 200, 255)
                    x1, y1, x2, y2 = map(int, o.box)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), col, 2)
            for d in dets:
                x1, y1, x2, y2 = map(int, d["xyxy"])
                cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 255, 255), 1)
            cv2.putText(vis, f"{clock}  obsadene: {n}/{capacity or '?'}", (12, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            writer.write(vis)

    f_csv.close()
    if writer:
        writer.release()
    print(f"Hotovo -> {args.csv}")


if __name__ == "__main__":
    main()
