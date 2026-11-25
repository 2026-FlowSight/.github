"""
Obrázky do reportu z výsledkov demo_eval.py.

Z priečinka prototyp/:
python demo_figures.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
       --res ../vysledky/video_960px_t30 --topdown solution_ci_parking_demo.mp4 \
       --model ../../../models/yolov8n.pt --out ../report/obrazky
"""
import argparse
import csv
import json
import os
from collections import defaultdict

import cv2
import numpy as np
from ultralytics import YOLO

GREEN, RED, ORANGE, VIOLET, WHITE = (60, 190, 60), (50, 50, 230), (0, 170, 255), (220, 90, 170), (255, 255, 255)
STATE_COL = {"FREE": GREEN, "ARRIVING": ORANGE, "OCCUPIED": RED, "LEAVING": VIOLET}
STATE_SK = {"FREE": "VOLNE", "ARRIVING": "PRICHADZA", "OCCUPIED": "OBSADENE", "LEAVING": "ODCHADZA?"}


def frame_at(cap, t, fps):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps)))
    return cap.read()[1]


def banner(img, text, sub=None, col=(30, 30, 30)):
    h = 52 if sub else 34
    out = cv2.copyMakeBorder(img, h, 0, 0, 0, cv2.BORDER_CONSTANT, value=col)
    cv2.putText(out, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 2, cv2.LINE_AA)
    if sub:
        cv2.putText(out, sub, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)
    return out


def draw_slots(img, slots, colors, boxes=None, thick=2):
    over = img.copy()
    for s in slots:
        cv2.fillPoly(over, [np.int32(s["polygon"])], colors[s["id"]])
    img = cv2.addWeighted(over, 0.45, img, 0.55, 0)
    for s in slots:
        cv2.polylines(img, [np.int32(s["polygon"])], True, colors[s["id"]], thick, cv2.LINE_AA)
    for b in boxes or []:
        x1, y1, x2, y2 = map(int, b)
        cv2.rectangle(img, (x1, y1), (x2, y2), WHITE, 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--zones", required=True)
    ap.add_argument("--res", required=True)
    ap.add_argument("--topdown")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--out", default="obrazky")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    slots = json.load(open(a.zones))["slots"]
    rows = list(csv.DictReader(open(f"{a.res}/slots.csv")))
    series = list(csv.DictReader(open(f"{a.res}/series.csv")))
    dets = {round(d["t"], 3): d["boxes"] for d in json.load(open(f"{a.res}/detections.json"))}
    by_t = defaultdict(dict)
    for r in rows:
        by_t[round(float(r["t"]), 3)][r["slot"]] = r
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_w, frame_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 1) porovnanie bez pamäte / s pamäťou v okamihu, keď je počet bez pamäte najhorší
    worst = max((s for s in series if float(s["t"]) >= 10 and float(s["t"]) < 60),
                key=lambda s: int(s["gt"]) - int(s["naive"]))
    t = round(float(worst["t"]), 3)
    fr = frame_at(cap, t, fps)
    st = by_t[t]
    naive_col = {i: (RED if st[i]["naive"] == "1" else GREEN) for i in st}
    mem_col = {i: STATE_COL[st[i]["state"]] for i in st}
    left = banner(draw_slots(fr, slots, naive_col, dets[t]),
                  f"Bez pamate: {worst['naive']} aut", f"skutocnost: {worst['gt']} aut  (cas {t:.0f} s)", (40, 40, 120))
    right = banner(draw_slots(fr, slots, mem_col, dets[t]),
                   f"S pamatou: {worst['memory']} aut", f"skutocnost: {worst['gt']} aut  (cas {t:.0f} s)", (120, 60, 20))
    cv2.imwrite(f"{a.out}/porovnanie.jpg", np.hstack([left, np.full((left.shape[0], 8, 3), 255, np.uint8), right]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])

    # 2) celý záber s miestami a ich ID
    fr0 = frame_at(cap, 30.0, fps)
    vis = draw_slots(fr0, slots, {s["id"]: (ORANGE if s["id"].startswith("E") else (255, 200, 0)) for s in slots}, thick=1)
    for s in slots:
        p = np.int32(s["polygon"]).min(axis=0)
        cv2.putText(vis, s["id"], (int(p[0]), int(p[1]) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.32, WHITE, 1, cv2.LINE_AA)
    cv2.imwrite(f"{a.out}/miesta.jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 88])

    # 3) pás udalostí: auto príde na S37, odíde; S30 po odchode; pickup prechádza cez E3/E4
    def strip(sid, times, pad=40, size=(150, 105)):
        s = next(x for x in slots if x["id"] == sid)
        p = np.array(s["polygon"])
        x1, y1 = np.maximum(p.min(0) - pad, 0)
        x2, y2 = np.minimum(p.max(0) + pad, [frame_w - 1, frame_h - 1])
        tiles = []
        for tt in times:
            tt = round(float(tt), 3)
            f = frame_at(cap, tt, fps)
            r = by_t[tt][sid]
            col = STATE_COL[r["state"]]
            cv2.polylines(f, [np.int32(s["polygon"])], True, col, 2, cv2.LINE_AA)
            crop = cv2.resize(f[y1:y2, x1:x2], size)
            crop = cv2.copyMakeBorder(crop, 22, 18, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(crop, f"{tt:.0f} s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
            cv2.rectangle(crop, (2, size[1] + 22), (size[0] + 2, size[1] + 40), col, -1)
            cv2.putText(crop, STATE_SK[r["state"]], (6, size[1] + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1, cv2.LINE_AA)
            tiles.append(crop)
        return np.hstack(tiles)

    cv2.imwrite(f"{a.out}/udalost_S37.jpg", strip("S37", [60, 64, 68, 73, 85, 94, 97, 110, 124, 130]))
    cv2.imwrite(f"{a.out}/udalost_S30.jpg", strip("S30", [40, 62, 66, 80, 96, 98, 110]))
    cv2.imwrite(f"{a.out}/udalost_E3.jpg", strip("E4", [100, 108, 110, 112, 116, 118, 125], pad=50))

    # 4) pohľad zhora: model z repa si autá pletie s inými predmetmi
    if a.topdown:
        c2 = cv2.VideoCapture(a.topdown)
        c2.set(cv2.CAP_PROP_POS_FRAMES, 40)
        img = c2.read()[1]
        r = YOLO(a.model).predict(img, imgsz=960, conf=0.25, verbose=False)[0]
        for b, cl, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            x1, y1, x2, y2 = map(int, b)
            name = r.names[int(cl)]
            col = (0, 200, 0) if name in ("car", "truck", "bus") else (40, 40, 230)
            cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
            cv2.putText(img, name, (x1, max(10, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1, cv2.LINE_AA)
        cv2.imwrite(f"{a.out}/zhora.jpg", banner(img, "Pohlad zhora: yolov8n vidi 'cell phone' namiesto aut"),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])

    print("hotovo", sorted(os.listdir(a.out)))


if __name__ == "__main__":
    main()
