"""Zlepšenie nočného / daždivého záberu pre YOLO (výstup úlohy 04).

Robí to, čo odporúčajú namerané výsledky (README.md):
  * odhadne ŠUM snímky (Immerkær 1996, ~0.25 ms na výreze),
  * režim `auto` (predvolený): ak je šum vysoký (sigma > --noise-threshold, typicky tmavá scéna
    s vysokým gainom kamery), použije Wienerov filter (+0,17 mAP50 pri umelej tme *dark*),
    inak snímku NECHÁ TAK. Zosvetľovanie (gama, SCI, Zero-DCE) sa nepoužíva, lebo takmer vo všetkých
    anotovaných testoch detekciu zhoršilo (aj na najtmavších snímkach ExDark; výnimka: mierne DAWN),
  * dá sa vynútiť ľubovoľná metóda z enhance.py (`--method clahe` a pod.),
  * voliteľne pustí YOLO na originál aj upravenú snímku a uloží porovnanie vedľa seba.

Príklady:
  # jeden obrázok -> upravený obrázok
  python night_enhance.py --source noc.jpg --out noc_enh.jpg

  # video -> upravené video + porovnanie s detekciami (vľavo originál, vpravo upravené)
  python night_enhance.py --source nocne_video.mp4 --out out.mp4 --compare --model yolov8n.pt

  # vynútiť konkrétnu metódu na každú snímku
  python night_enhance.py --source x.jpg --out y.jpg --method clahe

V kóde pipeline:
  from night_enhance import NightEnhancer
  enh = NightEnhancer()          # auto: Wiener len pri vysokom šume
  frame = enh(frame)             # pred yolo.predict(frame)
"""
from __future__ import annotations

import argparse
import os
import time

import cv2
import numpy as np

from enhance import METHODS

VEHICLES = [2, 3, 5, 7]


def noise_sigma(img, crop=(480, 270)) -> float:
    """Odhad smerodajnej odchýlky šumu (Immerkær 1996) na strednom výreze snímky.
    Čisté zábery (deň, osvetlená noc, kompresia) ~0.5-2; podexponovaný záber s gainom 8-20."""
    h, w = img.shape[:2]
    cw, ch = min(crop[0], w), min(crop[1], h)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    g = cv2.cvtColor(img[y0:y0 + ch, x0:x0 + cw], cv2.COLOR_BGR2GRAY).astype(np.float32)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    c = cv2.filter2D(g, -1, k)[1:-1, 1:-1]
    return float(np.sqrt(np.pi / 2) * np.abs(c).mean() / 6)


class NightEnhancer:
    """method='auto': Wiener, ak noise_sigma > noise_threshold, inak bez zmeny.
    Iná hodnota method = tá metóda z enhance.py na každú snímku."""

    def __init__(self, method: str = "auto", noise_threshold: float = 4.0):
        self.method = method
        self.noise_threshold = noise_threshold
        self.fn = METHODS["wiener"] if method == "auto" else METHODS[method]

    def decide(self, img):
        """Vráti (použiť_metódu, názov, šum)."""
        if self.method != "auto":
            return True, self.method, None
        s = noise_sigma(img)
        return s > self.noise_threshold, "wiener", s

    def __call__(self, img):
        use, _, _ = self.decide(img)
        return self.fn(img) if use else img



def auto_device():
    """CUDA (Jetson/PC) -> MPS (Mac) -> CPU. Ultralytics s device=None na Macu použije CPU, preto vlastný výber."""
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def draw(img, model, imgsz):
    r = model.predict(img, imgsz=imgsz, conf=0.25, classes=VEHICLES, verbose=False, device=auto_device())[0]
    vis = r.plot(labels=False, line_width=2)
    n = 0 if r.boxes is None else len(r.boxes)
    return vis, n


def label(img, text):
    cv2.rectangle(img, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(img, text, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return img


def process(frame, enh, model, imgsz, compare):
    t0 = time.perf_counter()
    use, name, sigma = enh.decide(frame)
    out = enh.fn(frame) if use else frame
    ms = (time.perf_counter() - t0) * 1000
    if not compare:
        return out
    a, na = draw(frame, model, imgsz)
    b, nb = draw(out, model, imgsz)
    stxt = "" if sigma is None else f" (sum {sigma:.1f})"
    label(a, f"original: {na} vozidiel")
    label(b, f"{name if use else 'bez zmeny'}{stxt}: {nb} vozidiel, +{ms:.1f} ms")
    return np.hstack([a, b])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="obrázok alebo video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--method", default="auto", choices=["auto"] + list(METHODS))
    ap.add_argument("--noise-threshold", type=float, default=4.0, help="pre auto: Wiener pri šume nad touto hodnotou")
    ap.add_argument("--compare", action="store_true", help="uložiť porovnanie s detekciami YOLO")
    ap.add_argument("--model", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "yolov8n.pt"))
    ap.add_argument("--imgsz", type=int, default=512)
    ap.add_argument("--max-width", type=int, default=1280, help="zmenšiť veľké videá (4K)")
    ap.add_argument("--max-seconds", type=float, default=None)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    enh = NightEnhancer(args.method, args.noise_threshold)
    model = None
    if args.compare:
        from ultralytics import YOLO
        model = YOLO(args.model)

    def fit(img):
        if img.shape[1] > args.max_width:
            s = args.max_width / img.shape[1]
            img = cv2.resize(img, (int(img.shape[1] * s) // 2 * 2, int(img.shape[0] * s) // 2 * 2))
        return img

    ext = os.path.splitext(args.source)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp"):
        img = cv2.imread(args.source)
        if img is None:
            raise SystemExit(f"neviem načítať obrázok {args.source}")
        img = fit(img)
        if not cv2.imwrite(args.out, process(img, enh, model, args.imgsz, args.compare)):
            raise SystemExit(f"neviem zapísať {args.out}")
        print("uložené:", args.out)
        return

    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        raise SystemExit(f"neviem otvoriť video {args.source}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 25.0
    writer = None
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok or (args.max_seconds and i / fps > args.max_seconds):
            break
        out = process(fit(frame), enh, model, args.imgsz, args.compare)
        if writer is None:
            writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (out.shape[1], out.shape[0]))
            if not writer.isOpened():
                raise SystemExit(f"neviem zapísať video {args.out}")
        writer.write(out)
        i += 1
    cap.release()
    if writer:
        writer.release()
    print(f"uložené: {args.out} ({i} snímok)")


if __name__ == "__main__":
    main()
