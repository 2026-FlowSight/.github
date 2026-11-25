# Task 8: Počítanie obsadenosti parkovísk

> **Stav:** prieskum, prototyp a dva testy sú hotové. Riešil: xKazimir.
> Všetky čísla nižšie sú namerané skriptmi v tomto priečinku (súbory vo [`vysledky/`](vysledky/)).

**Report:** [`report/navrh_08_obsadenost_parkovisk.pdf`](report/navrh_08_obsadenost_parkovisk.pdf) (16 strán).
Samostatný doplnok s testom na celom dni: [`report/navrh_08_doplnok_pklot.pdf`](report/navrh_08_doplnok_pklot.pdf) (2 strany).

## TL;DR

1. **Ako to funguje:**
   - Na obraze z kamery sa raz nakreslia parkovacie miesta.
   - YOLO (`models/yolov8n.pt`) nájde autá.
   - Miesto je obsadené, keď spodná časť auta pokrýva aspoň 30 % miesta.
2. **Pamäť:** každé miesto má stav **VOĽNÉ → PRICHÁDZA → OBSADENÉ → ODCHÁDZA?**
   - Za obsadené sa považuje až vtedy, keď tam auto stojí aspoň 8 s.
   - Za voľné až vtedy, keď tam auto 30 s nie je.
   - Keď miesto zakryje iné auto alebo autobus, odpočet sa zastaví.
   - Krátke výpadky YOLO preto počet nezmenia a auto, ktoré len prechádza, sa nezapočíta.
3. **Presnosť:**

   | Test | Bez pamäte | S pamäťou |
   |---|---|---|
   | Krátke video, 45 miest, 960 px ([`vysledky/video_960px_*`](vysledky/)) | 95,6 % miest, priemerná chyba 1,9 auta, počet skáče | **97,8 – 98,3 %**, priemerná chyba 0,65 – 0,86 auta |
   | Celý deň PKLot, 40 miest, fotka každých 5 min ([`vysledky/pklot_cely_box`](vysledky/pklot_cely_box)) | **98,6 %**, priemerná chyba 0,4 auta | 94,6 % (pri 5 min medzerách pamäť len oneskoruje) |

4. **Ako často detegovať:** stačí raz za 2–5 s. Pamäť je nastavená na kontrolu každých 1–5 s.
5. **Na čo dať pozor:**
   - pri rozlíšení 640 px YOLO prehliada malé autá vzadu, preto treba aspoň 960 px;
   - pri kamere, ktorá pozerá takmer zhora, treba v `zones.json` nastaviť `"footprint_ratio": 1.0`, inak presnosť klesne na 76 %;
   - pri zábere priamo zhora (dron) bežné YOLO autá nespozná.

## Spustenie

```bash
pip install -r requirements.txt
cd prototyp

# počítanie áut na videu -> CSV + výpis "O 14:00:00 tam bolo 38 áut / 45 miest"
python parking_occupancy.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
       --model ../../../models/yolov8n.pt --every 1 --start 14:00:00 --csv occupancy.csv --out annotated.mp4
```

Testovacie video `parking_lot_1.mp4` nie je v repe. Stiahneš ho z [olgarose/ParkingLot](https://github.com/olgarose/ParkingLot/raw/master/parking_lot/videos/parking_lot_1.mp4).

<details>
<summary><b>Zopakovanie testov a reportu</b></summary>

```bash
cd prototyp
# test na umelých dátach (kapitola 6)
python simulate.py --out ../vysledky/simulacia/series.csv

# test na videu (kapitola 7): bez pamäte vs. s pamäťou, rôzne nastavenia
python demo_eval.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
       --gt ../data/parking_lot_1/gt.json --model ../../../models/yolov8n.pt \
       --imgsz 960 --t-off 30 --out ../vysledky/video_960px_t30
#   ďalšie varianty: --imgsz 640 (video_640px_t30), --t-off 15 / 60 (video_960px_t15 / _t60)
#   --reuse použije uložené detekcie a YOLO znova nespúšťa
python demo_figures.py --video parking_lot_1.mp4 --zones ../data/parking_lot_1/zones.json \
       --res ../vysledky/video_960px_t30 --model ../../../models/yolov8n.pt --out ../report/obrazky

# test na celom dni z PKLot (kapitola 8), stiahne ~310 MB do data/pklot/
python pklot_download.py --source ufpr05 --date 2013-02-22
python pklot_eval.py --day ../data/pklot/ufpr05_2013-02-22 --model ../../../models/yolov8n.pt \
       --imgsz 1280 --fp-ratio 1.0 --out ../vysledky/pklot_cely_box
#   --fp-ratio 0.4 -> vysledky/pklot_spodok40 (len spodok auta, 76 %)
python pklot_figures.py --day ../data/pklot/ufpr05_2013-02-22 --res ../vysledky/pklot_cely_box --out ../report/obrazky

# report (HTML + PDF, potrebuje Google Chrome)
cd ../report && python build.py --pdf
```
</details>

## Štruktúra

```
prototyp/
├── occupancy_core.py      # pamäť a stavy miest (jadro, bez YOLO a OpenCV)
├── parking_occupancy.py   # hlavný skript: video -> CSV s počtom áut v čase
├── evaluate.py            # porovnanie CSV s ručným počtom (gt.csv: video_s,count)
├── simulate.py            # test na umelých dátach
├── demo_eval.py           # test na videu: bez pamäte vs. s pamäťou
├── demo_figures.py        # obrázky k testu na videu
├── pklot_download.py      # stiahne jeden deň z datasetu PKLot
├── pklot_eval.py          # test na dni z PKLot
├── pklot_figures.py       # obrázky k testu na PKLot
└── zones_example.json     # príklad formátu nakreslených miest
data/parking_lot_1/        # nakreslené miesta (zones.json) a správne odpovede (gt.json) k videu
vysledky/                  # metriky (metrics.json) a priebeh v čase (series.csv) každého testu
report/                    # report: šablóna, build.py, obrázky, hotové PDF
```

**Formát `zones.json`:**
```json
{"lot_id": "P1", "mode": "slots", "footprint_ratio": 0.4,
 "slots": [{"id": "A01", "polygon": [[x, y], [x, y], [x, y], [x, y]]}]}
```
Pre parkovisko bez nakreslených čiar: `{"lot_id": "P2", "mode": "zone", "capacity": 40, "zone": [[x, y], ...]}`.
Funguje aj súbor z nástroja Ultralytics `ParkingPtsSelection`.

<details>
<summary><b>Pôvodné zadanie</b> (klikni)</summary>

**Zadanie:** Preskúmať metódy pre spoľahlivé počítanie áut na parkovisku v reálnom čase (nielen prejazdov, ale trvalo stojacich áut). Nájsť spôsob, ako si udržať stav (koľko áut tam je), aj keď auto na chvíľu zmizne (napr. za stromom alebo ho zakryje iné auto).

**Čo treba spraviť:**
- Preštudovať papers a riešenia z praxe (napr. ako to rieši Frigate NVR, alebo komerčné systémy ako Park Assist).
- Vyskúšať prístup: detekcia áut v definovaných zónach (parkovacie miesta) + logika, ktorá si pamätá, že auto tam bolo aj keď ho YOLO na pár snímok stratí.
- Otestovať na videu ktoré bude v podkladoch.

**Podklady:** Napr. https://www.youtube.com/watch?v=U7HRKjlXK-Y podobné tomu čo budeme mať v praxi alebo si nájdite iné.

**Report:**
- Aké sú obtiažnosti (tiene, prekrytie, autá na okraji)?
- Ako zlepšiť model, aby počítal presnejšie?
- Aká je presnosť (napr. 85 %)?
- Ako často stačí robiť detekciu?

**Výstup:** Skript, ktorý na videu spočíta autá a vypíše, ako sa počet v čase menil (napr. „O 14:00 tam bolo 12 áut, o 14:30 15 áut“).
</details>
