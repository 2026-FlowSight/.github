"""Detekcia ohňa a dymu na videu + časové overenie + meranie času.

Pipeline pre každú spracovanú snímku (každá `stride`-tá, alebo `--fps-process` snímok za sekundu):
  1. YOLO (dotrénovaný na D-Fire, triedy 0=smoke, 1=fire) -> surové detekcie
  2. Časové overenie (potláča falošné poplachy):
       a) perzistencia: trieda musí byť videná aspoň v `min_hits_frac` (50 %) spracovaných snímok
          za posledných `window_s` sekúnd (definované v SEKUNDÁCH, aby sa správalo rovnako pri 15 aj 2 fps)
       b) pohyb: priemerný absolútny rozdiel jasu v boxe voči snímke spred `motion_gap_s` (1 s)
          musí byť aspoň `min_motion`. Oheň a dym sa za 1 s menia, statický obrázok (plagát) nie.
          Len pre PEVNÚ kameru; pre kameru, ktorá sa hýbe, `--min-motion 0`.
  3. Alarm = potvrdená detekcia; drží `hold_s` sekúnd po poslednom potvrdení (1 udalosť, nie blikanie)

Výstupy (do --out-dir):
  <video>_det.mp4      video s boxami (žlté = surové, červené = potvrdené) a bannerom ALARM
  <video>_frames.csv   pre každú spracovanú snímku: surové / potvrdené detekcie, pohyb, alarm, ms
  <video>_summary.json súhrn: podiely snímok, počet udalostí, oneskorenie alarmu, ms/snímka

Príklad (nasadenie: 2 snímky za sekundu na kameru):
  python detect_fire_video.py --model weights/fire_yolov8n_512.pt --source video.mp4 \
      --out-dir runs/demo --fps-process 2
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import deque

import cv2
import numpy as np

NAMES = {0: "smoke", 1: "fire"}
COLOR_RAW = (0, 215, 255)  # žltá
COLOR_OK = (0, 0, 255)  # červená



def auto_device():
    """CUDA (Jetson/PC) -> MPS (Mac) -> CPU. Ultralytics s device=None na Macu použije CPU, preto vlastný výber."""
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class TemporalVerifier:
    """Potvrdí detekciu, ak sa trieda objavuje opakovane (perzistencia) a voliteľne,
    ak sa obsah boxu za `motion_gap_s` zmení (pohyb), čo odlíši oheň od statického obrázka.

    proc_fps   = koľko snímok za sekundu ide do YOLO (fps videa / stride)
    video_fps  = fps videa (push_frame sa volá pre každú snímku videa)

    Zmerané (README §3.3): statický vložený obrázok ohňa má pohyb ~0,8, skutočný oheň a dym
    na videách 12-21 (medián). Prah 6 je medzi tým. Na pohyblivej kamere sa hýbe všetko -> vypnúť.
    """

    def __init__(self, proc_fps, video_fps, window_s=3.0, min_hits_frac=0.5, min_motion=6.0, motion_gap_s=1.0):
        self.window = max(2, int(round(window_s * proc_fps)))
        self.min_hits = max(2, int(math.ceil(min_hits_frac * self.window)))
        self.min_motion = min_motion
        self.hist = {c: deque(maxlen=self.window) for c in NAMES}
        self.gray = deque(maxlen=max(2, int(round(video_fps * motion_gap_s)) + 1))

    def push_frame(self, frame):
        """Volať pre KAŽDÚ snímku videa (aj tie, na ktoré nejde YOLO), aby sedel časový posun."""
        self.gray.append(cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0))

    def warmed_up(self):
        return self.min_motion <= 0 or len(self.gray) == self.gray.maxlen

    def motion_in(self, box):
        if self.min_motion <= 0:
            return float("nan")  # test pohybu vypnutý
        if len(self.gray) < self.gray.maxlen:
            return 0.0  # ešte nemáme snímku spred 1 s (zahrievanie po štarte)
        x1, y1, x2, y2 = (max(0, int(v)) for v in box)
        a = self.gray[-1][y1:y2, x1:x2]
        b = self.gray[0][y1:y2, x1:x2]
        return float(cv2.absdiff(a, b).mean()) if a.size else 0.0

    def update(self, dets):
        """dets: Nx6 (x1,y1,x2,y2,conf,cls). Vráti masku potvrdených detekcií a pohyb pre každú."""
        motion = np.array([self.motion_in(d[:4]) for d in dets], dtype=np.float32)
        moving = np.isnan(motion) | (motion >= self.min_motion)
        for c in NAMES:
            self.hist[c].append(bool(((dets[:, 5] == c) & moving).any()) if len(dets) else False)
        confirmed = np.array([sum(self.hist[int(d[5])]) >= self.min_hits and m
                              for d, m in zip(dets, moving)], dtype=bool)
        return confirmed, motion


def run(model, source, out_dir, stride=2, imgsz=512, conf=0.4, device=None, window_s=3.0, min_hits_frac=0.5,
        min_motion=6.0, motion_gap_s=1.0, hold_s=5.0, save_video=True, max_seconds=None, tag="",
        fps_process=None):
    device = device or auto_device()
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"neviem otvoriť video {source}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 25.0
    if fps_process:
        stride = max(1, int(round(fps / fps_process)))
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.splitext(os.path.basename(source))[0] + tag
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = 1280 / max(W, H) if max(W, H) > 1280 else 1.0  # 4K videá zmenšíme (kamera ~1080p)
    W2, H2 = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    writer = None
    if save_video:
        writer = cv2.VideoWriter(os.path.join(out_dir, f"{name}_det.mp4"),
                                 cv2.VideoWriter_fourcc(*"mp4v"), fps / stride, (W2, H2))
    ver = TemporalVerifier(fps / stride, fps, window_s, min_hits_frac, min_motion, motion_gap_s)
    rows, times = [], []
    idx = -1
    events = 0
    last_confirm_t = -1e9
    alarm_prev = False
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if max_seconds and idx / fps > max_seconds:
            break
        if scale != 1.0:
            frame = cv2.resize(frame, (W2, H2), interpolation=cv2.INTER_AREA)
        ver.push_frame(frame)
        if idx % stride:
            continue
        t0 = time.perf_counter()
        r = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False, device=device)[0]
        t_inf = (time.perf_counter() - t0) * 1000
        b = r.boxes
        dets = (np.concatenate([b.xyxy.cpu().numpy(), b.conf.cpu().numpy()[:, None],
                                b.cls.cpu().numpy()[:, None]], 1) if b is not None and len(b)
                else np.zeros((0, 6), np.float32))
        t1 = time.perf_counter()
        confirmed, motion = ver.update(dets)
        t_ver = (time.perf_counter() - t1) * 1000
        times.append((t_inf, t_ver))
        t_now = idx / fps
        if confirmed.any():
            last_confirm_t = t_now
        alarm = t_now - last_confirm_t <= hold_s
        events += alarm and not alarm_prev
        alarm_prev = alarm
        rows.append(dict(frame=idx, t=round(t_now, 2), raw=len(dets),
                         raw_fire=int((dets[:, 5] == 1).sum()), raw_smoke=int((dets[:, 5] == 0).sum()),
                         confirmed=int(confirmed.sum()), alarm=int(alarm),
                         max_conf=round(float(dets[:, 4].max()), 3) if len(dets) else 0.0,
                         max_motion=round(float(np.nanmax(motion)), 2) if len(dets) and not np.isnan(motion).all() else "",
                         infer_ms=round(t_inf, 2), verify_ms=round(t_ver, 3)))
        if writer is not None:
            vis = frame.copy()
            for d, c, m in zip(dets, confirmed, motion):
                x1, y1, x2, y2 = (int(v) for v in d[:4])
                col = COLOR_OK if c else COLOR_RAW
                cv2.rectangle(vis, (x1, y1), (x2, y2), col, 2)
                mtxt = "" if np.isnan(m) else f" pohyb {m:.0f}"
                cv2.putText(vis, f"{NAMES[int(d[5])]} {d[4]:.2f}{mtxt}", (x1, max(15, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
            if alarm:
                cv2.rectangle(vis, (0, 0), (W2, 36), COLOR_OK, -1)
                cv2.putText(vis, "ALARM: OHEN / DYM", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.putText(vis, f"YOLO {t_inf:.0f} ms", (10, H2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            writer.write(vis)
    cap.release()
    if writer is not None:
        writer.release()
    with open(os.path.join(out_dir, f"{name}_frames.csv"), "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    n = max(len(rows), 1)
    inf = np.array([t[0] for t in times]) if times else np.zeros(1)
    ver_ms = np.array([t[1] for t in times]) if times else np.zeros(1)
    first_raw = next((r["t"] for r in rows if r["raw"]), None)
    first_alarm = next((r["t"] for r in rows if r["alarm"]), None)
    summary = dict(
        video=os.path.basename(source),
        mode=dict(device=str(device), stride=stride, proc_fps=round(fps / stride, 2), conf=conf, window_s=window_s,
                  window_frames=ver.window, min_hits=ver.min_hits, min_motion=min_motion,
                  motion_gap_s=motion_gap_s, hold_s=hold_s, imgsz=imgsz),
        duration_s=round((idx + 1) / fps, 1), processed_frames=len(rows),
        raw_detection_rate=round(sum(r["raw"] > 0 for r in rows) / n, 3),
        confirmed_rate=round(sum(r["confirmed"] > 0 for r in rows) / n, 3),  # bez podržania alarmu
        alarm_rate=round(sum(r["alarm"] for r in rows) / n, 3),  # vrátane podržania hold_s
        alarm_events=int(events),
        first_raw_detection_s=first_raw,
        first_alarm_s=first_alarm,
        alarm_latency_s=round(first_alarm - first_raw, 2) if first_alarm is not None and first_raw is not None else None,
        infer_ms_median=round(float(np.median(inf[2:] if len(inf) > 3 else inf)), 2),  # bez zahrievania
        infer_ms_p95=round(float(np.percentile(inf[2:] if len(inf) > 3 else inf, 95)), 2),
        verify_ms_median=round(float(np.median(ver_ms)), 3),
        verify_ms_p95=round(float(np.percentile(ver_ms, 95)), 3),
    )
    with open(os.path.join(out_dir, f"{name}_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--source", nargs="+", required=True, help="video súbor(y)")
    ap.add_argument("--out-dir", default="runs/videos")
    ap.add_argument("--stride", type=int, default=2, help="spracuj každú N-tú snímku")
    ap.add_argument("--fps-process", type=float, default=None,
                    help="namiesto --stride: koľko snímok za sekundu poslať do YOLO (napr. 2)")
    ap.add_argument("--imgsz", type=int, default=512)
    ap.add_argument("--conf", type=float, default=0.4, help="0.4 = odporúčané (README §3.1)")
    ap.add_argument("--device", default=None, help="None = automaticky (CUDA, MPS, CPU)")
    ap.add_argument("--window", type=float, default=3.0, help="okno perzistencie v sekundách")
    ap.add_argument("--min-hits-frac", type=float, default=0.5, help="podiel snímok v okne s detekciou")
    ap.add_argument("--min-motion", type=float, default=6.0,
                    help="0 = vypnúť test pohybu (pohyblivá kamera); 6 = pevná CCTV kamera")
    ap.add_argument("--motion-gap", type=float, default=1.0, help="pohyb voči snímke spred N sekúnd")
    ap.add_argument("--hold", type=float, default=5.0, help="alarm drží N sekúnd po poslednom potvrdení")
    ap.add_argument("--tag", default="", help="prípona názvu výstupných súborov")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()

    from ultralytics import YOLO

    args.device = args.device or auto_device()
    model = YOLO(args.model)
    for src in args.source:
        s = run(model, src, args.out_dir, args.stride, args.imgsz, args.conf, args.device, args.window,
                args.min_hits_frac, args.min_motion, args.motion_gap, args.hold, not args.no_video,
                args.max_seconds, args.tag, args.fps_process)
        print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
