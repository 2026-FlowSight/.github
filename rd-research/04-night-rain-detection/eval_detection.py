"""Porovnanie predspracovaní: ako ovplyvnia detekciu vozidiel YOLO v noci / v daždi.

Pre každú metódu z enhance.py:
  snímka -> predspracovanie -> YOLO (COCO, imgsz 512) -> porovnanie s anotáciami
a vypíše mAP50, mAP50-95, recall a precision (pri conf 0.25) zvlášť pre každú
podmienku (night / rainy / cloudy / sunny).

Triedy COCO car(2), motorcycle(3), bus(5), truck(7) sa zlúčia do jednej triedy
"vehicle" (class-agnostic), lebo každý dataset má iné delenie vozidiel.

Podporované datasety (cesty sa zadávajú argumentmi, dáta nie sú v gite):
  detrac : UA-DETRAC (pevná dopravná kamera, 960x540), --detrac-frames + --detrac-xml
  yolo   : ľubovoľný dataset v YOLO formáte (ExDark, DAWN), --yolo-dir, --yolo-classes

Príklad:
  python eval_detection.py --dataset detrac \
      --detrac-frames data/uadetrac_frames --detrac-xml data/DETRAC-Test-Annotations-XML \
      --methods none,auto,gamma_auto,clahe,wiener --out runs/detrac.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import pickle
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

import cv2
import numpy as np

from enhance import METHODS

COCO_VEHICLES = {2, 3, 5, 7}  # car, motorcycle, bus, truck (pre ExDark/DAWN s bicyklami pridať 1)
DEFAULT_MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "yolov8n.pt")

# Úrovne umelého stmavenia: (násobok svetla, šum senzora sigma v 0..255)
DARK_LEVELS = {"dusk": (0.45, 4.0), "dark": (0.22, 6.0), "very_dark": (0.10, 8.0)}


def synth_low_light(img, level, seed):
    """Fyzikálne motivované stmavenie dennej snímky (podľa MAET / Wei et al.):
    linearizácia (sRGB ~ gama 2.2) -> menej fotónov (× k) -> šum (shot + read) -> späť gama -> JPEG.
    Výsledok vyzerá ako podexponovaný nočný záber s šumom, aký robí lacná kamera."""
    k, read_sigma = DARK_LEVELS[level]
    rng = np.random.default_rng(seed)
    lin = (img.astype(np.float32) / 255.0) ** 2.2 * k
    shot = rng.normal(0, 1, lin.shape).astype(np.float32) * np.sqrt(np.maximum(lin, 0) * 0.01)
    read = rng.normal(0, read_sigma / 255.0, lin.shape).astype(np.float32)
    out = np.clip(lin + shot + read, 0, 1) ** (1 / 2.2)
    out = (out * 255.0 + 0.5).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


# ---------------------------------------------------------------------------
# Načítanie anotácií
# ---------------------------------------------------------------------------
def load_detrac(frames_dir, xml_dir, min_size=0):
    """Vráti zoznam položiek {img, cond, seq, gt: Nx4 xyxy, ignore: Mx4 xyxy}."""
    items = []
    for seq_dir in sorted(glob.glob(os.path.join(frames_dir, "MVI_*"))):
        seq = os.path.basename(seq_dir)
        root = ET.parse(os.path.join(xml_dir, seq + ".xml")).getroot()
        cond = root.find("sequence_attribute").get("sence_weather")
        ignore = [
            [float(b.get("left")), float(b.get("top")),
             float(b.get("left")) + float(b.get("width")), float(b.get("top")) + float(b.get("height"))]
            for b in root.find("ignored_region").findall("box")
        ]
        frames = {}
        for fr in root.findall("frame"):
            boxes = []
            for t in fr.find("target_list").findall("target"):
                b = t.find("box")
                l, tp, w, h = (float(b.get(k)) for k in ("left", "top", "width", "height"))
                if min(w, h) >= min_size:
                    boxes.append([l, tp, l + w, tp + h])
            frames[int(fr.get("num"))] = boxes
        for img in sorted(glob.glob(os.path.join(seq_dir, "img*.jpg"))):
            num = int(os.path.basename(img)[3:-4])
            items.append(dict(img=img, cond=cond, seq=seq,
                              gt=np.array(frames.get(num, []), dtype=np.float32).reshape(-1, 4),
                              ignore=np.array(ignore, dtype=np.float32).reshape(-1, 4)))
    return items


def load_yolo(root, vehicle_ids, cond):
    """Dataset v YOLO formáte: root/images/*.jpg + root/labels/*.txt."""
    items = []
    for img in sorted(glob.glob(os.path.join(root, "images", "*"))):
        lab = os.path.join(root, "labels", os.path.splitext(os.path.basename(img))[0] + ".txt")
        if not os.path.exists(lab):
            continue
        im = cv2.imread(img)
        if im is None:
            continue
        H, W = im.shape[:2]
        boxes = []
        for line in open(lab):
            p = line.split()
            if len(p) >= 5 and int(p[0]) in vehicle_ids:
                cx, cy, w, h = (float(v) for v in p[1:5])
                boxes.append([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H])
        items.append(dict(img=img, cond=cond, seq=cond,
                          gt=np.array(boxes, dtype=np.float32).reshape(-1, 4),
                          ignore=np.zeros((0, 4), np.float32)))
    return items


# ---------------------------------------------------------------------------
# Metriky
# ---------------------------------------------------------------------------
def iou_matrix(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (area_a[:, None] + area_b[None, :] - inter + 1e-9)


def center_in(boxes, ignore):
    """Maska boxov, ktorých stred leží v niektorej ignorovanej oblasti."""
    if len(boxes) == 0 or len(ignore) == 0:
        return np.zeros(len(boxes), bool)
    cx = (boxes[:, 0] + boxes[:, 2]) / 2
    cy = (boxes[:, 1] + boxes[:, 3]) / 2
    return ((cx[:, None] >= ignore[None, :, 0]) & (cx[:, None] <= ignore[None, :, 2]) &
            (cy[:, None] >= ignore[None, :, 1]) & (cy[:, None] <= ignore[None, :, 3])).any(1)


def match_with_ignore(det, gt, ignore, thr):
    """Protokol UA-DETRAC (podobne ako 'crowd' v COCO): anotácie so stredom v ignorovanej oblasti
    sa nepočítajú ako GT, a detekcie, ktoré nič nenašli a ležia v ignorovanej oblasti
    (alebo sa trafili do ignorovanej anotácie), sa nepočítajú ako FP.
    Vráti (tp, valid) pre každú detekciu a počet platných GT."""
    ig = center_in(gt, ignore)
    gt_keep, gt_ign = gt[~ig], gt[ig]
    tp = match(det, gt_keep, thr)
    valid = np.ones(len(det), bool)
    fp = tp == 0
    if fp.any() and (len(ignore) or len(gt_ign)):
        drop = center_in(det[fp], ignore)
        if len(gt_ign):
            drop |= match(det[fp], gt_ign, thr) > 0
        idx = np.where(fp)[0]
        valid[idx[drop]] = False
    return tp, valid, len(gt_keep)


def match(det, gt, thr):
    """Greedy priradenie podľa skóre. Vráti pole tp (0/1) pre každú detekciu."""
    tp = np.zeros(len(det), np.float32)
    if len(det) == 0 or len(gt) == 0:
        return tp
    order = np.argsort(-det[:, 4])
    ious = iou_matrix(det[order, :4], gt)
    used = np.zeros(len(gt), bool)
    for i in range(len(order)):
        j = int(np.argmax(np.where(used, -1, ious[i])))
        if ious[i, j] >= thr and not used[j]:
            used[j] = True
            tp[order[i]] = 1
    return tp


def ap_from(scores, tps, n_gt):
    """AP s 101-bodovou interpoláciou (ako COCO)."""
    if n_gt == 0:
        return float("nan")
    if len(scores) == 0:
        return 0.0
    o = np.argsort(-scores)
    tp = np.cumsum(tps[o])
    fp = np.cumsum(1 - tps[o])
    rec = tp / n_gt
    prec = tp / np.maximum(tp + fp, 1e-9)
    prec = np.maximum.accumulate(prec[::-1])[::-1]
    rs = np.linspace(0, 1, 101)
    idx = np.searchsorted(rec, rs, side="left")
    return float(np.mean([prec[i] if i < len(prec) else 0.0 for i in idx]))


def evaluate(items, preds, conf_op=0.25):
    """preds[i] = Nx5 (x1,y1,x2,y2,score). Vráti dict metrík."""
    thrs = np.arange(0.5, 0.96, 0.05)
    per_thr = {t: ([], []) for t in thrs}
    n_gt = 0
    tp_op = fp_op = 0
    for it, det in zip(items, preds):
        gt = it["gt"]
        n_valid = 0
        for t in thrs:
            tp, valid, n_valid = match_with_ignore(det, gt, it["ignore"], t)
            per_thr[t][0].append(det[valid, 4])
            per_thr[t][1].append(tp[valid])
        n_gt += n_valid
        keep = det[det[:, 4] >= conf_op]
        tp, valid, _ = match_with_ignore(keep, gt, it["ignore"], 0.5)
        tp_op += tp[valid].sum()
        fp_op += valid.sum() - tp[valid].sum()
    aps = [ap_from(np.concatenate(s) if s else np.zeros(0), np.concatenate(t) if t else np.zeros(0), n_gt)
           for s, t in per_thr.values()]
    # recall pri precision >= 0.9 (nezávislé od zvoleného prahu conf -> férové porovnanie modelov)
    sc = np.concatenate(per_thr[thrs[0]][0]) if per_thr[thrs[0]][0] else np.zeros(0)
    tpv = np.concatenate(per_thr[thrs[0]][1]) if per_thr[thrs[0]][1] else np.zeros(0)
    r_p90 = 0.0
    if len(sc) and n_gt:
        o = np.argsort(-sc)
        ctp = np.cumsum(tpv[o])
        prec = ctp / np.arange(1, len(o) + 1)
        ok = prec >= 0.9
        r_p90 = float(ctp[ok].max() / n_gt) if ok.any() else 0.0
    return dict(
        images=len(items), gt=n_gt,
        mAP50=aps[0], mAP50_95=float(np.nanmean(aps)),
        recall=tp_op / max(n_gt, 1), precision=tp_op / max(tp_op + fp_op, 1), recall_at_p90=r_p90,
    )


# ---------------------------------------------------------------------------
def predict(model, img, imgsz, device, vehicle_classes=COCO_VEHICLES):
    r = model.predict(img, imgsz=imgsz, conf=0.001, iou=0.6, max_det=300, verbose=False, device=device)[0]
    b = r.boxes
    if b is None or len(b) == 0:
        return np.zeros((0, 5), np.float32)
    cls = b.cls.cpu().numpy().astype(int)
    keep = np.isin(cls, list(vehicle_classes))
    xyxy = b.xyxy.cpu().numpy()[keep]
    conf = b.conf.cpu().numpy()[keep]
    return np.concatenate([xyxy, conf[:, None]], 1).astype(np.float32)


def class_agnostic_nms(det, iou=0.7):
    """Po zlúčení tried car/bus/truck môže jedno auto mať 2 boxy (car aj truck)."""
    if len(det) == 0:
        return det
    order = np.argsort(-det[:, 4])
    det = det[order]
    keep = []
    supp = np.zeros(len(det), bool)
    ious = iou_matrix(det[:, :4], det[:, :4])
    for i in range(len(det)):
        if supp[i]:
            continue
        keep.append(i)
        supp |= ious[i] > iou
    return det[keep]



def auto_device():
    """CUDA (Jetson/PC) -> MPS (Mac) -> CPU. Ultralytics s device=None na Macu použije CPU, preto vlastný výber."""
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def predictions(items, name, fn, model, model_path, imgsz, device, vcls, cache_dir):
    """Predspracovanie `fn` + YOLO na všetkých položkách, s cache na disku (podľa modelu, metódy a snímok)."""
    key = hashlib.md5(json.dumps([os.path.abspath(model_path), name, imgsz, sorted(vcls),
                                  [(it["img"], it.get("dark")) for it in items]]).encode()).hexdigest()[:16]
    cache = os.path.join(cache_dir, f"{name}_{key}.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    preds, t_enh = [], []
    for k, it in enumerate(items):
        img = cv2.imread(it["img"])
        if img is None:
            raise SystemExit(f"neviem načítať {it['img']} (poškodený súbor?)")
        if it.get("dark"):
            img = synth_low_light(img, it["dark"], seed=k)
        t0 = time.perf_counter()
        img2 = fn(img)
        t_enh.append(time.perf_counter() - t0)
        preds.append(class_agnostic_nms(predict(model, img2, imgsz, device, vcls)))
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache, "wb") as f:
        pickle.dump((preds, t_enh), f)
    return preds, t_enh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["detrac", "yolo"], required=True)
    ap.add_argument("--detrac-frames")
    ap.add_argument("--detrac-xml")
    ap.add_argument("--yolo-dir")
    ap.add_argument("--yolo-classes", help="čiarkou oddelené ID tried vozidiel v datasete")
    ap.add_argument("--cond", default="night", help="názov podmienky pre YOLO dataset")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--imgsz", type=int, default=512)
    ap.add_argument("--device", default=None, help="None = automaticky (CUDA, MPS, CPU)")
    ap.add_argument("--cache-dir", default="runs/pred_cache",
                    help="predikcie sa uložia sem, opakované vyhodnotenie s inou metrikou je potom okamžité")
    ap.add_argument("--every", type=int, default=1, help="použi len každú N-tú snímku")
    ap.add_argument("--synthetic-dark", default="",
                    help="čiarkou oddelené úrovne (dusk,dark,very_dark): denné snímky sa umelo stmavia")
    ap.add_argument("--only-cond", default="", help="napr. sunny,cloudy: použi len tieto podmienky")
    ap.add_argument("--only-seq", default="", help="čiarkou oddelené sekvencie UA-DETRAC (napr. testovacie lokality)")
    ap.add_argument("--vehicle-classes", default="2,3,5,7",
                    help="ID tried modelu, ktoré sú vozidlá (COCO: 2,3,5,7; dotrénovaný 1-triedny model: 0)")
    ap.add_argument("--tag", default="", help="pridá sa k názvu metódy vo výsledkoch (napr. názov modelu)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from ultralytics import YOLO

    if args.dataset == "detrac":
        items = load_detrac(args.detrac_frames, args.detrac_xml)
    else:
        items = load_yolo(args.yolo_dir, {int(c) for c in args.yolo_classes.split(",")}, args.cond)
    if args.only_seq:
        items = [it for it in items if it["seq"] in args.only_seq.split(",")]
    if args.only_cond:
        items = [it for it in items if it["cond"] in args.only_cond.split(",")]
    items = items[:: args.every]
    if args.synthetic_dark:
        base = items
        items = [dict(it, cond="day_original", dark=None) for it in base]
        for lvl in args.synthetic_dark.split(","):
            items += [dict(it, cond=f"synth_{lvl}", dark=lvl) for it in base]
    print(f"{len(items)} snímok, {sum(len(i['gt']) for i in items)} anotovaných vozidiel")

    args.device = args.device or auto_device()
    model = YOLO(args.model)
    vcls = {int(c) for c in args.vehicle_classes.split(",")}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)
    rows = []
    for name in args.methods.split(","):
        if name == "auto":  # adaptívny režim z night_enhance.py (Wiener len pri vysokom šume)
            from night_enhance import NightEnhancer
            fn = NightEnhancer("auto")
        else:
            fn = METHODS[name]
        preds, t_enh = predictions(items, name, fn, model, args.model, args.imgsz, args.device, vcls, args.cache_dir)
        by_cond = defaultdict(list)
        for i, it in enumerate(items):
            by_cond[it["cond"]].append(i)
        if "sunny" in by_cond and "cloudy" in by_cond:  # spoločné vyhodnotenie všetkých denných snímok
            by_cond["day"] = by_cond["sunny"] + by_cond["cloudy"]
        for cond, idx in sorted(by_cond.items()):
            m = evaluate([items[i] for i in idx], [preds[i] for i in idx])
            m.update(method=name + args.tag, cond=cond, enhance_ms=1000 * float(np.median([t_enh[i] for i in idx])))
            rows.append(m)
            print(f"{name:14s} {cond:7s} mAP50={m['mAP50']:.3f} mAP50-95={m['mAP50_95']:.3f} "
                  f"R={m['recall']:.3f} P={m['precision']:.3f} R@P90={m['recall_at_p90']:.3f}  (enh {m['enhance_ms']:.1f} ms)", flush=True)
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["method", "cond", "images", "gt", "mAP50", "mAP50_95",
                                              "recall", "precision", "recall_at_p90", "enhance_ms"])
            w.writeheader()
            w.writerows(rows)
    print("uložené:", args.out)


if __name__ == "__main__":
    main()
