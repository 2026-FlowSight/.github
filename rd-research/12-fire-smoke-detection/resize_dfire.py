"""Zmenší D-Fire obrázky na dlhšiu stranu 512 px (YOLO labely sú normalizované, ostávajú rovnaké).
Použitie: python resize_dfire.py <dfire_yolo> <dfire512>"""
import os, sys, glob, shutil, cv2
from concurrent.futures import ProcessPoolExecutor
def one(p, SRC=None, DST=None):
    SRC, DST = SRC or os.environ['RS_SRC'], DST or os.environ['RS_DST']
    rel = os.path.relpath(p, SRC); out = os.path.join(DST, rel)
    if os.path.exists(out): return
    im = cv2.imread(p)
    if im is None: return rel
    h, w = im.shape[:2]; s = 512 / max(h, w)
    if s < 1: im = cv2.resize(im, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, im, [cv2.IMWRITE_JPEG_QUALITY, 95])
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    SRC, DST = sys.argv[1], sys.argv[2]
    os.environ['RS_SRC'], os.environ['RS_DST'] = SRC, DST
    for split in ("train", "val", "test"):
        os.makedirs(os.path.join(DST, split), exist_ok=True)
        shutil.copytree(os.path.join(SRC, split, "labels"), os.path.join(DST, split, "labels"), dirs_exist_ok=True)
    imgs = glob.glob(os.path.join(SRC, "*", "images", "*.jpg"))
    with ProcessPoolExecutor(8) as ex:
        bad = [r for r in ex.map(one, imgs, chunksize=64) if r]
    print("hotovo", len(imgs), "chybné:", bad)
