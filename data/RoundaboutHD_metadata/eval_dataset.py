# my_eval.py
import sys
import numpy as np
from collections import defaultdict


def load_tracking_file(path):
    """Načíta formát: frame_id obj_id x1 y1 x2 y2 class_id"""
    data = defaultdict(list)  # frame_id -> [(obj_id, x1, y1, x2, y2, cls)]
    ids = set()
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            frame_id = int(parts[0])
            obj_id = int(parts[1])
            x1, y1, x2, y2 = map(float, parts[2:6])
            cls = int(parts[6])
            data[frame_id].append((obj_id, x1, y1, x2, y2, cls))
            ids.add(obj_id)
    return data, ids


def compute_iou(a, b):
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    if xb <= xa or yb <= ya:
        return 0.0
    inter = (xb - xa) * (yb - ya)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def compute_ap(rec, prec):
    mrec = np.concatenate(([0.0], rec, [1.0]))
    mpre = np.concatenate(([0.0], prec, [0.0]))
    for i in range(mpre.size - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])
    i = np.where(mrec[1:] != mrec[:-1])[0]
    return np.sum((mrec[i + 1] - mrec[i]) * mpre[i + 1])


def evaluate(gt_path, pred_path, iou_thresholds=(0.5, 0.75, 0.9)):
    gt_data, gt_ids = load_tracking_file(gt_path)
    pred_data, pred_ids = load_tracking_file(pred_path)

    gt_total = sum(len(v) for v in gt_data.values())
    pred_total = sum(len(v) for v in pred_data.values())

    print("=" * 60)
    print(f"GT:        {gt_total:6d} detekcií, {len(gt_ids):5d} unique IDs, "
          f"{len(gt_data):5d} snímok")
    print(f"Predikcie: {pred_total:6d} detekcií, {len(pred_ids):5d} unique IDs, "
          f"{len(pred_data):5d} snímok")
    print(f"Rozdiel:   {pred_total - gt_total:+6d} detekcií, "
          f"{len(pred_ids) - len(gt_ids):+5d} IDs")
    print("=" * 60)

    # AP výpočet (per-frame matching, triedy sa ignorujú)
    results = {}
    for thr in iou_thresholds:
        npos = gt_total
        if npos == 0 or pred_total == 0:
            results[thr] = 0.0
            continue

        # Zoznam všetkých predikcií (frame_id, x1, y1, x2, y2) — bez score,
        # lebo tvoj formát score nemá. Zoradíme podľa frame_id.
        preds = []
        for fid, items in pred_data.items():
            for (oid, x1, y1, x2, y2, cls) in items:
                preds.append((fid, x1, y1, x2, y2))

        # GT použité flagy
        gt_used = {fid: [False] * len(items) for fid, items in gt_data.items()}

        tp = np.zeros(len(preds))
        fp = np.zeros(len(preds))

        for i, (fid, x1, y1, x2, y2) in enumerate(preds):
            boxes = gt_data.get(fid, [])
            max_iou, max_idx = 0.0, -1
            for j, (oid, gx1, gy1, gx2, gy2, cls) in enumerate(boxes):
                v = compute_iou((x1, y1, x2, y2), (gx1, gy1, gx2, gy2))
                if v > max_iou:
                    max_iou, max_idx = v, j
            if max_iou >= thr and max_idx != -1 and not gt_used[fid][max_idx]:
                tp[i] = 1
                gt_used[fid][max_idx] = True
            else:
                fp[i] = 1

        tp_cum = np.cumsum(tp)
        fp_cum = np.cumsum(fp)
        rec = tp_cum / npos
        prec = tp_cum / (tp_cum + fp_cum + 1e-9)
        results[thr] = compute_ap(rec, prec)

    print("\n--- Detection metrics (class-agnostic) ---")
    for thr in iou_thresholds:
        print(f"AP@{thr:.2f}: {results[thr]:.4f}")
    print(f"mAP:     {np.mean(list(results.values())):.4f}")

    # Detailnejší rozbor po snímkach
    all_frames = sorted(set(gt_data.keys()) | set(pred_data.keys()))
    if all_frames:
        avg_gt = gt_total / len(all_frames)
        avg_pred = pred_total / len(all_frames)
        print(f"\n--- Per-frame priemer ---")
        print(f"GT na snímku:        {avg_gt:.2f}")
        print(f"Predikcie na snímku: {avg_pred:.2f}")

    return results


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Použitie: python my_eval.py <pred.txt> <gt.txt>")
        sys.exit(1)
    evaluate(sys.argv[2], sys.argv[1])  # gt, pred