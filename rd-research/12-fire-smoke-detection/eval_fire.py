"""Vyhodnotenie modelu ohňa/dymu na testovacej sade D-Fire (4 306 obrázkov, 2 005 bez ohňa aj dymu).

Vypíše / uloží:
  1. Box metriky (Ultralytics val): mAP50, mAP50-95, precision, recall pre smoke / fire / spolu
  2. Metriky na úrovni obrázka (to, čo zaujíma mesto: "spustí sa poplach, alebo nie?"),
     pre rôzne prahy confidence:
       TPR  = podiel obrázkov s ohňom/dymom, kde model niečo našiel
       FPR  = podiel NEGATÍVNYCH obrázkov (bez ohňa aj dymu), kde model niečo našiel (= falošný poplach)
     aj podľa zdroja obrázka (AoF = zábery z D-Fire (vrátane CCTV), WEB = internet, PublicDataset = HPWREN/FESB/FireNet)
  3. Galériu falošných poplachov s najvyšším skóre (čo model mýli s ohňom)
  4. Rýchlosť inferencie (ms/obrázok) na zvolenom zariadení

  python eval_fire.py --model weights/fire_yolov8n_512.pt --data dfire512.yaml \
      --test-dir <D-Fire>/test --out results/
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

import cv2
import numpy as np

NAMES = {0: "smoke", 1: "fire"}


def source_of(name):
    for p in ("AoF", "WEB", "PublicDataset"):
        if name.startswith(p):
            return p
    return "other"



def auto_device():
    """CUDA (Jetson/PC) -> MPS (Mac) -> CPU. Ultralytics s device=None na Macu použije CPU, preto vlastný výber."""
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True, help="YAML datasetu (pre box metriky na split=test)")
    ap.add_argument("--test-dir", required=True, help="priečinok s images/ a labels/")
    ap.add_argument("--imgsz", type=int, default=512)
    ap.add_argument("--device", default=None, help="None = automaticky (CUDA, MPS, CPU)")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "figures"), exist_ok=True)

    from ultralytics import YOLO

    args.device = args.device or auto_device()
    model = YOLO(args.model)

    # 1. Box metriky
    m = model.val(data=args.data, split="test", imgsz=args.imgsz, batch=32, device=args.device,
                  plots=True, project=os.path.abspath(args.out), name="val_test", exist_ok=True, verbose=False)
    box = dict(all=dict(P=float(m.box.mp), R=float(m.box.mr), mAP50=float(m.box.map50), mAP50_95=float(m.box.map)))
    for i, c in enumerate(m.box.ap_class_index):
        box[NAMES[int(c)]] = dict(P=float(m.box.p[i]), R=float(m.box.r[i]),
                                  mAP50=float(m.box.ap50[i]), mAP50_95=float(m.box.ap[i]))
    print(json.dumps(box, indent=1))

    # 2. Úroveň obrázka
    imgs = sorted(glob.glob(os.path.join(args.test_dir, "images", "*.jpg")))
    rec = []
    times = []
    for k, p in enumerate(imgs):
        lab = os.path.join(args.test_dir, "labels", os.path.basename(p)[:-4] + ".txt")
        classes = {int(l.split()[0]) for l in open(lab) if l.strip()} if os.path.exists(lab) else set()
        img = cv2.imread(p)
        t0 = time.perf_counter()
        r = model.predict(img, imgsz=args.imgsz, conf=0.05, verbose=False, device=args.device)[0]
        if k >= 5:
            times.append((time.perf_counter() - t0) * 1000)
        cls = r.boxes.cls.cpu().numpy().astype(int) if r.boxes is not None else np.zeros(0, int)
        conf = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.zeros(0)
        rec.append(dict(img=p, src=source_of(os.path.basename(p)), gt=classes,
                        max_any=float(conf.max()) if len(conf) else 0.0,
                        max_fire=float(conf[cls == 1].max()) if (cls == 1).any() else 0.0,
                        max_smoke=float(conf[cls == 0].max()) if (cls == 0).any() else 0.0))

    pos = [r for r in rec if r["gt"]]
    neg = [r for r in rec if not r["gt"]]
    fire_pos = [r for r in rec if 1 in r["gt"]]
    smoke_pos = [r for r in rec if 0 in r["gt"]]
    table = []
    for thr in (0.1, 0.25, 0.4, 0.5, 0.6):
        row = dict(conf=thr,
                   TPR_any=np.mean([r["max_any"] >= thr for r in pos]),
                   TPR_fire=np.mean([r["max_fire"] >= thr for r in fire_pos]),
                   TPR_smoke=np.mean([r["max_smoke"] >= thr for r in smoke_pos]),
                   FPR_any=np.mean([r["max_any"] >= thr for r in neg]),
                   FPR_fire=np.mean([r["max_fire"] >= thr for r in neg]),
                   FPR_smoke=np.mean([r["max_smoke"] >= thr for r in neg]))
        for s in ("AoF", "WEB", "PublicDataset"):
            ns = [r for r in neg if r["src"] == s]
            row[f"FPR_{s}"] = np.mean([r["max_any"] >= thr for r in ns]) if ns else float("nan")
        table.append({k: (round(float(v), 4) if not isinstance(v, str) else v) for k, v in row.items()})
    for t in table:
        print(t)

    # 3. Galéria falošných poplachov (najvyššie skóre na negatívnych obrázkoch)
    worst = sorted(neg, key=lambda r: -r["max_any"])[:16]
    tiles = []
    for r in worst:
        res = model.predict(r["img"], imgsz=args.imgsz, conf=0.25, verbose=False, device=args.device)[0]
        t = cv2.resize(res.plot(line_width=2), (320, 240))
        cv2.putText(t, f"{r['src']} {r['max_any']:.2f}", (5, 232), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        tiles.append(t)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)])
    cv2.imwrite(os.path.join(args.out, "figures", "false_positives_top16.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # Galéria správnych detekcií (náhodné pozitívne obrázky)
    rng = np.random.default_rng(0)
    tiles = []
    for i in rng.choice(len(pos), 8, replace=False):
        res = model.predict(pos[i]["img"], imgsz=args.imgsz, conf=0.25, verbose=False, device=args.device)[0]
        tiles.append(cv2.resize(res.plot(line_width=2), (320, 240)))
    grid = np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, 8, 4)])
    cv2.imwrite(os.path.join(args.out, "figures", "detections_examples.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])

    summary = dict(model=os.path.basename(args.model), imgsz=args.imgsz, device=args.device,
                   test_images=len(rec), positives=len(pos), negatives=len(neg),
                   box_metrics=box, image_level=table,
                   predict_ms_median=round(float(np.median(times)), 2),
                   predict_ms_p95=round(float(np.percentile(times, 95)), 2))
    with open(os.path.join(args.out, "eval_test.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print("uložené:", os.path.join(args.out, "eval_test.json"))


if __name__ == "__main__":
    main()
