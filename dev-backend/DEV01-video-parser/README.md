# DEV01: Video Parser a Loader

## Cieľ
Vytvoriť modul, ktorý načíta video súbor (MP4/AVI) alebo RTSP stream, rozdelí ho na snímky a pripraví ich pre ďalšie spracovanie (YOLO). Mal by podporovať aj preskakovanie snímok (stride) pre úsporu výkonu.

## Vstup
- Cesta k video súboru (napr. `data/video.mp4`) alebo RTSP URL.
- Voliteľne: `stride` (napr. 2 = spracuj každú druhú snímku).

## Výstup
- Generátor/iterátor, ktorý vracia snímky (numpy array) a ich časové pečiatky (timestamp).
- Uloženie metadát o videu (FPS, rozlíšenie, počet snímok) do konzoly alebo JSONu.

## Postup
1. Použiť `cv2.VideoCapture` alebo inú lepšiu funkciu na načítanie.
2. Implementovať funkciu `load_frames(path, stride)`.
3. Otestovať na krátkom videu (10 sekúnd).

## Definition of Done
- [ ] Skript sa spustí bez chýb.
- [ ] Vypíše počet snímok a FPS.
- [ ] Dokáže vrátiť snímky jedna po druhej.