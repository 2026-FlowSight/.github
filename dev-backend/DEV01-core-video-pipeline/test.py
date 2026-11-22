from ultralytics import YOLO

# Načítame tvoj čistý PyTorch model
model = YOLO("../../models/yolo26n_tuned.pt")

# Export do ONNX s dynamickým rozlíšením (umožní nám potom použiť 512 alebo 960 podľa potreby)
# Pre istotu nastavíme imgsz=960, lebo to je naša cieľová veľkosť
model.export(format="engine", imgsz=960, dynamic=True, simplify=True, quantize=16)
