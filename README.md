# 🚦 FlowSight: Inteligentný kamerový systém pre mesto Pezinok

## 📌 O projekte
FlowSight je výskumno-vývojový projekt zameraný na analýzu mestských kamerových záznamov pomocou počítačového videnia (YOLO, ReID) a vektorových databáz (Qdrant). Cieľom je poskytnúť mestu nástroj na sledovanie dopravy, obsadenosti parkovísk a vyhľadávanie vozidiel v archíve.

## 📂 Štruktúra repozitára
*   `/rd-research/` – Výskumné úlohy (prieskum papers, testovanie modelov, reporty).
*   `/dev-backend/` – Vývojové úlohy (Python skripty, spracovanie videa, Qdrant).
*   `/dev-dashboard/` – Vývojové úlohy (Webové rozhranie, API, vizualizácie).
*   `/data/` – Testovacie videá a výrezy (tento priečinok nie je súčasťou gitu, dáta sa zdieľajú cez SharePoint/OneDrive).

---

<details>
<summary><h2>R&D Tasky (Klikni pre rozbalenie)</h2></summary>

### 01 - Klasifikácia značky a modelu auta (EU)
- [ ] Preštudované papers o európskych autách
- [ ] Vyskúšané aspoň 2 modely
- [ ] Otestované na našich výrezoch
- [ ] Napísaný report a odprezentované

### 02 - Multi-view ReID a duplikáty
- [ ] Preštudované papers o multi-view ReID
- [ ] Vyskúšaný Max-pooling alebo priemerovanie
- [ ] Navrhnutá štruktúra pre Qdrant
- [ ] Otestované na videách s prekryvom

### 03 - Ukladanie a agregácia dát (1TB limit)
- [ ] Preštudované stratégie pre time-series a Qdrant
- [ ] Navrhnutý dátový model
- [ ] Vypočítané odhady spotreby disku

### 04 - YOLO v noci a daždi
- [ ] Preštudované papers o low-light detekcii
- [ ] Vyskúšané aspoň 2 metódy (napr. gama + Wiener)
- [ ] Zmeraná časová náročnosť
- [ ] Odporúčanie, čo použiť

### 05 - Klasifikátor farieb a features
- [ ] Preštudované metódy pre rozpoznávanie farieb
- [ ] Vyskúšaná HSV analýza a prípadne CNN
- [ ] Navrhnuté kategórie farieb

### 06 - Príprava na Axis integráciu (ŠPZ)
- [ ] Preštudovaná dokumentácia Axis LPR
- [ ] Navrhnutý API endpoint
- [ ] Vytvorený mock JSON

### 07 - Príprava na detekciu presetov (PTZ)
- [ ] Preštudované VAPIX API
- [ ] Navrhnutá architektúra pre správu presetov

### 08 - Počítanie obsadenosti parkovísk
- [ ] Preštudované metódy pre počítanie
- [ ] Vyskúšané na videu z parkoviska
- [ ] Napísaný report s presnosťou

### 09 - Detekcia nehôd a podozrivého správania
- [ ] Preštudované metódy pre detekciu nehôd
- [ ] Navrhnuté pravidlá
- [ ] Otestované na videu

### 10 - Rozlíšenie áut s rovnakým modelom a farbou
- [ ] Preštudované metódy
- [ ] Navrhnuté možnosti
- [ ] Odporúčanie, čo má zmysel

### 11 - Časová a priestorová kauzalita
- [ ] Preštudované metódy
- [ ] Navrhnutý graf prechodov
- [ ] Implementovaná funkcia

### 12 - Detekcia ohňa a dymu
- [ ] Preštudované papers o detekcii ohňa
- [ ] Vyskúšaný aspoň 1 model
- [ ] Otestované na videu + negatívne príklady
- [ ] Zmeraná výpočtová náročnosť
- [ ] Napísaný report

</details>

---

<details>
<summary><h2>DEV Backend Tasky (Klikni pre rozbalenie)</h2></summary>

### DEV01 - Video Parser a Loader
- [ ] Skript sa spustí bez chýb
- [ ] Vypíše počet snímok a FPS
- [ ] Dokáže vrátiť snímky jedna po druhej

### DEV02 - YOLO Detekcia a Tracking
- [ ] Video sa prehráva plynule
- [ ] Bboxy a ID sedia na autách
- [ ] Traily sa kreslia správne

### DEV03 - ReID Embeddingy a Qdrant Storage
- [ ] V Qdrant pribúdajú body pri nových autách
- [ ] Payload obsahuje `original_id`, `frame_path`, `timestamp`, `camera`
- [ ] Obrázky sa ukladajú do priečinka `frames/` a `crops/`

### DEV04 - Výber Najlepšieho Záberu
- [ ] V DB sú pre jedno auto rôzne uhly (ak boli dostupné)
- [ ] Staré, nekvalitné zábery sa nahrádzajú lepšími

### DEV05 - Filtrovanie Zlých Bboxov
- [ ] V DB nie sú autá, ktoré sú len čiastočne v zábere
- [ ] V DB nie sú príliš rozmazané alebo úzke detekcie

### DEV06 - Multi-query ReID Vyhľadávanie
- [ ] Pri prechode auta z kamery 1 na kameru 2 sa vypíše "REID MATCH"
- [ ] Threshold je nastaviteľný v konfigurácii

### DEV07 - Časová a Priestorová Kauzalita
- [ ] Funkcia funguje na mock dátach
- [ ] Dokáže spojiť auto aj keď ReID zlyhal, ale čas a vzdialenosť sedia

### DEV08 - Smer Jazdy Vozidla
- [ ] Funkcia vráti správny smer na testovacom videu
- [ ] Je odolná voči šumu (napr. použiť priemer z viacerých bodov)

### DEV09 - Počítanie Áut na Parkovisku
- [ ] Skript spočíta autá na testovacom videu
- [ ] Výstup je CSV s časom a počtom áut

### DEV10 - Klasifikácia Farieb (HSV)
- [ ] Funkcia vráti farbu pre testovacie výrezy
- [ ] Výsledky sú aspoň na 80 % správne pri jasných farbách

### DEV11 - Mapovanie Presetov (PTZ)
- [ ] Konfigurácia existuje
- [ ] Skript dokáže zistiť aktuálny preset (alebo aspoň manuálne prepnutie)

### DEV12 - Integrácia Klasifikátora Vozidiel
- [ ] V Qdrant sú značky a modely áut
- [ ] Model beží v rozumnom čase (napr. < 50 ms na výrez)

### DEV13 - Integrácia Detekcie Ohňa
- [ ] Model deteguje oheň na testovacom videu
- [ ] Alert sa zobrazí v dashboarde

### DEV18 - Integrácia Axis LPR
- [ ] Endpoint prijme mock JSON
- [ ] Dáta sa uložia do Qdrant

### DEV19 - Detekcia Nehôd (Pravidlá)
- [ ] Pravidlá bežia na CPU
- [ ] Vygenerujú alert pri simulovanej nehode

### DEV20 - OCR pre Čítanie Presetov
- [ ] OCR prečíta text aspoň na 90 % testovacích snímok
- [ ] Výsledok sa použije na prepnutie trackera

</details>

---

<details>
<summary><h2>DEV Dashboard Tasky (Klikni pre rozbalenie)</h2></summary>

### DEV14 - FastAPI Server
- [ ] API beží na localhoste
- [ ] Endpointy vracajú dáta z Qdrant

### DEV15 - Interaktívna Mapa (Leaflet)
- [ ] Mapa sa načíta
- [ ] Vrstvy sa dajú vypnúť/zapnúť
- [ ] Kamery sú klikateľné

### DEV16 - Vyhľadávací Dashboard (Frontend)
- [ ] Nahrávanie obrázka funguje
- [ ] Výsledky sa zobrazia do 2 sekúnd

### DEV17 - Export Výsledkov (PDF/CSV)
- [ ] Export funguje pre mock dáta
- [ ] Súbor sa stiahne do prehliadača

</details>

---

## 📝 Ako pracovať s týmto repozitárom (bez branches)
1. Pred prácou si vždy stiahni najnovšie zmeny: `git pull origin main`.
2. Pracuj IBA vo svojom priečinku pre tvoj pridelený task(napr. `/dev-backend/DEV01-video-parser/`).
3. Ak potrebuješ zmeniť niečo mimo svojho priečinka, najprv sa opýtaj v tímovom chate.
4. Keď skončíš, nahraj zmeny: `git add .`, `git commit -m "Dokončený DEV01"`, `git push origin main`
