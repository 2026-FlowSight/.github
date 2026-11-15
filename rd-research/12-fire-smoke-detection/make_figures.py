"""Vyrobí ukážkový obrázok results/figures/video_demo.jpg zo snímok videí, ktoré uložil detect_fire_video.py,
a tabuľky do README (markdown) zo súhrnov *_summary.json.

  python make_figures.py --det-dir runs/demo_15fps --summary-dir results/videos/deploy_2fps
"""
import argparse
import csv
import glob
import json
import os

import cv2
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "figures")
SHOTS = [("Pexels_4116863_burning_apartment", 3, "Horiaci byt: ALARM"),
         ("Pexels_8365993_drone_burning", 10, "Dym a ohen nad mestom (dron): ALARM"),
         ("SYNTH_static_fire_poster_roundabout", 30, "Vlozeny staticky obrazok ohna: detekcia, BEZ alarmu"),
         ("Car_Fire_Perth_Amboy_720p", 24, "Horiace auto: ALARM (dym)")]


def grab(det_dir, name, t, label):
    rows = list(csv.DictReader(open(os.path.join(det_dir, name + "_frames.csv"))))
    k = min(range(len(rows)), key=lambda i: abs(float(rows[i]["t"]) - t))
    cap = cv2.VideoCapture(os.path.join(det_dir, name + "_det.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, k)
    ok, f = cap.read()
    f = cv2.resize(f, (640, 360))
    cv2.rectangle(f, (0, 332), (640, 360), (0, 0, 0), -1)
    cv2.putText(f, label, (8, 351), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return f


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--det-dir", required=True, help="priečinok s *_det.mp4 a *_frames.csv")
    ap.add_argument("--summary-dir", default=None, help="priečinok so *_summary.json -> vypíše tabuľku")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t = [grab(a.det_dir, *s) for s in SHOTS]
    cv2.imwrite(os.path.join(OUT, "video_demo.jpg"), np.vstack([np.hstack(t[:2]), np.hstack(t[2:])]),
                [cv2.IMWRITE_JPEG_QUALITY, 82])
    if a.summary_dir:
        print("| video | trvanie s | proc fps | surová detekcia | potvrdené | v alarme | udalosti | 1. detekcia s | 1. alarm s | oneskorenie s |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for f in sorted(glob.glob(os.path.join(a.summary_dir, "*_summary.json"))):
            s = json.load(open(f))
            print(f"| {s['video']} | {s['duration_s']} | {s['mode']['proc_fps']} | {s['raw_detection_rate']:.1%} | "
                  f"{s['confirmed_rate']:.1%} | {s['alarm_rate']:.1%} | {s['alarm_events']} | {s['first_raw_detection_s']} | "
                  f"{s['first_alarm_s']} | {s['alarm_latency_s']} |")
    print("hotovo")
