import cv2
import numpy as np
import uuid
import time
import os
import torch
from ultralytics import YOLO
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.engine.results import Boxes
from types import SimpleNamespace
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoprimaryctx
from generate_html import generate_html

#frames priečinok
os.makedirs("frames", exist_ok=True)

print("Načítavam YOLO TensorRT engine...")
yolo_model = YOLO("../../modely/yolov8n_b1_512.engine", task='detect')

print("Načítavam Vehicle ReID TensorRT engine...")
TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
with open("../models/vehicle_reid.engine", "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
    reid_engine = runtime.deserialize_cuda_engine(f.read())

reid_context = reid_engine.create_execution_context()
reid_stream = cuda.Stream()

input_name = reid_engine.get_tensor_name(0)
output_name = reid_engine.get_tensor_name(1)
output_shape = reid_engine.get_tensor_shape(output_name)
output_size = trt.volume(output_shape)

host_input = cuda.pagelocked_empty(1 * 3 * 208 * 208, dtype=np.float32)
device_input = cuda.mem_alloc(host_input.nbytes)
host_output = cuda.pagelocked_empty(output_size, dtype=np.float32)
device_output = cuda.mem_alloc(host_output.nbytes)

reid_context.set_tensor_address(input_name, int(device_input))
reid_context.set_tensor_address(output_name, int(device_output))

#vygeneruj embedding
def get_reid_embedding(crop_bgr):
    img = cv2.resize(crop_bgr, (208, 208))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)

    np.copyto(host_input, img.ravel())
    cuda.memcpy_htod_async(device_input, host_input, reid_stream)
    reid_context.execute_async_v3(stream_handle=reid_stream.handle)
    cuda.memcpy_dtoh_async(host_output, device_output, reid_stream)
    reid_stream.synchronize()

    embedding = host_output.copy()
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding


#qdrant init
print("Inicializujem Qdrant...")
qdrant = QdrantClient(path="./qdrant_demo")
collection_name = "vehicles"

if not qdrant.collection_exists(collection_name):
    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

#tracker nastavenia
DET_CONF_THRES = 0.35
VEHICLE_CLASSES = [1, 2, 3, 5, 7] #bicycle, car, motorcycle, bus, truck

args = SimpleNamespace(
    tracker_type="bytetrack",
    track_high_thresh=0.25,
    track_low_thresh=0.1,
    new_track_thresh=0.25,
    track_buffer=30,
    match_thresh=0.8,
    fuse_score=True,
)
tracker = BYTETracker(args)

#načítanie snímkov
def load_frames(video_path, max_frames=None, stride=1):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {total} snímok, {fps:.1f} FPS, stride={stride}")

    frames = []
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            frames.append(f)
            if max_frames and len(frames) >= max_frames:
                break
        idx += 1
    cap.release()
    print(f"Načítaných: {len(frames)} snímok (efektívne FPS: {fps/stride:.1f})")
    return frames, fps / stride

print("Spúšťam spracovanie videa...")


# Cesta k videu
video_path = "../data/videos/RoundaboutHD/kamera1_hd_1min.mp4"

stride = 2
frames, effective_fps = load_frames(video_path, max_frames=None, stride=stride)

if not frames:
    print("Žiadne snímky na spracovanie.")
    exit()

h, w = frames[0].shape[:2]

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter("output_reid_demo.mp4", fourcc, effective_fps, (w, h))

trails = {}
TRAIL_LENGTH = 30
all_ids = set()
best_tracks = {} #najlepšie snímky
frame_count = 0



for frame in frames:
    frame_count += 1
    clean_frame = frame.copy() #clean frame pre uloženie do db

    results = yolo_model.predict(
        frame,
        imgsz=512,
        conf=DET_CONF_THRES,
        iou=0.45,
        verbose=False,
    )

    r = results[0]
    dets = []
    if r.boxes is not None:
        for box in r.boxes:
            cls = int(box.cls[0])
            if cls not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf_val = float(box.conf[0])
            dets.append({
                "xyxy": [x1, y1, x2, y2],
                "score": conf_val,
                "class": cls,
            })

    #príprava pre ByteTrack
    if dets:
        det_np = np.array([
            [d["xyxy"][0], d["xyxy"][1], d["xyxy"][2], d["xyxy"][3],
             d["score"], d["class"]]
            for d in dets
        ], dtype=np.float32)
    else:
        det_np = np.empty((0, 6), dtype=np.float32)

    detections = Boxes(torch.from_numpy(det_np), orig_shape=(h, w))
    online = tracker.update(detections, img=None, feats=None)

    #spracuj výsledky z trackera
    if online is not None and len(online) > 0:
        for row in online:
            x1, y1, x2, y2, tid = row[0], row[1], row[2], row[3], int(row[4])
            cls = int(row[6])
            all_ids.add(tid)

            #stred boxu pre trail
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            if tid not in trails:
                trails[tid] = []
            trails[tid].append((cx, cy))
            if len(trails[tid]) > TRAIL_LENGTH:
                trails[tid].pop(0)

            #vykreslenie trailu
            for j in range(1, len(trails[tid])):
                cv2.line(frame, trails[tid][j - 1], trails[tid][j], (0, 255, 255), 2)

            #vykreslenie boxu
            bx1, by1, bx2, by2 = map(int, [x1, y1, x2, y2])
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)

            #ID text
            label = f"ID {tid}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(frame, (bx1, by1 - th - 10), (bx1 + tw + 5, by1), (0, 255, 0), -1)
            cv2.putText(frame, label, (bx1 + 2, by1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

            #reid a uloženie
            bbox_w = bx2 - bx1
            bbox_h = by2 - by1
            area = bbox_w * bbox_h

            #zlé boxy
            if bbox_w < 50 or bbox_h < 40:
                continue
            aspect_ratio = bbox_w / bbox_h
            if aspect_ratio > 4.0 or aspect_ratio < 0.2:
                continue

            #okraj kamery
            MARGIN = 15
            if bx1 <= MARGIN or by1 <= MARGIN or bx2 >= w - MARGIN or by2 >= h - MARGIN:
                continue

            #je tento obraz lepší?
            is_better = False

            if tid not in best_tracks:
                is_better = True
            else:
                old_track = best_tracks[tid]
                if area > old_track["area"] * 1.10: #aspoň o 10% lepší
                    is_better = True

            #uložíme najlepší záber
            if is_better:
                #výrez pre reid
                crop_reid = clean_frame[by1:by2, bx1:bx2]

                if crop_reid.size > 0:
                    os.makedirs("crops", exist_ok=True)
                    original_id = str(uuid.uuid4())
                    qdrant_id = str(uuid.uuid4())

                    #embedding z cropu
                    emb = get_reid_embedding(crop_reid)

                    #hľadáme v Qdrant
                    matched = False
                    if tid not in best_tracks:
                        search_response = qdrant.query_points(
                            collection_name=collection_name,
                            query=emb.tolist(),
                            limit=1
                        )
                        if search_response.points and search_response.points[0].score > 0.75:
                            original_id = search_response.points[0].payload["original_id"]
                            qdrant_id = search_response.points[0].id
                            matched = True
                            score = search_response.points[0].score
                            print(f"ID {tid} -> REID MATCH s {original_id[:8]} (skóre: {score:.2f})")

                    if not matched:
                        if tid not in best_tracks:
                            print(f"ID {tid} -> NOVÉ auto ({original_id[:8]})")
                        else:
                            original_id = best_tracks[tid]["original_id"]
                            qdrant_id = best_tracks[tid]["qdrant_id"]
                            print(f"ID {tid} -> Aktualizujem lepší záber (plocha: {area})")

                    #uložíme crop pre ReID (napr. crops/abc.jpg)
                    reid_crop_path = f"crops/{original_id}.jpg"
                    cv2.imwrite(reid_crop_path, crop_reid)

                    #široký výrez pre dashboard, použijeme 20% rezervu a doplnenie do 4:3
                    pad_w = int(bbox_w * 0.2)
                    pad_h = int(bbox_h * 0.2)
                    cx1 = max(0, bx1 - pad_w)
                    cy1 = max(0, by1 - pad_h)
                    cx2 = min(w, bx2 + pad_w)
                    cy2 = min(h, by2 + pad_h)

                    clean_crop = clean_frame[cy1:cy2, cx1:cx2]

                    #doplnenie do 4:3 (aby karty v HTML boli rovnaké)
                    target_ratio = 4 / 3
                    h_crop, w_crop = clean_crop.shape[:2]
                    current_ratio = w_crop / h_crop

                    if current_ratio < target_ratio:
                        needed_w = int(h_crop * target_ratio)
                        extra_w = needed_w - w_crop
                        new_cx1 = max(0, cx1 - extra_w // 2)
                        new_cx2 = min(w, cx2 + extra_w // 2)
                        clean_crop = clean_frame[cy1:cy2, new_cx1:new_cx2]
                    elif current_ratio > target_ratio:
                        needed_h = int(w_crop / target_ratio)
                        extra_h = needed_h - h_crop
                        new_cy1 = max(0, cy1 - extra_h // 2)
                        new_cy2 = min(h, cy2 + extra_h // 2)
                        clean_crop = clean_frame[new_cy1:new_cy2, cx1:cx2]

                    #uložíme široký výrez pre Dashboard (napr. frames/abc.jpg)
                    frame_path = f"frames/{original_id}.jpg"
                    cv2.imwrite(frame_path, clean_crop)

                    #uložíme do Qdrant
                    qdrant.upsert(
                        collection_name=collection_name,
                        points=[PointStruct(
                            id=qdrant_id,
                            vector=emb.tolist(),
                            payload={
                                "original_id": original_id,
                                "frame_path": frame_path, #široký výrez (pre dashboard)
                                "reid_crop_path": reid_crop_path, #tesný výrez (pre ReID/debug)
                                "timestamp": time.strftime("%H:%M:%S"),
                                "camera": "demo_cam"
                            }
                        )]
                    )

                    best_tracks[tid] = {
                        "original_id": original_id,
                        "qdrant_id": qdrant_id,
                        "area": area,
                        "bx1": bx1, "by1": by1, "bx2": bx2, "by2": by2
                    }

    #počet unique ID
    cv2.putText(frame, f"Frame {frame_count} | Unique IDs: {len(all_ids)}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    writer.write(frame)
    cv2.imshow("Demo - Custom Tracking + ReID", frame)

    time.sleep(1.0 / effective_fps)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        generate_html(qdrant)
        break

writer.release()
cv2.destroyAllWindows()
generate_html(qdrant)
qdrant.close()
print(f"\nHotovo. Spracovaných snímok: {frame_count}, Unique IDs: {len(all_ids)}")