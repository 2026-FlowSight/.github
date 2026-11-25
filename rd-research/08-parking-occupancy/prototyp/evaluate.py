"""
Vyhodnotenie presnosti počítania voči ručne anotovanej pravde.

gt.csv: video_s,count            (napr. anotácia každých 30 s)
pred.csv: výstup parking_occupancy.py

python evaluate.py --pred occupancy.csv --gt gt.csv
"""
import argparse
import csv


def load(path, tcol, ccol):
    with open(path, encoding="utf-8") as f:
        return [(float(r[tcol]), int(r[ccol])) for r in csv.DictReader(f)]


def nearest(series, t):
    return min(series, key=lambda x: abs(x[0] - t))[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gt", required=True)
    a = ap.parse_args()
    pred = load(a.pred, "video_s", "occupied")
    gt = load(a.gt, "video_s", "count")
    errs = [nearest(pred, t) - c for t, c in gt]
    n = len(errs)
    mae = sum(abs(e) for e in errs) / n
    exact = sum(e == 0 for e in errs) / n
    within1 = sum(abs(e) <= 1 for e in errs) / n
    total_gt = sum(c for _, c in gt)
    count_acc = 1 - sum(abs(e) for e in errs) / max(1, total_gt)
    print(f"vzoriek: {n}")
    print(f"MAE (autá):            {mae:.2f}")
    print(f"bias (pred - gt):      {sum(errs)/n:+.2f}")
    print(f"presne trafené:        {exact:.1%}")
    print(f"chyba <= 1 auto:       {within1:.1%}")
    print(f"presnosť počtu 1-ΣE/ΣN: {count_acc:.1%}")


if __name__ == "__main__":
    main()
