"""Meranie výpočtovej náročnosti predspracovaní (ms/snímka, GFLOPs) a YOLO pre porovnanie.

- ms/snímka: medián z --runs opakovaní po zahriatí (warm-up), pre 960x540 a 1920x1080
- GFLOPs: pre SCI a Zero-DCE++ cez torch.utils.flop_counter, pre YOLO cez `thop` (MACs × 2, ako Ultralytics);
  pre klasické operácie len hrubý odhad z počtu operácií na pixel (enhance.macs_per_pixel)

Spúšťať, keď na stroji nebeží nič iné (inak sú časy skreslené).
  python benchmark.py --image <nocny_snimok.jpg> --model yolov8n.pt --out results/benchmark.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import time

import cv2
import numpy as np

import enhance
from enhance import METHODS


def time_fn(fn, img, runs, sync=None):
    for _ in range(3):
        fn(img)
    if sync:
        sync()
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn(img)
        if sync:
            sync()
        ts.append((time.perf_counter() - t0) * 1000)
    return float(np.median(ts))


def cnn_gflops(name, h, w):
    """FLOPs cez torch.utils.flop_counter (počíta konvolúcie a maticové operácie, nie elementwise).
    thop tu dával chybné čísla (SCI: zdieľaný modul sa počítal 2x). Pre Zero-DCE++ sa analyticky
    pripočíta 8 iterácií krivky na plnom rozlíšení (3 operácie na pixel a kanál)."""
    import torch
    from torch.utils.flop_counter import FlopCounterMode

    builder = {"sci": enhance._build_sci, "zero_dce": enhance._build_zdce}[name]
    m = builder()
    with FlopCounterMode(display=False) as fc, torch.no_grad():
        m(torch.rand(1, 3, h, w))
    flops = fc.get_total_flops()
    if name == "zero_dce":
        flops += 8 * 3 * 3 * h * w
    return flops / 1e9, int(sum(p.numel() for p in m.parameters()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--model", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "yolov8n.pt"))
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--device", default=None, help="None = automaticky (CUDA, MPS, CPU)")
    ap.add_argument("--out", default="results/benchmark.csv")
    args = ap.parse_args()

    import torch
    from ultralytics import YOLO

    dev = args.device or enhance._device()
    sync = torch.mps.synchronize if dev == "mps" else torch.cuda.synchronize if dev.startswith("cuda") else None
    base = cv2.imread(args.image)
    sizes = {"960x540": (960, 540), "1920x1080": (1920, 1080)}
    imgs = {k: cv2.resize(base, v) for k, v in sizes.items()}
    mpp = enhance.macs_per_pixel()
    rows = []
    for name, fn in METHODS.items():
        if name == "none":
            continue
        row = dict(method=name)
        for k, img in imgs.items():
            row[f"ms_{k}"] = round(time_fn(fn, img, args.runs if name != "nlmeans" else 5,
                                           sync if name in ("sci", "zero_dce") else None), 2)
        if name in ("sci", "zero_dce"):
            g, p = cnn_gflops(name, 540, 960)
            row.update(gflops_960x540=round(g, 3), params=p, kind="CNN (torch flop_counter)")
        else:
            row.update(gflops_960x540=round(2 * mpp.get(name, 0) * 960 * 540 / 1e9, 3), params=0,
                       kind="klasická (odhad)")
        rows.append(row)
        print(row, flush=True)

    # adaptívny režim night_enhance (odhad šumu na výreze + Wiener len pri šume)
    from night_enhance import NightEnhancer, noise_sigma

    rows.append(dict(method="auto: len odhad šumu (čistá snímka)", kind="klasická",
                     **{f"ms_{k}": round(time_fn(noise_sigma, img, args.runs), 3) for k, img in imgs.items()},
                     gflops_960x540=0.0, params=0))
    # YOLO samotné pre porovnanie (predict = preprocess + inferencia + NMS)
    model = YOLO(args.model)
    for k, img in imgs.items():
        ms = time_fn(lambda x: model.predict(x, imgsz=512, verbose=False, device=dev), img, args.runs)
        rows.append(dict(method=f"YOLO {os.path.basename(args.model)} predict imgsz512 ({k})", **{f"ms_{k}": round(ms, 2)}))
    import copy

    from thop import profile

    net = copy.deepcopy(YOLO(args.model).model).float().cpu().eval()
    yolo_macs, _ = profile(net, inputs=(torch.zeros(1, 3, 512, 512),), verbose=False)
    rows.append(dict(method=f"YOLO {os.path.basename(args.model)} @512 (GFLOPs pri vstupe 512)",
                     gflops_960x540=round(2 * yolo_macs / 1e9, 2),  # thop: MACs x 2
                     params=int(sum(p.numel() for p in model.model.parameters())), kind="CNN (ultralytics)"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    keys = ["method", "kind", "ms_960x540", "ms_1920x1080", "gflops_960x540", "params"]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    print("uložené:", args.out)


if __name__ == "__main__":
    main()
