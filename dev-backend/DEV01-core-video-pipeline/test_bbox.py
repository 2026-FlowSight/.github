import cv2
import numpy as np
import torch
from ultralytics import YOLO
from types import SimpleNamespace
from ultralytics.engine.results import Boxes
from byte_tracker_modified import BYTETracker
import os

# --- NASTAVENIA ---
# !!! ZMEŇ NA CESTU K TVOJMU OBRÁZKU !!!
TEST_IMAGE_PATH = "test_frame_13s.jpg"
yolo_path = "../../models/yolo26n_tuned.pt"

# Skúsime aj iné imgsz, aby sme videli rozdiel
IMG_SIZES = [512, 960]

def run_test():
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"CHYBA: Nenašiel som obrázok {TEST_IMAGE_PATH}")
        return

    frame = cv2.imread(TEST_IMAGE_PATH)
    h, w = frame.shape[:2]
    print(f"Rozmery obrázka: {w}x{h}")

    print("Načítavam YOLO...")
    yolo_model = YOLO(yolo_path, task='detect')

    # Inicializácia trackera (rovnaké nastavenia ako v tvojom main kóde)
    args = SimpleNamespace(
        tracker_type="bytetrack",
        track_high_thresh=0.25,
        track_low_thresh=0.2,
        new_track_thresh=0.45,
        track_buffer=30,
        match_thresh=0.8,
        fuse_score=True,
    )
    tracker = BYTETracker(args)

    for imgsz in IMG_SIZES:
        print(f"\n--- TESTOVANIE S imgsz={imgsz} ---")
        # 1. ČISTÉ YOLO
        results = yolo_model.predict(frame, imgsz=imgsz, conf=0.20, iou=0.45, verbose=False)
        r = results[0]

        dets = []
        if r.boxes is not None:
            for box in r.boxes:
                cls = int(box.cls[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append([x1, y1, x2, y2, float(box.conf[0]), cls])

        if len(dets) > 0:
            # Zoberieme najväčší box (predpokladáme, že je to to auto)
            best_det = max(dets, key=lambda d: (d[2]-d[0])*(d[3]-d[1]))
            yx1, yy1, yx2, yy2 = map(int, best_det[:4])
            print(f"YOLO (modry) box: w={yx2-yx1}, h={yy2-yy1}")

            # Nakreslíme modrý YOLO box
            test_img = frame.copy()
            cv2.rectangle(test_img, (yx1, yy1), (yx2, yy2), (255, 0, 0), 2)
            cv2.putText(test_img, "YOLO", (yx1, yy1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

            # 2. TRACKER
            det_np = np.array(dets, dtype=np.float32)
            detections = Boxes(torch.from_numpy(det_np), orig_shape=(h, w))

            # Pustíme tracker (aj keď len na 1 frame, ukáže nám to, čo vráti)
            online = tracker.update(detections, img=None, feats=None)

            if online is not None and len(online) > 0:
                # Nájdeme najväčší trackovaný box
                best_track = max(online, key=lambda row: (row[2]-row[0])*(row[3]-row[1]))
                tx1, ty1, tx2, ty2 = map(int, best_track[:4])
                print(f"TRACKER (cerveny) box: w={tx2-tx1}, h={ty2-ty1}")

                # Nakreslíme červený TRACKER box
                cv2.rectangle(test_img, (tx1, ty1), (tx2, ty2), (0, 0, 255), 2)
                cv2.putText(test_img, "TRACK", (tx1, ty1-30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                print("TRACKER: Nič nevrátil (napr. track ešte nie je potvrdený).")

            out_name = f"test_bbox_{imgsz}.jpg"
            cv2.imwrite(out_name, test_img)
            print(f"Uložené ako {out_name} - pozri sa, či modrý a červený sedia.")
        else:
            print("YOLO nenašlo žiadne auto!")

if __name__ == "__main__":
    run_test()
