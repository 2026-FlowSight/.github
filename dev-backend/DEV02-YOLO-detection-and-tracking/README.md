# DEV02: YOLO Detekcia a Tracking (Baseline)

## Cieľ
Integrovať YOLO (TensorRT engine) a ByteTrack do pipeline. Detekovať triedy `car, truck, bus, motorcycle, cycle` a priradiť im unikátne `track_id`. Vykresliť bboxy a traily (trajektórie) na výstupné video.

## Vstup
- Snímky z DEV01.
- YOLO engine (napr. `yolov8n_b1_512.engine`, `yolov8n_b32_512.engine`).

## Výstup
- Upravené video s nakreslenými bboxami, ID a trailmi.
- Dáta o detekciách (súradnice, ID, trieda) pre každú snímku.

## Postup
1. Inicializovať YOLO a ByteTrack.
2. Pre každú snímku spustiť `predict`.
3. Výsledky z `tracker.update` vykresliť na snímku.
4. Uložiť výstupné video.

## Definition of Done
- [ ] Video sa prehráva plynule.
- [ ] Bboxy a ID sedia na autách.
- [ ] Traily sa kreslia správne.