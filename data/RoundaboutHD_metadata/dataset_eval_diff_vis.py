# visualize_diffs.py
import cv2
import numpy as np
from collections import defaultdict
import os

VIDEO_PATH = "data/RoundaboutHD/imagesc001/video_hd.mp4"  # 720p video
PRED_PATH = "custom_tracking_roundabout.txt"
GT_PATH = "data/RoundaboutHD/imagesc001/SCT/SCT_GT.txt"
OUT_DIR = "diff_frames2"
SCALE = 3  # 720p -> 4K (ak sú predikcie v 720p, inak 1)

IOU_THR = 0.5


def load_tracking_file(path):
    data = defaultdict(list)
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            fid = int(parts[0])
            oid = int(parts[1])
            x1, y1, x2, y2 = map(float, parts[2:6])
            cls = int(parts[6])
            data[fid].append((oid, x1, y1, x2, y2, cls))
    return data


def compute_iou(a, b):
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    if xb <= xa or yb <= ya:
        return 0.0
    inter = (xb - xa) * (yb - ya)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    pred_data = load_tracking_file(PRED_PATH)
    gt_data = load_tracking_file(GT_PATH)

    # Video je 720p, GT je 4K. Ak predikcie sú v 720p, škáluj ich na 4K.
    # Zisti to podľa max súradnice v predikciách.
    max_pred_x = max((b[3] for v in pred_data.values() for b in v), default=0)
    scale = SCALE if max_pred_x < 2000 else 1
    print(f"Max x v predikciách: {max_pred_x:.1f}, scale={scale}")

    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_idx = 0
    saved = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fid = frame_idx + 1  # GT začína od 1

        preds = pred_data.get(fid, [])
        gts = gt_data.get(fid, [])

        if not preds and not gts:
            frame_idx += 1
            continue

        # Zmenši 4K frame na 720p pre vykreslenie (alebo ponechaj)
        # Predikcie škáluj na 4K, ale vykresľujeme na 720p -> predikcie nechaj,
        # GT škáluj dole na 720p (deliť 3).
        vis = frame.copy()

        # GT -> 720p (deliť 3)
        gt_boxes_720 = []
        for (oid, x1, y1, x2, y2, cls) in gts:
            gt_boxes_720.append((oid, x1/3, y1/3, x2/3, y2/3, cls))

        # Predikcie -> ak sú v 720p, nechaj; ak v 4K, deľ 3
        pred_boxes_720 = []
        for (oid, x1, y1, x2, y2, cls) in preds:
            if scale == 3:
                pred_boxes_720.append((oid, x1, y1, x2, y2, cls))  # už 720p
            else:
                pred_boxes_720.append((oid, x1/3, y1/3, x2/3, y2/3, cls))

        # Matching
        gt_matched = [False] * len(gt_boxes_720)
        pred_matched = [False] * len(pred_boxes_720)

        for i, p in enumerate(pred_boxes_720):
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gt_boxes_720):
                if gt_matched[j]:
                    continue
                v = compute_iou((p[1], p[2], p[3], p[4]), (g[1], g[2], g[3], g[4]))
                if v > best_iou:
                    best_iou, best_j = v, j
            if best_iou >= IOU_THR and best_j != -1:
                pred_matched[i] = True
                gt_matched[best_j] = True

        has_diff = (not all(pred_matched)) or (not all(gt_matched))
        if not has_diff:
            frame_idx += 1
            continue

        # Vykresli
        for i, p in enumerate(pred_boxes_720):
            x1, y1, x2, y2 = int(p[1]), int(p[2]), int(p[3]), int(p[4])
            if pred_matched[i]:
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            else:
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(vis, "FP", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        for j, g in enumerate(gt_boxes_720):
            if not gt_matched[j]:
                x1, y1, x2, y2 = int(g[1]), int(g[2]), int(g[3]), int(g[4])
                cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(vis, "FN", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

        out_path = os.path.join(OUT_DIR, f"frame_{fid:05d}.jpg")
        cv2.imwrite(out_path, vis)
        saved += 1

        if saved % 100 == 0:
            print(f"  uložených {saved} snímok...")

        frame_idx += 1

    cap.release()
    print(f"Hotovo. Uložených {saved} snímok s rozdielom do {OUT_DIR}/")


if __name__ == "__main__":
    main()