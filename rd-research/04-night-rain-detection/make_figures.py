"""Vyrobí obrázky a doplnkové analýzy do results/ (všetko, čo nie je priamo z eval_detection.py / benchmark.py).

  results/figures/compare_*.jpg            porovnanie metód s detekciami YOLO (umelá tma, noc, dážď)
  results/figures/synth_levels.jpg         ako vyzerajú úrovne umelej tmy
  results/figures/repo_night_gamma_extra_detections.jpg   čo nájde gama navyše na nočnom videu z repozitára
  results/repo_night_video_counts.json     počty detekcií na nočnom videu z repozitára (bez anotácií) + jas a šum
  results/exdark_by_brightness.json        ExDark rozdelený podľa jasu (používa cache predikcií z eval_detection.py)
  results/noise_by_dataset.json            jas a šum (odhad Immerkær) pre jednotlivé typy záberov

  python make_figures.py --frames <uadetrac_frames> --xml <DETRAC-Test-Annotations-XML> --exdark <exdark/data/test> \
      --night-video ../../data/videos/nocne_video_360p.mp4 --cache-dir runs/pred_cache
"""
import argparse
import glob
import json
import os

import cv2
import numpy as np

from enhance import METHODS
from eval_detection import (DEFAULT_MODEL, evaluate, load_yolo, predictions,
                            synth_low_light)
from night_enhance import noise_sigma
from eval_detection import auto_device

VEH = [2, 3, 5, 7]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def tile(model, img, name, device):
    r = model.predict(img, imgsz=512, conf=0.25, classes=VEH, verbose=False, device=device)[0]
    v = cv2.resize(r.plot(labels=False, line_width=2), (480, 270))
    cv2.rectangle(v, (0, 0), (480, 26), (0, 0, 0), -1)
    cv2.putText(v, f"{name}: {len(r.boxes)} vozidiel", (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return v


def bright(img):
    return float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--xml", required=True)
    ap.add_argument("--exdark", required=True)
    ap.add_argument("--night-video", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default=None)
    ap.add_argument("--cache-dir", default="runs/pred_cache")
    a = ap.parse_args()
    from ultralytics import YOLO

    a.device = a.device or auto_device()
    m = YOLO(a.model)
    fig = os.path.join(OUT, "figures")
    os.makedirs(fig, exist_ok=True)

    # 1) porovnanie metód s detekciami
    meths = ["none", "gamma_auto", "clahe", "zero_dce", "sci", "wiener"]
    day = cv2.imread(os.path.join(a.frames, "MVI_40701", "img00011.jpg"))
    sources = {"synth_dark": synth_low_light(day, "dark", 1),
               "detrac_night": cv2.imread(os.path.join(a.frames, "MVI_40792", "img00101.jpg")),
               "detrac_rain": cv2.imread(os.path.join(a.frames, "MVI_40891", "img00201.jpg"))}
    for k, img in sources.items():
        t = [tile(m, METHODS[n](img), n, a.device) for n in meths]
        cv2.imwrite(os.path.join(fig, f"compare_{k}.jpg"), np.vstack([np.hstack(t[:3]), np.hstack(t[3:])]),
                    [cv2.IMWRITE_JPEG_QUALITY, 82])

    # 2) úrovne umelej tmy
    lv = [day] + [synth_low_light(day, l, 1) for l in ("dusk", "dark", "very_dark")]
    g = np.vstack([np.hstack(lv[:2]), np.hstack(lv[2:])])
    cv2.imwrite(os.path.join(fig, "synth_levels.jpg"), cv2.resize(g, (1280, 720)), [cv2.IMWRITE_JPEG_QUALITY, 80])

    # 3) nočné video z repozitára: počty detekcií (bez anotácií) + jas/šum
    cap = cv2.VideoCapture(a.night_video)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % 15 == 0:
            frames.append((i, f))
        i += 1
    cmeths = ["none", "auto", "gamma_auto", "clahe", "he", "zero_dce", "sci", "wiener", "bilateral", "wiener_gamma"]
    from night_enhance import NightEnhancer

    fns = dict(METHODS, auto=NightEnhancer("auto"))
    res = {}
    extra = []
    for k in cmeths:
        counts, confs = [], []
        for j, (fi, f) in enumerate(frames):
            r = m.predict(fns[k](f), imgsz=512, conf=0.25, classes=VEH, verbose=False, device=a.device)[0]
            counts.append(len(r.boxes))
            confs += r.boxes.conf.cpu().tolist()
            if k == "gamma_auto" and len(extra) < 16 and j % 7 == 0 and len(r.boxes) > res["none"]["_c"][j]:
                v = cv2.resize(r.plot(line_width=2), (400, 225))
                cv2.putText(v, f"f{fi} none={res['none']['_c'][j]} gamma={len(r.boxes)}", (5, 215),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                extra.append(v)
        res[k] = dict(mean_vehicles_per_frame=round(float(np.mean(counts)), 3),
                      frames_with_vehicle=int(np.sum(np.array(counts) > 0)),
                      mean_conf=round(float(np.mean(confs)), 3) if confs else 0.0, _c=counts)
    while extra and len(extra) % 4:
        extra.append(np.zeros_like(extra[0]))
    if extra:
        g = np.vstack([np.hstack(extra[k:k + 4]) for k in range(0, len(extra), 4)])
        cv2.imwrite(os.path.join(fig, "repo_night_gamma_extra_detections.jpg"), cv2.resize(g, (1280, 720)),
                    [cv2.IMWRITE_JPEG_QUALITY, 78])
    for v in res.values():
        v.pop("_c")
    json.dump(dict(video=os.path.basename(a.night_video), total_frames=n_total, sampled_every=15,
                   sampled_frames=len(frames),
                   brightness_median=round(float(np.median([bright(f) for _, f in frames])), 1),
                   noise_sigma_median=round(float(np.median([noise_sigma(f) for _, f in frames])), 2),
                   note="bez anotácií: počet detekcií je len orientačný", results=res),
              open(os.path.join(OUT, "repo_night_video_counts.json"), "w"), indent=1, ensure_ascii=False)

    # 4) jas a šum podľa typu záberu
    F = a.frames
    dayimgs = [cv2.imread(p) for p in sorted(glob.glob(F + "/MVI_40701/*.jpg"))[::10] + sorted(glob.glob(F + "/MVI_39211/*.jpg"))[::10]]
    sets = {"detrac_day": dayimgs,
            "synth_dusk": [synth_low_light(x, "dusk", i) for i, x in enumerate(dayimgs)],
            "synth_dark": [synth_low_light(x, "dark", i) for i, x in enumerate(dayimgs)],
            "synth_very_dark": [synth_low_light(x, "very_dark", i) for i, x in enumerate(dayimgs)],
            "detrac_night": [cv2.imread(p) for s in ("MVI_40742", "MVI_40771", "MVI_40792") for p in sorted(glob.glob(f"{F}/{s}/*.jpg"))[::15]],
            "detrac_rain": [cv2.imread(p) for s in ("MVI_40863", "MVI_40891", "MVI_40901") for p in sorted(glob.glob(f"{F}/{s}/*.jpg"))[::15]],
            "exdark": [cv2.imread(p) for p in sorted(glob.glob(a.exdark + "/images/*"))],
            "repo_night_video": [f for _, f in frames]}
    stats = {}
    for k, v in sets.items():
        v = [x for x in v if x is not None]  # v priečinkoch môžu byť aj iné súbory ako obrázky
        b = [bright(x) for x in v]
        n = [noise_sigma(x) for x in v]
        stats[k] = dict(images=len(v), brightness_median=round(float(np.median(b)), 1),
                        noise_sigma_median=round(float(np.median(n)), 2),
                        noise_sigma_p95=round(float(np.percentile(n, 95)), 2),
                        share_above_auto_threshold=round(float(np.mean(np.array(n) > 4.0)), 3))
    json.dump(stats, open(os.path.join(OUT, "noise_by_dataset.json"), "w"), indent=1)

    # 5) ExDark podľa jasu (z cache predikcií eval_detection.py, triedy ako v reporte)
    items = [it for it in load_yolo(a.exdark, {0, 3, 4, 9}, "exdark_night")]
    vcls = {1, 2, 3, 5, 7}
    br = [bright(cv2.imread(it["img"])) for it in items]
    out = {"popis": "ExDark test, YOLOv8n COCO imgsz 512, vozidlá vrátane bicyklov, podľa priemerného jasu (0-255)"}
    for meth in ["none", "gamma_auto", "clahe", "zero_dce", "wiener"]:
        preds, _ = predictions(items, meth, METHODS[meth], m, a.model, 512, a.device, vcls, a.cache_dir)
        for lo, hi in [(0, 15), (15, 30), (30, 60), (60, 256)]:
            idx = [i for i, b in enumerate(br) if lo <= b < hi and len(items[i]["gt"])]
            e = evaluate([items[i] for i in idx], [preds[i] for i in idx])
            out.setdefault(f"{lo}-{hi}", {})[meth] = dict(images=len(idx), gt=int(e["gt"]), mAP50=round(float(e["mAP50"]), 3),
                                                         recall=round(float(e["recall"]), 3))
    json.dump(out, open(os.path.join(OUT, "exdark_by_brightness.json"), "w"), indent=1, ensure_ascii=False)
    print("hotovo")


if __name__ == "__main__":
    main()
