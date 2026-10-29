# Task 13 - High-Level Architecture Diagram (Initial Draft)

## 📝 Popis
Vytvoriť **vysokoúrovňový blokový diagram architektúry** celého systému FlowSight. Tento diagram slúži ako "mapa" pre celý tím, aby všetci (R&D aj DEV) videli, ako do seba jednotlivé časti zapadajú.

**Dôležité:** Tento diagram **nie je detailný** (nezachádza do implementácie), ale musí obsahovať všetky kľúčové komponenty a ich vzájomné prepojenie. Bude slúžiť aj ako podklad pre prezentáciu mesta.

## 🎯 Čo musí diagram obsahovať

### 1. Vstupné dáta (Data Sources)
*   **IP Kamery / PTZ Kamery:** Streamy z mesta (rôzne rozlíšenia a FPS).
*   **Axis LPR (ANPR):** Samostatná vetva pre kamery, ktoré samé detegujú ŠPZ (posielajú udalosti).
*   **Video súbory:** Možnosť spracovať aj nahraté `.avi` / `.mp4` (pre demo a testovanie).

### 2. Spracovanie (Processing Core)
*   **Video Parser / Loader:** Načítanie a príprava snímok.
*   **YOLO Detekcia:** Nájde autá (triedy: car, truck, bus, motorcycle).
*   **Tracker:** ByteTrack – priradí ID a sleduje trajektóriu.
*   **ReID Model:** Extrakcia embeddingov z výrezov pre porovnávanie.
*   **Logika:** Časová kauzalita, filtrovanie, smer jazdy.

### 3. Úložisko (Storage)
*   **Qdrant (Vector DB):** Ukladanie embeddingov, metadát, časov a kamier.
*   **Lokálny Disk (SSD):** Ukladanie výrezov do `crops/` a širokých záberov do `frames/`.

### 4. Výstup (Output / Dashboard)
*   **FastAPI Server:** Backend pre frontend.
*   **Interaktívna Mapa:** Leaflet, kamery, parkoviská.
*   **Vyhľadávací Dashboard:** Hľadanie podľa obrázka/času.
*   **Export:** PDF/CSV pre policajtov.

### 5. Hardvérová vrstva (Hardware)
*   **Edge zariadenie:** Jetson Orin AGX Orin (ak sa rozhodne o lokálnom nasadení).
*   **Server:** Milestone NVR, ktorý už existuje.

## 🔗 Prepojenia
*   Nakresliť šípky toku dát (napr. Kamera -> YOLO -> Tracker -> ReID -> Qdrant -> Dashboard).
*   Oddeliť **"Live" processing** (reálny čas) a **"Offline" processing** (spracovanie záznamov).
*   Zobraziť, kde presne vstupuje **Axis LPR** (ako samostatný zdroj ŠPZ, ktorý sa pripája do Qdrant).

## 🛠️ Nástroje
*   **Draw.io** (integrované v Jire) alebo **Mermaid** (textový zápis priamo v Markdown).
*   Odporúčam **Mermaid**, lebo sa dá ľahko upraviť a je priamo v Git repozitári.

## 📦 Výstup
*   Obrázok (`.png` alebo `.svg`) uložený v priečinku **`/docs/architecture/high_level.png`**.
*   Alebo **Mermaid kód** v súbore **`/docs/architecture/README.md`**.
*   Krátky popis k diagramu (1 odstavec), ktorý vysvetlí, čo ktorý blok znamená.

## ✅ Definition of Done (Kedy je task hotový)
- [ ] Diagram obsahuje všetky bloky zo zoznamu vyššie.
- [ ] Sú v ňom zakreslené toky dát (šípky).
- [ ] Je jasne oddelený vstup (kamery, Axis), spracovanie (YOLO, ReID), úložisko (Qdrant) a výstup (Dashboard).
- [ ] Diagram je uložený v Git repozitári (v `/docs/architecture/`).
- [ ] Diagram bol odprezentovaný na tímovom stretnutí (alebo aspoň zdieľaný v chate).

