"""Vyrobí syntetické testovacie video "statický obrázok ohňa na pevnej kamere".

Do záberu pevnej kamery (RoundaboutHD z repozitára) sa vloží statická fotka ohňa
(testovací obrázok z D-Fire s veľkým plameňom) s rámčekom, ako billboard.
Každá snímka dostane šum sigma=2, aby to nebol dokonale statický obrázok.
POZOR: je to digitálne vložený obrázok – skutočný plagát by mal aj zmeny osvetlenia,
odlesky, autoexpozíciu a autá idúce popred neho. Je to teda optimistický test.

  python make_synth_poster.py --poster <D-Fire>/test/images/WEB10606.jpg \
      --video ../../data/videos/RoundaboutHD/kamera1_hd_1min.mp4 --out data/SYNTH_static_fire_poster_roundabout.mp4
"""
import argparse

import cv2
import numpy as np

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poster", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=380)
    a = ap.parse_args()
    poster = cv2.imread(a.poster)
    poster = cv2.resize(poster, (a.width, int(a.width * poster.shape[0] / poster.shape[1])))
    cap = cv2.VideoCapture(a.video)
    fps, W, H = cap.get(cv2.CAP_PROP_FPS), int(cap.get(3)), int(cap.get(4))
    out = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    rng = np.random.default_rng(0)
    x0, y0 = 60, 40
    while True:
        ok, f = cap.read()
        if not ok:
            break
        pp = np.clip(poster.astype(np.float32) + rng.normal(0, 2, poster.shape), 0, 255).astype(np.uint8)
        f[y0:y0 + pp.shape[0], x0:x0 + pp.shape[1]] = pp
        cv2.rectangle(f, (x0 - 4, y0 - 4), (x0 + pp.shape[1] + 4, y0 + pp.shape[0] + 4), (40, 40, 40), 4)
        out.write(f)
    out.release()
    print("uložené:", a.out)
