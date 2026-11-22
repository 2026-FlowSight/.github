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
import pycuda.autoprimaryctx #nechytať
from ultralytics.utils.ops import xyxy2xywh

#user conf
DET_CONF_THRES = 0.20
video_stride = 2 #video video_stride (real fps = orig fps / video_stride), video_stride=2 means taking every 2nd frame

print("heloo stride",video_stride)

#frames priečinok
os.makedirs("frames", exist_ok=True)
os.makedirs("crops", exist_ok=True)

#paths
yolo_path = "../../models/yolo26n_tuned.pt"
reid_path = "../../models/vehicle_reid_fixed.engine"
video_path = "../../data/videos/RoundaboutHD/kamera1_hd_1min.mp4"

#try to import reid, print errors
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


#load models
print("Načítavam YOLO TensorRT engine...")
yolo_model = YOLO(yolo_path, task='detect')

print("Načítavam Vehicle ReID TensorRT engine...")
reid_encoder = ReID(reid_path, imgsz=208)

#qdrant init
print("Inicializujem Qdrant...")
qdrant = QdrantClient(path="./qdrant_demo")

#kolekcia pre ReID (všetky uhly)
collection_reid = "vehicles_reid"
if not qdrant.collection_exists(collection_reid):
    qdrant.create_collection(
        collection_name=collection_reid,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE) # 512 podľa tvojho modelu
    )

#kolekcia pre Dashboard (len best zábery)
collection_dash = "vehicles_dashboard"
if not qdrant.collection_exists(collection_dash):
    qdrant.create_collection(
        collection_name=collection_dash,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

#tracker
#tuned engine má iné mapovanie tried
yolo_tuned = "tuned" not in yolo_path
VEHICLE_CLASSES = [1, 2, 3, 5, 7] if yolo_tuned else [0, 1, 2, 3, 4] #bicycle, car, motorcycle, bus, truck

args = SimpleNamespace(
    tracker_type="bytetrack",
    track_high_thresh=0.25,
    track_low_thresh=0.2,
    new_track_thresh=0.45,
    track_buffer=120,
    match_thresh=0.8,
    fuse_score=True,
)
tracker = BYTETracker(args)

#ostrosť obrazu
def laplacian_score(img):
    if img.size == 0: return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

#načítanie snímkov
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


def save_vehicle_view(original_id, embedding, clean_frame, bx1, by1, bx2, by2, slot_name, area, w_img, h_img, aspect_ratio=0.0):
    """Uloží čistý záber (bez boxov) do Qdrantu pre ReID a Dashboard."""

    # 1. Striháme striktne z clean_frame (bez boxov!)
    crop_reid = clean_frame[by1:by2, bx1:bx2]
    if crop_reid.size == 0:
        return

    #zistíme sharpness
    gray = cv2.cvtColor(crop_reid, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    reid_crop_path = f"crops/{original_id}_{slot_name}.jpg"
    cv2.imwrite(reid_crop_path, crop_reid)

    # 2. Široký výrez pre dashboard (z clean_frame)
    bbox_w = bx2 - bx1
    bbox_h = by2 - by1
    pad_w = int(bbox_w * 0.2)
    pad_h = int(bbox_h * 0.2)

    cx1 = max(0, bx1 - pad_w)
    cy1 = max(0, by1 - pad_h)
    cx2 = min(w_img, bx2 + pad_w)
    cy2 = min(h_img, by2 + pad_h)

    clean_crop = clean_frame[cy1:cy2, cx1:cx2]

    # Doplnenie do 4:3 (aby karty v HTML boli rovnaké)
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

    # 3. Uložíme do HLAVNÉ REID KOLEKCIE
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
                "aspect_ratio": aspect_ratio,
                "sharpness": sharpness,
            }
        )]
    )

    # 4. Uložíme / Aktualizujeme DASHBOARD KOLEKCIU
    dash_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, original_id))
    existing = qdrant.retrieve(collection_name="vehicles_dashboard", ids=[dash_id])

    views_list = []
    best_frame = ""

    existing_best_sharpness = 0.0
    if existing:
        views_list = existing[0].payload.get("views", [])
        best_frame = existing[0].payload.get("best_frame_path", "")
        existing_best_sharpness = existing[0].payload.get("best_sharpness", 0.0)

    # Pridáme nový pohľad (ak tam ešte nie je)
    view_data = {"slot": slot_name, "reid_crop_path": reid_crop_path}
    views_list = [v for v in views_list if v["slot"] != slot_name]
    views_list.append(view_data)

    # Ak je to "best" (alebo ešte nemáme žiadny hlavný obrázok), nastavíme ho
    if slot_name == "best" or not best_frame:
        best_frame = frame_path

    qdrant.upsert(
        collection_name="vehicles_dashboard",
        points=[PointStruct(
            id=dash_id,
            vector=embedding.tolist(),
            payload={
                "original_id": original_id,
                "best_frame_path": best_frame,
                "best_sharpness": sharpness if slot_name == "best" else existing_best_sharpness,
                "timestamp": timestamp,
                "camera": "demo_cam",
                "views": views_list
            }
        )]
    )





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
                if not yolo_tuned and cls not in VEHICLE_CLASSES:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                box_w = x2 - x1

                #príliš široké boxy
                if box_w > w * 0.6:
                    continue

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

                if tid not in trails: #add tracked ID to trails
                    trails[tid] = []
                trails[tid].append((cx, cy))
                if len(trails[tid]) > TRAIL_LENGTH: #trail is too long
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
                aspect_ratio = bbox_w / bbox_h

                first_seen = tid in best_tracks
                #zlé boxy
                if first_seen:
                    if bbox_w < 50 or bbox_h < 40:
                        continue
                else:
                    if bbox_w < 30 or bbox_h < 25:
                        continue

                if aspect_ratio > 4.0 or aspect_ratio < 0.2:
                    continue

                #okraj kamery
                MARGIN = 15
                if bx1 <= MARGIN or by1 <= MARGIN or bx2 >= w - MARGIN or by2 >= h - MARGIN:
                    continue

                # Príprava detekcie pre ReID (musí byť xywh so stredom)
                cx_box = (bx1 + bx2) / 2
                cy_box = (by1 + by2) / 2
                dets_xywh = np.array([[cx_box, cy_box, bbox_w, bbox_h]], dtype=np.float32)

                #1. výskyt auta
                if tid not in best_tracks:

                    embs = reid_encoder(frame, dets_xywh)
                    if embs[0] is None:
                        continue

                    embedding = embs[0]

                    #reid search či ho už nepoznáme
                    search_response = qdrant.query_points(
                        collection_name=collection_reid,
                        query=embedding.tolist(),
                        limit=5
                    )

                    matched = False
                    original_id = str(uuid.uuid4())

                    #hodnoty pre nové auto
                    db_best_area = 0
                    db_angles = []

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
                                # Toto auto už máme v best_tracks pod iným tid! Prepíšeme to.
                                tracker.force_track_id(tid, existing_tid)
                                tid = existing_tid  # Aktualizujeme si premennú pre túto snímku
                                print(f"  -> Vizuálne prepísané na staré tid: {existing_tid}")


                            # --- NOVÉ: Zisti existujúce zábery z Qdrantu ---
                            existing_points, _ = qdrant.scroll(
                                collection_name=collection_reid,
                                scroll_filter=models.Filter(
                                    must=[
                                        models.FieldCondition(
                                            key="original_id",
                                            match=models.MatchValue(value=original_id)
                                        )
                                    ]
                                ),
                                limit=20,
                                with_payload=True
                            )

                            for p in existing_points:
                                slot = p.payload.get("slot")
                                p_area = p.payload.get("area", 0)
                                p_aspect = p.payload.get("aspect_ratio", 0)
                                if slot == "best" and p_area > db_best_area:
                                    db_best_area = p_area
                                elif slot.startswith("angle"):
                                    db_angles.append(p_aspect)
                            # ----------------------------------------------

                    if not matched:
                        print(f"ID {tid} -> NOVÉ auto ({original_id[:8]})")

                    # Uložíme prvý záber (aj keď je malý) - vždy, keď je nový tid
                    save_vehicle_view(original_id, embedding, clean_frame, bx1, by1, bx2, by2, "first", area, w, h, aspect_ratio=aspect_ratio)

                    # Inicializujeme best_tracks s prevzatými hodnotami z DB
                    best_tracks[tid] = {
                        "original_id": original_id,
                        "slots": {
                            "first": area,
                            "best": max(db_best_area, area),  # Prevzaté z DB!
                            "angles": db_angles,  # Prevzaté z DB!
                            "exit": False
                        },
                        "last_aspect": aspect_ratio
                    }

                    # Ak sme našli match, mali by sme hneď skúsiť aj best (lebo sme ho mohli vidieť zle)
                    # Ale necháme to na ďalšie snímky, keď bude väčší.

                # 2. AKTUALIZÁCIA (Lepší záber alebo zmena uhla)
                else:
                    track = best_tracks[tid]
                    slots = track["slots"]
                    slot_to_save = None
                    new_area = None
                    new_aspect = None

                    # A) Best (o 30% väčší ako entry — nie hneď pri prvom zábere!)
                    if area > slots["best"] * 1.30:
                        slot_to_save = "best"
                        new_area = area

                    # B) Angle (zmena aspect ratio o 20% a máme menej ako 3 uhly)
                    #    Embedding check pridáme vo Fáze 2, zatiaľ len AR
                    elif len(slots["angles"]) < 3:
                        aspect_change = abs(aspect_ratio - track["last_aspect"]) / track["last_aspect"]
                        if aspect_change > 0.20:
                            slot_to_save = f"angle_{len(slots['angles']) + 1}"
                            new_area = area
                            new_aspect = aspect_ratio

                    # C) Exit (blíži sa k okraju a už máme best)
                    is_near_edge = (bx1 < 50 or by1 < 50 or bx2 > w - 50 or by2 > h - 50)
                    if slot_to_save is None and is_near_edge and not slots["exit"] and slots["best"] > 0:
                        slot_to_save = "exit"
                        new_area = area

                    # Ak treba, extrahujeme nový embedding a uložíme
                    if slot_to_save is not None:
                        embs = reid_encoder(frame, dets_xywh)
                        if embs[0] is not None:
                            print(f"ID {tid} -> Ukladám nový pohľad: {slot_to_save} (plocha: {area})")
                            save_vehicle_view(
                                track["original_id"], embs[0], clean_frame,
                                bx1, by1, bx2, by2, slot_to_save, area, w, h, aspect_ratio=aspect_ratio
                            )
                            # aktualizuj stav až po úspešnom uložení
                            if slot_to_save == "best":
                                slots["best"] = area
                            elif slot_to_save.startswith("angle"):
                                slots["angles"].append(new_aspect)
                                track["last_aspect"] = new_aspect
                            elif slot_to_save == "exit":
                                slots["exit"] = True


        #počet unique ID
        cv2.putText(frame, f"Frame {frame_count} | Unique IDs: {len(all_ids)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(frame)
        cv2.imshow("Demo - Custom Tracking + ReID", frame)

        time.sleep(1.0 / effective_fps) #slow original video to our fps

        if cv2.waitKey(1) & 0xFF == ord('q'):
            generate_html(qdrant)
            break

    writer.release()
    cv2.destroyAllWindows()
    print(f"\nHotovo. Spracovaných snímok: {frame_count}, Unique IDs: {len(all_ids)}")


process_video()
generate_html(qdrant)
qdrant.close()

#todoo
#prerobiť ByteTrack na vlastný tracker
#multi-view brať viac uhlov do db, rovnaké ID nevadí množstvo
#update reid pohľadu nech porovnáva s tým čo je v db - ak vidím auto, match, načítam si to čo je v db a porovnávam s tým asi
#ostrost snimky - laplaceov
#pridať reid do vlastneho trackera, opraviť hladanie lepšej snimky

#multi-view reid: 4 uhly
#1. Entry, 2. Best reid, 3. Angle (2-3), 4. Exit
