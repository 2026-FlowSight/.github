import cv2
import numpy as np
import uuid
import time
import os
import torch
from ultralytics import YOLO
from byte_tracker_modified import BYTETracker
from ultralytics.trackers.utils.reid import ReID
from ultralytics.engine.results import Boxes
from types import SimpleNamespace
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client import models
import tensorrt as trt
import pycuda.driver as cuda
from generate_html import generate_html
import pycuda.autoprimaryctx
from ultralytics.utils.ops import xyxy2xywh

# ==========================================
# NASTAVENIA
# ==========================================
DET_CONF_THRES = 0.35  # Zvýšené z 0.20
video_stride = 2

os.makedirs("frames", exist_ok=True)
os.makedirs("crops", exist_ok=True)

yolo_path = "../../models/yolo26n_tuned.engine"  # Alebo .engine ak máš
reid_path = "../../models/vehicle_reid_fixed.engine"
#video_path = "../../data/videos/RoundaboutHD/kamera1_hd_1min.mp4"
video_path = "kamera1_od_12s.mp4"

TRT_LOGGER = trt.Logger(trt.Logger.VERBOSE)
try:
    with open(reid_path, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
        test_engine = runtime.deserialize_cuda_engine(f.read())
        if test_engine is None:
            raise RuntimeError(f"TensorRT nedokázal načítať engine: {reid_path}")
        print(f"Engine úspešne načítaný. Vstup: {test_engine.get_tensor_name(0)}")
except Exception as e:
    print(f"CHYBA pri načítavaní TensorRT engine: {e}")
    raise

print("Načítavam YOLO...")
yolo_model = YOLO(yolo_path, task='detect')

print("Načítavam Vehicle ReID...")
reid_encoder = ReID(reid_path, imgsz=208)

print("Inicializujem Qdrant...")
qdrant = QdrantClient(path="./qdrant_demo")

collection_reid = "vehicles_reid"
if not qdrant.collection_exists(collection_reid):
    qdrant.create_collection(
        collection_name=collection_reid,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

collection_dash = "vehicles_dashboard"
if not qdrant.collection_exists(collection_dash):
    qdrant.create_collection(
        collection_name=collection_dash,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

yolo_tuned = "tuned" not in yolo_path
VEHICLE_CLASSES = [1, 2, 3, 5, 7] if yolo_tuned else [0, 1, 2, 3, 4]

args = SimpleNamespace(
    tracker_type="bytetrack",
    track_high_thresh=0.25,
    track_low_thresh=0.2,
    new_track_thresh=0.45,
    track_buffer=30,  # Znížené z 120
    match_thresh=0.8,
    fuse_score=True,
)
tracker = BYTETracker(args)

# ==========================================
# POMOCNÉ FUNKCIE
# ==========================================
def laplacian_score(img):
    if img.size == 0: return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def quality_score(area, sharpness, w_img, h_img):
    # Normalizujeme plochu (napr. auto zaberá 5% obrazu = 1.0)
    norm_area = area / (w_img * h_img)
    # Normalizujeme ostrosť (bežne býva 10 - 1000)
    norm_sharp = min(sharpness / 100.0, 5.0) # Capneme to na 5, aby to nedominovalo
    # Skóre: 70% váha na veľkosť, 30% na ostrosť
    return (norm_area * 0.7) + (norm_sharp * 0.3)

def load_frames(video_path, max_frames=None, video_stride=1):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {total} snímok, {fps:.1f} FPS, video_stride={video_stride}")

    frames = []
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx % video_stride == 0:
            frames.append(f)
            if max_frames and len(frames) >= max_frames:
                break
        idx += 1
    cap.release()
    print(f"Načítaných: {len(frames)} snímok (efektívne FPS: {fps/video_stride:.1f})")
    return frames, fps / video_stride

def save_vehicle_view(original_id, embedding, clean_frame, bx1, by1, bx2, by2, slot_name, area, w_img, h_img, sharpness):
    """Uloží čistý záber (bez boxov) do Qdrantu pre ReID a Dashboard."""
    crop_reid = clean_frame[by1:by2, bx1:bx2]
    if crop_reid.size == 0:
        return

    reid_crop_path = f"crops/{original_id}_{slot_name}.jpg"
    cv2.imwrite(reid_crop_path, crop_reid)

    # Široký výrez pre dashboard (4:3)
    bbox_w = bx2 - bx1
    bbox_h = by2 - by1
    pad_w = int(bbox_w * 0.2)
    pad_h = int(bbox_h * 0.2)
    cx1 = max(0, bx1 - pad_w)
    cy1 = max(0, by1 - pad_h)
    cx2 = min(w_img, bx2 + pad_w)
    cy2 = min(h_img, by2 + pad_h)
    clean_crop = clean_frame[cy1:cy2, cx1:cx2]

    target_ratio = 4 / 3
    h_crop, w_crop = clean_crop.shape[:2]
    current_ratio = w_crop / h_crop if h_crop > 0 else 1
    if current_ratio < target_ratio:
        needed_w = int(h_crop * target_ratio)
        extra_w = needed_w - w_crop
        new_cx1 = max(0, cx1 - extra_w // 2)
        new_cx2 = min(w_img, cx2 + extra_w // 2)
        clean_crop = clean_frame[cy1:cy2, new_cx1:new_cx2]
    elif current_ratio > target_ratio:
        needed_h = int(w_crop / target_ratio)
        extra_h = needed_h - h_crop
        new_cy1 = max(0, cy1 - extra_h // 2)
        new_cy2 = min(h_img, cy2 + extra_h // 2)
        clean_crop = clean_frame[new_cy1:new_cy2, cx1:cx2]

    frame_path = f"frames/{original_id}_{slot_name}.jpg"
    cv2.imwrite(frame_path, clean_crop)

    timestamp = time.strftime("%H:%M:%S")

    # ReID kolekcia
    qdrant.upsert(
        collection_name=collection_reid,
        points=[PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={
                "original_id": original_id,
                "slot": slot_name,
                "frame_path": frame_path,
                "reid_crop_path": reid_crop_path,
                "timestamp": timestamp,
                "camera": "demo_cam",
                "area": area,
                "sharpness": sharpness,
            }
        )]
    )

    # Dashboard kolekcia
    dash_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, original_id))
    existing = qdrant.retrieve(collection_name=collection_dash, ids=[dash_id])

    views_list = []
    best_frame = ""
    existing_best_sharpness = 0.0

    if existing:
        views_list = existing[0].payload.get("views", [])
        best_frame = existing[0].payload.get("best_frame_path", "")
        existing_best_sharpness = existing[0].payload.get("best_sharpness", 0.0)

    view_data = {"slot": slot_name, "reid_crop_path": reid_crop_path}
    views_list = [v for v in views_list if v["slot"] != slot_name]
    views_list.append(view_data)

    if not best_frame or sharpness > existing_best_sharpness:
        best_frame = frame_path
        existing_best_sharpness = sharpness

    qdrant.upsert(
        collection_name=collection_dash,
        points=[PointStruct(
            id=dash_id,
            vector=embedding.tolist(),
            payload={
                "original_id": original_id,
                "best_frame_path": best_frame,
                "best_sharpness": existing_best_sharpness,
                "timestamp": timestamp,
                "camera": "demo_cam",
                "views": views_list
            }
        )]
    )

# ==========================================
# HLAVNÝ PROCES
# ==========================================
def process_video():
    print("Spúšťam spracovanie videa...")
    frames, effective_fps = load_frames(video_path, max_frames=None, video_stride=video_stride)

    if not frames:
        print("Žiadne snímky na spracovanie.")
        exit()

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter("output_reid_demo.mp4", fourcc, effective_fps, (w, h))

    trails = {}
    TRAIL_LENGTH = 30
    all_ids = set()
    best_tracks = {}
    frame_count = 0

    for frame in frames:
        frame_count += 1
        clean_frame = frame.copy()

        results = yolo_model.predict(
            frame,
            imgsz=512,
            conf=DET_CONF_THRES,
            iou=0.55,
            verbose=False,
        )

        r = results[0]
        dets = []
        if r.boxes is not None:
            for box in r.boxes:
                cls = int(box.cls[0])
                if not yolo_tuned and cls not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                if (x2 - x1) > w * 0.6:
                    continue
                dets.append({"xyxy": [x1, y1, x2, y2], "score": float(box.conf[0]), "class": cls})

        if dets:
            det_np = np.array([[d["xyxy"][0], d["xyxy"][1], d["xyxy"][2], d["xyxy"][3], d["score"], d["class"]] for d in dets], dtype=np.float32)
        else:
            det_np = np.empty((0, 6), dtype=np.float32)

        detections = Boxes(torch.from_numpy(det_np), orig_shape=(h, w))
        online = tracker.update(detections, img=None, feats=None)

        if online is not None and len(online) > 0:
            for row in online:
                x1, y1, x2, y2, tid = row[0], row[1], row[2], row[3], int(row[4])
                all_ids.add(tid)

                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                if tid not in trails: trails[tid] = []
                trails[tid].append((cx, cy))
                if len(trails[tid]) > TRAIL_LENGTH: trails[tid].pop(0)

                for j in range(1, len(trails[tid])):
                    cv2.line(frame, trails[tid][j - 1], trails[tid][j], (0, 255, 255), 2)

                bx1, by1, bx2, by2 = map(int, [x1, y1, x2, y2])
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                label = f"ID {tid}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                cv2.rectangle(frame, (bx1, by1 - th - 10), (bx1 + tw + 5, by1), (0, 255, 0), -1)
                cv2.putText(frame, label, (bx1 + 2, by1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

                bbox_w = bx2 - bx1
                bbox_h = by2 - by1
                area = bbox_w * bbox_h
                aspect_ratio = bbox_w / bbox_h

                # 1. FILTRE
                if bbox_w < 40 or bbox_h < 35: continue
                if aspect_ratio > 4.0 or aspect_ratio < 0.35: continue

                # 2. CLIPPING
                EDGE_MARGIN = 20
                is_clipped = (bx1 <= EDGE_MARGIN or by1 <= EDGE_MARGIN or bx2 >= w - EDGE_MARGIN or by2 >= h - EDGE_MARGIN)
                if is_clipped:
                    continue

                cx_box = (bx1 + bx2) / 2
                cy_box = (by1 + by2) / 2
                dets_xywh = np.array([[cx_box, cy_box, bbox_w, bbox_h]], dtype=np.float32)

                # 3. PRVÝ ZÁBER (Inicializácia)
                if tid not in best_tracks:
                    embs = reid_encoder(frame, dets_xywh)
                    if embs[0] is None: continue
                    embedding = embs[0]

                    # ReID match
                    search_response = qdrant.query_points(collection_name=collection_reid, query=embedding.tolist(), limit=5)
                    matched = False
                    original_id = str(uuid.uuid4())

                    if search_response.points:
                        best_match = max(search_response.points, key=lambda p: p.score)
                        if best_match.score > 0.65:
                            original_id = best_match.payload["original_id"]
                            matched = True
                            print(f"ID {tid} -> REID MATCH s {original_id[:8]} (skóre: {best_match.score:.2f})")

                            existing_tid = None
                            for t, data in best_tracks.items():
                                if data["original_id"] == original_id:
                                    existing_tid = t
                                    break
                            if existing_tid is not None and existing_tid != tid:
                                tracker.force_track_id(tid, existing_tid)
                                tid = existing_tid

                    if not matched:
                        print(f"ID {tid} -> NOVÉ auto ({original_id[:8]})")

                    sharpness = laplacian_score(clean_frame[by1:by2, bx1:bx2])
                    initial_score = quality_score(area, sharpness, w, h)

                    best_tracks[tid] = {
                        "original_id": original_id,
                        "current_angle": "angle_1",
                        "angles": {
                            "angle_1": {
                                "best_score": initial_score,
                                "best_bbox": (bx1, by1, bx2, by2),
                                "best_emb": embedding,
                                "saved": False
                            }
                        },
                        "angle_embeddings": {"angle_1": embedding},
                        "embeddings": [embedding],
                        "exit": False
                    }

                # 4. AKTUALIZÁCIA
                else:
                    track = best_tracks[tid]

                    # Poistka (ak by náhodou chýbali kľúče)
                    if "angles" not in track:
                        track["current_angle"] = "angle_1"
                        track["angles"] = {
                            "angle_1": {
                                "best_score": 0.0,
                                "best_bbox": (bx1, by1, bx2, by2),
                                "best_emb": None,
                                "saved": False
                            }
                        }
                        track["angle_embeddings"] = {}
                        track["embeddings"] = []
                        track["exit"] = False

                    current_angle = track["current_angle"]

                    embs = reid_encoder(frame, dets_xywh)
                    if embs[0] is None: continue
                    current_emb = embs[0]
                    sharpness = laplacian_score(clean_frame[by1:by2, bx1:bx2])
                    current_score = quality_score(area, sharpness, w, h)

                    ref_emb = track["angle_embeddings"].get(current_angle)
                    if ref_emb is None:
                        track["angle_embeddings"][current_angle] = current_emb
                        ref_emb = current_emb

                    sim = np.dot(current_emb, ref_emb) / (np.linalg.norm(current_emb) * np.linalg.norm(ref_emb) + 1e-8)
                    is_same_angle = sim > 0.75

                    slot_to_save = None
                    bbox_to_save = None

                    if is_same_angle:
                        angle_data = track["angles"][current_angle]
                        if current_score > angle_data["best_score"] * 1.20:
                            angle_data["best_score"] = current_score
                            angle_data["best_bbox"] = (bx1, by1, bx2, by2)
                            angle_data["best_emb"] = current_emb
                            slot_to_save = current_angle
                            bbox_to_save = (bx1, by1, bx2, by2)
                    else:
                        existing_angle_name = None
                        for a_name, a_emb in track["angle_embeddings"].items():
                            a_sim = np.dot(current_emb, a_emb) / (np.linalg.norm(current_emb) * np.linalg.norm(a_emb) + 1e-8)
                            if a_sim > 0.75:
                                existing_angle_name = a_name
                                break

                        if existing_angle_name is not None:
                            track["current_angle"] = existing_angle_name
                            current_angle = existing_angle_name
                            angle_data = track["angles"][current_angle]
                            if current_score > angle_data["best_score"] * 1.20:
                                angle_data["best_score"] = current_score
                                angle_data["best_bbox"] = (bx1, by1, bx2, by2)
                                angle_data["best_emb"] = current_emb
                                slot_to_save = current_angle
                                bbox_to_save = (bx1, by1, bx2, by2)
                        else:
                            if len(track["angles"]) < 4:
                                new_angle_name = f"angle_{len(track['angles']) + 1}"
                                track["angles"][new_angle_name] = {
                                    "best_score": current_score,
                                    "best_bbox": (bx1, by1, bx2, by2),
                                    "best_emb": current_emb,
                                    "saved": False
                                }
                                track["angle_embeddings"][new_angle_name] = current_emb
                                track["current_angle"] = new_angle_name
                                slot_to_save = new_angle_name
                                bbox_to_save = (bx1, by1, bx2, by2)
                                print(f"ID {tid} -> Nový uhol: {new_angle_name}")

                    # 5. EXIT (Uložíme všetko, čo ešte nie je v DB + samotný exit)
                    is_near_edge = (bx1 < 100 or by1 < 100 or bx2 > w - 100 or by2 > h - 100)
                    if slot_to_save is None and is_near_edge and not track["exit"]:
                        # Uložíme všetky uhly z pamäte, ktoré ešte neboli uložené
                        for a_name, a_data in track["angles"].items():
                            if not a_data["saved"] and a_data["best_emb"] is not None:
                                print(f"ID {tid} -> Ukladám pri odchode: {a_name}")
                                ax1, ay1, ax2, ay2 = a_data["best_bbox"]
                                save_vehicle_view(track["original_id"], a_data["best_emb"], clean_frame, ax1, ay1, ax2, ay2, a_name, area, w, h, a_data["best_score"])
                                a_data["saved"] = True

                        # Uložíme exit záber
                        print(f"ID {tid} -> Ukladám: exit")
                        save_vehicle_view(track["original_id"], current_emb, clean_frame, bx1, by1, bx2, by2, "exit", area, w, h, sharpness)
                        track["exit"] = True
                        slot_to_save = None

                    # 6. ULOŽENIE NOVÉHO NAJLEPŠIEHO ZÁBERU PRE UHOL
                    if slot_to_save is not None and bbox_to_save is not None:
                        sx1, sy1, sx2, sy2 = bbox_to_save
                        print(f"ID {tid} -> Ukladám lepší záber pre: {slot_to_save}")
                        save_vehicle_view(
                            track["original_id"], current_emb, clean_frame,
                            sx1, sy1, sx2, sy2, slot_to_save,
                            (sx2-sx1)*(sy2-sy1), w, h, sharpness
                        )
                        track["angles"][slot_to_save]["saved"] = True

        cv2.putText(frame, f"Frame {frame_count} | Unique IDs: {len(all_ids)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(frame)
        cv2.imshow("Demo - Custom Tracking + ReID", frame)

        time.sleep(1.0 / effective_fps)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            generate_html(qdrant)
            break

    writer.release()
    cv2.destroyAllWindows()
    print(f"\nHotovo. Spracovaných snímok: {frame_count}, Unique IDs: {len(all_ids)}")

if __name__ == "__main__":
    process_video()
    generate_html(qdrant)
    qdrant.close()
