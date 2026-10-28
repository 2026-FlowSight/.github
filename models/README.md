Tu sú modely, s ktorými budeme pracovať a vylepšovať.
V kóde budeme používať modely .engine, to sú modely knižnice TensorRT, ktoré sú optimalizované na konkretnu GPUčku, technicky si môžete spraviť svoje pre váš hardvér alebo proste použiť toto.

**Ako previesť .pt YOLO model na .engine (TensorRT) tak, aby to bolo FP16:**
- .pt na .onnx (full precision): yolo export model=best.pt format=onnx imgsz=512 simplify=True opset=17
- prevod na fp16 .onxx: python -m modelopt.onnx.autocast --onnx_path yolov8n.onnx --output_path yolov8n_fp16.onnx
- prevod na .engine cez trtexec (treba stiahnuť toolkit): rtexec --onnx=yolov8n_fp16.onnx --saveEngine=yolov8n_fp16.engine --memPoolSize=workspace:4096

Ale treba na to doinštalovať trtexec, modelcast a pod. Claude poradí xd.
Používame **YOLOv26**, ten je vo verzii:
- batch 1 (b1): dokáže na vstupe prijať len 1 snímok
- batch 32 (b32): prejde 32 snímok na jeden prechod

**Ako spustiť model:**
```python 
import tensorrt as trt
DET_CONF_THRES = 0.35  # Zvýšené z 0.10 na 0.25, aby to nereagovalo na každý pixel
VEHICLE_CLASSES = [1, 2, 3, 5, 7]  # bicycle, car, motorcycle, bus
yolo_model = YOLO("models/yolov8n_b1_512.engine", task='detect')

results = yolo_model.predict(
    frame,
    imgsz=512,
    conf=DET_CONF_THRES,
    iou=0.45,
    verbose=False,
)

r = results[0]

#odfiltrovať len triedy čo chceme
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
```

Pre ReID používame **vehicle_reid.engine**.