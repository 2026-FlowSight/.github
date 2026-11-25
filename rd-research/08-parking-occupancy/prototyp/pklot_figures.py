"""
Obrázky do reportu z výsledkov pklot_eval.py: graf počtu áut počas dňa a jeden záber s miestami.

Z priečinka prototyp/:
  python pklot_figures.py --day ../data/pklot/ufpr05_2013-02-22 --res ../vysledky/pklot_cely_box \
         --at 12:00 --out ../report/obrazky
"""
import argparse
import csv
import json
import os

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GREEN, RED, ORANGE, WHITE = (60, 190, 60), (50, 50, 230), (0, 200, 255), (255, 255, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--res", required=True)
    ap.add_argument("--at", default="12:00", help="čas záberu HH:MM")
    ap.add_argument("--out", default="../report/obrazky")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    series = list(csv.DictReader(open(f"{a.res}/series.csv", encoding="utf-8")))
    rows = list(csv.DictReader(open(f"{a.res}/slots.csv", encoding="utf-8")))
    det = json.load(open(f"{a.res}/detections.json", encoding="utf-8"))
    gt = json.load(open(f"{a.day}/gt.json", encoding="utf-8"))
    date = gt[0]["ts"][:10]

    # 1) graf počtu áut počas dňa
    hours = [int(r["clock"][:2]) + int(r["clock"][3:5]) / 60 for r in series]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(hours, [int(r["gt"]) for r in series], "k--", lw=1.6, label="Skutočnosť (označenie PKLot)")
    ax.plot(hours, [int(r["naive"]) for r in series], color="#2563eb", lw=2, label="YOLO bez pamäte")
    ax.plot(hours, [int(r["memory"]) for r in series], color="#e8a33d", lw=1.4, label="YOLO s pamäťou (8 s / 30 s)")
    ax.set_xlabel(f"hodina ({date})")
    ax.set_ylabel(f"obsadené miesta (z {len(det['slots'])})")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(f"{a.out}/pklot_den.png", dpi=130)

    # 2) záber v zvolenom čase: farba = stav bez pamäte, oranžová = chyba
    i = min(range(len(series)), key=lambda k: abs(hours[k] - (int(a.at[:2]) + int(a.at[3:]) / 60)))
    t, frame = float(series[i]["t"]), det["dets"][i]
    img = cv2.imread(f"{a.day}/img/{frame['file']}")
    state = {r["slot"]: r for r in rows if abs(float(r["t"]) - t) < 1}
    overlay = img.copy()
    for s in det["slots"]:
        r = state[s["id"]]
        col = ORANGE if r["gt"] != r["naive"] else (RED if r["naive"] == "1" else GREEN)
        cv2.fillPoly(overlay, [np.int32(s["polygon"])], col)
    img = cv2.addWeighted(overlay, 0.45, img, 0.55, 0)
    for x1, y1, x2, y2 in (map(int, b) for b in frame["boxes"]):
        cv2.rectangle(img, (x1, y1), (x2, y2), WHITE, 1)
    img = cv2.copyMakeBorder(img, 34, 0, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
    camera = os.path.basename(os.path.normpath(a.day)).split("_")[0].upper()
    label = f"PKLot {camera} {series[i]['clock']} -cervena obsadene, zelena volne, oranzova chyba"
    cv2.putText(img, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, WHITE, 2, cv2.LINE_AA)
    cv2.imwrite(f"{a.out}/pklot_{a.at.replace(':', '')}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    errors = sum(r["gt"] != r["naive"] for r in state.values())
    print(f"Hotovo -> {a.out} (záber {series[i]['clock']}, chýb: {errors})")


if __name__ == "__main__":
    main()
