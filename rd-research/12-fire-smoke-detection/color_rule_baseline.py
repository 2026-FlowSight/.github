"""Klasický baseline bez neurónovej siete: farebné pravidlo pre oheň v priestore YCbCr.

Çelik & Demirel (2009), "Fire detection in video sequences using a generic color model",
Fire Safety Journal 44(2). Pixel je "ohňový", ak:
    Y > Cb,  Cr > Cb,  |Cb - Cr| >= tau,  Y > mean(Y),  Cb < mean(Cb),  Cr > mean(Cr)
Obrázok je "s ohňom", ak ohňové pixely tvoria aspoň p % plochy.

Na testovacej sade D-Fire vypočíta TPR (obrázky s ohňom) a FPR (obrázky bez ohňa a dymu)
pre rôzne p, aby sa dalo porovnať s YOLO. Dym toto pravidlo nedeteguje vôbec.

  python color_rule_baseline.py --test-dir <D-Fire>/test --out results/color_rule.csv
"""
import argparse
import csv
import glob
import os

import cv2
import numpy as np


def fire_fraction(img, tau=40):
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    Y, Cr, Cb = ycc[..., 0], ycc[..., 1], ycc[..., 2]
    m = (Y > Cb) & (Cr > Cb) & (np.abs(Cb - Cr) >= tau) & (Y > Y.mean()) & (Cb < Cb.mean()) & (Cr > Cr.mean())
    return float(m.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-dir", required=True)
    ap.add_argument("--out", default="results/color_rule.csv")
    args = ap.parse_args()
    fr, gt = [], []
    for p in sorted(glob.glob(os.path.join(args.test_dir, "images", "*.jpg"))):
        lab = os.path.join(args.test_dir, "labels", os.path.basename(p)[:-4] + ".txt")
        classes = {int(l.split()[0]) for l in open(lab) if l.strip()}
        img = cv2.imread(p)
        fr.append(fire_fraction(cv2.resize(img, (320, 240))))
        gt.append(classes)
    fr = np.array(fr)
    has_fire = np.array([1 in g for g in gt])
    negative = np.array([not g for g in gt])
    rows = []
    for p in (0.001, 0.005, 0.01, 0.02, 0.05):
        det = fr >= p
        rows.append(dict(min_fire_pixels=p, TPR_fire=round(det[has_fire].mean(), 4),
                         FPR_negatives=round(det[negative].mean(), 4)))
        print(rows[-1])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
