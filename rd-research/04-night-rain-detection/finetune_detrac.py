"""Experiment "dotrénovanie YOLO na nočných / daždivých dátach" (UA-DETRAC, pevná dopravná kamera).

Delenie podľa LOKALITY kamery (nie podľa snímok), aby test nebol na tých istých miestach:
  trénovanie  night+rain: noc B (MVI_4076x), noc C (MVI_4077x), dážď G (MVI_4090x)
  trénovanie  day (kontrola): všetky denné sekvencie (sunny + cloudy), rovnaký počet snímok
  test:       noc A (MVI_4074x), noc D (MVI_4079x), dážď E (MVI_4086x), dážď F (MVI_4089x)

Kontrolný model natrénovaný na dennych snímkach ukáže, koľko zlepšenia je len z prispôsobenia
na UA-DETRAC (štýl anotácií, uhol kamery) a koľko je skutočne z nočných/daždivých dát.

Oblasti "ignored_region" z anotácií sa v trénovacích snímkach zamaskujú sivou farbou
(sú tam neoznačené autá, ktoré by sa inak učili ako pozadie) a anotácie so stredom v nich sa vynechajú.
Pozor: ako validačná množina pri tréningu slúžia testovacie lokality -> vyhodnocuje sa `last.pt`
(bez výberu), `best.pt` je vybraný podľa testu a jeho čísla by boli nadhodnotené.

  python finetune_detrac.py prepare --frames <...>/frames --xml <...>/DETRAC-Test-Annotations-XML --out <dataset_dir>
  python finetune_detrac.py train --data <dataset_dir>/night_rain.yaml --name ft_night_rain
"""
from __future__ import annotations

import argparse
import glob
import os
import random
import xml.etree.ElementTree as ET

import cv2

TRAIN_NIGHT_RAIN = ["MVI_40761", "MVI_40762", "MVI_40763",  # noc B
                    "MVI_40771", "MVI_40772", "MVI_40773", "MVI_40774", "MVI_40775",  # noc C
                    "MVI_40901", "MVI_40902", "MVI_40903", "MVI_40904", "MVI_40905"]  # dážď G
TRAIN_DAY = ["MVI_39031", "MVI_39211", "MVI_39311", "MVI_39371",  # sunny
             "MVI_40701", "MVI_40711", "MVI_40851", "MVI_40852"]  # cloudy
TEST = ["MVI_40742", "MVI_40743", "MVI_40792", "MVI_40793",  # noc A, D
        "MVI_40863", "MVI_40864", "MVI_40891", "MVI_40892"]  # dážď E, F


def convert(seq, frames_dir, xml_dir, out_img, out_lab):
    root = ET.parse(os.path.join(xml_dir, seq + ".xml")).getroot()
    ignore = [[float(b.get(k)) for k in ("left", "top", "width", "height")]
              for b in root.find("ignored_region").findall("box")]
    boxes = {}
    for fr in root.findall("frame"):
        boxes[int(fr.get("num"))] = [[float(t.find("box").get(k)) for k in ("left", "top", "width", "height")]
                                     for t in fr.find("target_list").findall("target")]
    n = 0
    for p in sorted(glob.glob(os.path.join(frames_dir, seq, "img*.jpg"))):
        num = int(os.path.basename(p)[3:-4])
        img = cv2.imread(p)
        H, W = img.shape[:2]
        for l, t, w, h in ignore:
            cv2.rectangle(img, (int(l), int(t)), (int(l + w), int(t + h)), (114, 114, 114), -1)
        stem = f"{seq}_{num:05d}"
        cv2.imwrite(os.path.join(out_img, stem + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        with open(os.path.join(out_lab, stem + ".txt"), "w") as f:
            for l, t, w, h in boxes.get(num, []):
                cx, cy = l + w / 2, t + h / 2
                if any(il <= cx <= il + iw and it <= cy <= it + ih for il, it, iw, ih in ignore):
                    continue  # auto v zamaskovanej (sivej) oblasti -> nesmie byť v labeloch
                f.write(f"0 {(l + w / 2) / W:.6f} {(t + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}\n")
        n += 1
    return n


def prepare(args):
    random.seed(0)
    for split, seqs in [("train_night_rain", TRAIN_NIGHT_RAIN), ("train_day", TRAIN_DAY), ("test", TEST)]:
        img_dir = os.path.join(args.out, split, "images")
        lab_dir = os.path.join(args.out, split, "labels")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lab_dir, exist_ok=True)
        n = sum(convert(s, args.frames, args.xml, img_dir, lab_dir) for s in seqs)
        print(split, n, "snímok")
    # vyrovnať počet: night_rain zmenšíme na veľkosť day (férové porovnanie)
    day = sorted(glob.glob(os.path.join(args.out, "train_day", "images", "*.jpg")))
    nr = sorted(glob.glob(os.path.join(args.out, "train_night_rain", "images", "*.jpg")))
    random.shuffle(nr)
    lists = {"night_rain": sorted(nr[: len(day)]), "day": day}
    for name, files in lists.items():
        lst = os.path.join(args.out, f"{name}.txt")
        open(lst, "w").write("\n".join(files) + "\n")
        open(os.path.join(args.out, f"{name}.yaml"), "w").write(
            f"path: {os.path.abspath(args.out)}\ntrain: {name}.txt\nval: test/images\nnames:\n  0: vehicle\n")
        print(name, len(files), "trénovacích snímok")


def train(args):
    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(data=args.data, imgsz=512, epochs=args.epochs, batch=16, device=args.device,
                single_cls=True, lr0=0.002, warmup_epochs=1, mosaic=1.0, close_mosaic=3,
                hsv_v=0.5, deterministic=False, plots=True, patience=100,
                project=os.path.abspath(args.project), name=args.name, exist_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--frames", required=True)
    p.add_argument("--xml", required=True)
    p.add_argument("--out", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", required=True)
    t.add_argument("--name", required=True)
    t.add_argument("--model", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "yolov8n.pt"))
    t.add_argument("--epochs", type=int, default=15)
    t.add_argument("--device", default=None)
    t.add_argument("--project", default="runs")
    a = ap.parse_args()
    prepare(a) if a.cmd == "prepare" else train(a)
