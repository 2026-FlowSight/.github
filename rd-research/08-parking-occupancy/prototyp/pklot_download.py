"""
Stiahne jeden deň z jednej kamery datasetu PKLot (verzia Voxel51 na Hugging Face).

Z priečinka prototyp/:
  python pklot_download.py --source ufpr05 --date 2013-02-22 --out ../data/pklot
  python pklot_download.py --list           # ktoré dni majú najviac fotiek a zmien

Výstup: <out>/<source>_<date>/gt.json a <out>/<source>_<date>/img/*.jpg
Najprv sa stiahne samples.json so všetkými označeniami (~270 MB, len raz), potom fotky daného dňa (~40 MB).
"""
import argparse
import collections
import json
import os
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://huggingface.co/datasets/Voxel51/PKLot/resolve/main/"


def download(url, path):
    if not os.path.exists(path):
        tmp = path + ".part"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.replace(tmp, path)
    return path


def load_samples(out):
    path = download(BASE + "samples.json", os.path.join(out, "samples.json"))
    return json.load(open(path, encoding="utf-8"))["samples"]


def by_day(samples):
    days = collections.defaultdict(list)
    for s in samples:
        days[(s["source"], s["date"]["$date"][:10])].append(s)
    for v in days.values():
        v.sort(key=lambda s: s["parking_timestamp"]["$date"])
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="ufpr05", choices=["ufpr04", "ufpr05", "pucpr"])
    ap.add_argument("--date", default="2013-02-22")
    ap.add_argument("--out", default="../data/pklot")
    ap.add_argument("--list", action="store_true", help="vypíše vhodné dni a skončí")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    days = by_day(load_samples(a.out))

    if a.list:
        for (src, date), v in sorted(days.items(), key=lambda kv: -len(kv[1]))[:20]:
            occ = [sum(p.get("occupancy_status") == "occupied" for p in s["parking_spaces"]["polylines"]) for s in v]
            print(f"{src:7s} {date}  fotiek {len(v):3d}  obsadené {min(occ)}–{max(occ)}  {v[0]['weather']['label']}")
        return

    day = days[(a.source, a.date)]
    if not day:
        raise SystemExit(f"Deň {a.source} {a.date} v datasete nie je. Skús --list.")
    folder = os.path.join(a.out, f"{a.source}_{a.date}")
    os.makedirs(os.path.join(folder, "img"), exist_ok=True)

    gt = [{"file": s["filepath"], "ts": s["parking_timestamp"]["$date"], "weather": s["weather"]["label"],
           "spaces": [{"id": p["space_id"], "pts": p["points"][0], "occ": p.get("occupancy_status") == "occupied"}
                      for p in s["parking_spaces"]["polylines"]]} for s in day]
    json.dump(gt, open(os.path.join(folder, "gt.json"), "w", encoding="utf-8"))

    with ThreadPoolExecutor(12) as ex:
        list(ex.map(lambda g: download(BASE + g["file"], os.path.join(folder, "img", os.path.basename(g["file"]))), gt))
    print(f"Hotovo: {len(gt)} fotiek, {len(gt[0]['spaces'])} miest -> {folder}")


if __name__ == "__main__":
    main()
