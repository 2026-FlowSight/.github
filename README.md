# 🚦 FlowSight: Inteligentný kamerový systém pre mesto Pezinok

## 📌 O projekte
FlowSight je výskumno-vývojový projekt zameraný na analýzu mestských kamerových záznamov pomocou počítačového videnia (YOLO, ReID) a vektorových databáz (Qdrant). Cieľom je poskytnúť mestu nástroj na sledovanie dopravy, obsadenosti parkovísk a vyhľadávanie vozidiel v archíve.

## 📂 Štruktúra repozitára
*   `/rd-research/` – Výskumné úlohy (prieskum papers, testovanie modelov, reporty).
*   `/dev-backend/` – Vývojové úlohy (Python skripty, spracovanie videa, Qdrant).
*   `/dev-dashboard/` – Vývojové úlohy (Webové rozhranie, API, vizualizácie).
*   `/data/` – Testovacie videá a výrezy (tento priečinok nie je súčasťou gitu, dáta sa zdieľajú cez SharePoint/OneDrive).

---

## Geografické informácie o RoundaboutHD

**Kamera 1**: [39°55'37.1"N 86°06'22.3"W]
https://maps.app.goo.gl/U8wMKaLVq7Qu1EdVA

**Kamera 2**: [39°55'37.2"N 86°05'56.2"W]
https://maps.app.goo.gl/LZ9wMKXw9S1nDPik6

**Kamera 3**: [39°55'38.6"N 86°05'20.1"W]
https://maps.app.goo.gl/g3aq8n5pEGGnUEMR9

**Kamera 4**: [39°55'36.8"N 86°04'47.9"W]
https://maps.app.goo.gl/fr8T9Eng3LXddmJv8

**Ostatné parametre (natočenie, uhol, pohľad,... ) a pohľady z kamier budú uložené** v /data/RoundaboutHD_metadata/.

---

<details>
<summary><h2>R&D Tasky (Klikni pre rozbalenie)</h2></summary>

### 01 - Klasifikácia značky a modelu auta (EU)
**Popis:** Cieľom je zistiť, aké sú dostupné metódy na rozpoznanie značky (napr. Škoda, VW) a modelu európskeho auta z výrezu kamery, a overiť, či niektorý z modelov dosahuje použiteľnú presnosť na našich dátach. Výstupom je odporúčanie, ktorý prístup má zmysel ďalej rozvíjať.
- [X] Preštudované papers o európskych autách
- [X] Vyskúšané aspoň 2 modely
- [X] Otestované na našich výrezoch
- [X] Napísaný report a odprezentované

### 02 - Multi-view ReID a duplikáty
**Popis:** Ide o to, aby systém rozpoznal to isté auto z rôznych kamier (multi-view) a zároveň vedel rozlíšiť, kedy ide o duplikát v Qdrante. Cieľom je navrhnúť spôsob agregácie embeddingov (napr. max-pooling alebo priemerovanie) a štruktúru kolekcie v Qdrante tak, aby vyhľadávanie bolo presné a rýchle.
- [] Preštudované papers o multi-view ReID
- [ ] Vyskúšaný Max-pooling alebo priemerovanie
- [X] Navrhnutá štruktúra pre Qdrant
- [X] Otestované na videách s prekryvom

### 03 - Ukladanie a agregácia dát (1TB limit)
**Popis:** Systém bude ukladať veľké množstvo metadát a embeddingov, pričom disk je limitovaný na 1 TB. Úlohou je preskúmať stratégie ukladania časových radov a agregácie v Qdrante, navrhnúť dátový model a vypočítať, koľko miesta zaberie prevádzka za rozumné obdobie.
- [ ] Preštudované stratégie pre time-series a Qdrant
- [ ] Navrhnutý dátový model
- [ ] Vypočítané odhady spotreby disku

### 04 - YOLO v noci a daždi
**Popis:** Štandardné YOLO modely výrazne strácajú presnosť pri slabom osvetlení a daždi. Cieľom je preskúmať metódy predspracovania (napr. gama korekcia, Wienerov filter) a overiť, ktoré z nich reálne zlepšia detekciu na našich nočných a daždivých videách, vrátane merania výpočtovej náročnosti.
- [X] Preštudované papers o low-light detekcii
- [X] Vyskúšané aspoň 2 metódy (napr. gama + Wiener)
- [X] Zmeraná časová náročnosť
- [X] Odporúčanie, čo použiť

### 05 - Klasifikátor farieb a features
**Popis:** Pre vyhľadávanie áut podľa farby je potrebné spoľahlivo určiť farbu z výrezu. Úlohou je preskúmať metódy rozpoznávania farieb, vyskúšať HSV analýzu a prípadne CNN, a navrhnúť sadu kategórií farieb, ktoré budú pre používateľov zmysluplné a zároveň dobre rozlíšiteľné.
- [X] Preštudované metódy pre rozpoznávanie farieb
- [X] Vyskúšaná HSV analýza a prípadne CNN
- [X] Navrhnuté kategórie farieb

### 06 - Príprava na Axis integráciu (ŠPZ)
**Popis:** Cieľom je pripraviť sa na napojenie na Axis LPR (rozpoznávanie ŠPZ) tak, aby systém vedel prijímať dáta o poznávacích značkách. Úlohou je preštudovať dokumentáciu, navrhnúť API endpoint a pripraviť mock JSON, na ktorom sa dá integrovať ešte pred dodaním reálnej kamery.
- [ ] Preštudovaná dokumentácia Axis LPR
- [ ] Navrhnutý API endpoint
- [ ] Vytvorený mock JSON

### 07 - Príprava na detekciu presetov (PTZ)
**Popis:** PTZ kamery sa otáčajú medzi presetmi a systém musí vedieť, v akom režime práve snímajú. Cieľom je preskúmať VAPIX API a navrhnúť architektúru, ktorá umožní zisťovať a spravovať aktuálny preset kamery.
- [ ] Preštudované VAPIX API
- [ ] Navrhnutá architektúra pre správu presetov

### 08 - Počítanie obsadenosti parkovísk
**Popis:** Mesto chce vedieť, ako sú parkoviská obsadené. Úlohou je preskúmať metódy počítania áut na parkovisku, vyskúšať ich na videu z reálneho parkoviska a napísať report s dosiahnutou presnosťou, aby bolo jasné, či je výsledok použiteľný v praxi.
- [X] Preštudované metódy pre počítanie
- [X] Vyskúšané na videu z parkoviska
- [X] Napísaný report s presnosťou

### 09 - Detekcia nehôd a podozrivého správania
**Popis:** Cieľom je navrhnúť pravidlá, ktoré dokážu z tracking dát odhaliť nehodu alebo podozrivé správanie (napr. náhle zastavenie, nezvyčajný pohyb). Úlohou je preskúmať existujúce metódy, navrhnúť konkrétne pravidlá a otestovať ich na videu.
- [ ] Preštudované metódy pre detekciu nehôd
- [ ] Navrhnuté pravidlá
- [ ] Otestované na videu

### 10 - Rozlíšenie áut s rovnakým modelom a farbou
**Popis:** Dve autá rovnakej značky, modelu a farby môžu vyzerať takmer identicky. Úlohou je preskúmať metódy, ktoré ich dokážu odlíšiť (napr. detaily ako kolesá, nálepky, poškodenia) a navrhnúť, ktoré možnosti majú reálny zmysel nasadiť.
- [ ] Preštudované metódy
- [ ] Navrhnuté možnosti
- [ ] Odporúčanie, čo má zmysel

### 11 - Časová a priestorová kauzalita
**Popis:** Ak ReID zlyhá, auto sa dá stále spojiť podľa toho, kedy a kde sa objavilo — musí to však dávať fyzikálny zmysel (nemožno byť na dvoch miestach naraz). Cieľom je preskúmať metódy, navrhnúť graf prechodov medzi kamerami a implementovať funkciu, ktorá takéto spojenie overí.
- [ ] Preštudované metódy
- [ ] Navrhnutý graf prechodov
- [ ] Implementovaná funkcia

### 12 - Detekcia ohňa a dymu
**Popis:** Cieľom je overiť, či existujúci alebo dostupný model dokáže spoľahlivo detegovať oheň a dym na mestských kamerách, a to aj s ohľadom na falošné poplachy (západ slnka, červené svetlá). Úlohou je preskúmať papers, vyskúšať aspoň jeden model, otestovať ho na videu vrátane negatívnych príkladov, zmerať výpočtovú náročnosť a napísať report.
- [X] Preštudované papers o detekcii ohňa
- [X] Vyskúšaný aspoň 1 model
- [X] Otestované na videu + negatívne príklady
- [X] Zmeraná výpočtová náročnosť
- [X] Napísaný report

### 13 - High-Level Architecture Diagram
**Popis:** Cieľom je vytvoriť vysokúrovňový blokový diagram systému FlowSight, ktorý zobrazí hlavné komponenty a tok dát. Diagram slúži ako mapa pre tím (R&D aj DEV), aby všetci videli, ako do seba zapadá vstup z kamier, spracovanie (YOLO, ReID), ukladanie (Qdrant) a výstup (Dashboard, Mapa). Musí obsahovať aj vetvu pre Axis LPR a hardvérovú vrstvu (Jetson, Server). Výstupom je obrázok alebo Mermaid kód v `/docs/architecture/`.
- [X] Navrhnutá štruktúra blokov (Kamery, YOLO, ReID, Qdrant, Dashboard)
- [X] Zakreslené toky dát (šípky)
- [X] Oddelená vetva pre Axis LPR a hardvér
- [X] Diagram uložený v `/docs/architecture/`
- [X] Odprezentované na tímovom stretnutí

</details>

---

<details>
<summary><h2>DEV Backend Tasky (Klikni pre rozbalenie)</h2></summary>

### DEV01 - Core Video Pipeline (Parser, YOLO, Tracking, ReID, Filtre, Smer)
**Popis:** Vytvoriť kompletný spracovateľský reťazec (pipeline) pre jedno video. Na vstupe je video súbor (RoundaboutHD), na výstupe je spracované video s nakreslenými bboxami, trailmi a uloženými dátami v Qdrant databáze. Súčasťou je aj logika pre filtrovanie zlých detekcií a výpočet smeru jazdy.

**Čo task zahŕňa (pôvodné časti):**
*   **Video Parser a Loader:** Načítanie videa, zistenie FPS a počtu snímok, vracanie snímok (so stride).
*   **YOLO Detekcia a Tracking:** Detekcia vozidiel, priradenie ID (ByteTrack) a kreslenie trajektórií.
*   **Filtrovanie zlých bboxov:** Odstránenie detekcií, ktoré sú na okraji kamery, príliš úzke alebo malé.
*   **ReID Storage a Najlepší záber:** Extrakcia embeddingov, výber najlepšieho záberu (prvý/stredný/posledný) a ukladanie do Qdrant a na disk (`frames/`, `crops/`).
*   **Smer jazdy vozidla:** Výpočet vektora pohybu z trajektórie a určenie smeru.

**Checklist:**
- [ ] Skript sa spustí bez chýb (načíta video, vypíše FPS a počet snímok)
- [ ] Video sa prehráva plynule, bboxy a ID sedia na autách
- [ ] Traily (trajektórie) sa kreslia správne
- [ ] V DB nie sú autá, ktoré sú len čiastočne v zábere (kontrola MARGIN)
- [ ] V DB nie sú príliš rozmazané alebo úzke detekcie (kontrola aspect_ratio)
- [ ] V Qdrant pribúdajú body pri nových autách (ukladá sa `original_id`, `frame_path`, `timestamp`, `camera`)
- [ ] Obrázky sa ukladajú do priečinka `frames/` a `crops/` (ukladá sa najlepší záber)
- [ ] Funkcia vráti správny smer jazdy vozidla na testovacom videu (odolná voči šumu)

### DEV02 - Časová a Priestorová Kauzalita
- [] Funkcia funguje na mock dátach
- [] Dokáže spojiť auto aj keď ReID zlyhal, ale čas a vzdialenosť sedia

### DEV03 - Počítanie Áut na Parkovisku
- [X] Skript spočíta autá na testovacom videu
- [] Výstup je CSV s časom a počtom áut

### DEV04 - Klasifikácia Farieb (HSV)
- [X] Funkcia vráti farbu pre testovacie výrezy
- [X] Výsledky sú aspoň na 80 % správne pri jasných farbách

### DEV05 - Mapovanie Presetov (PTZ)
- [ ] Konfigurácia existuje
- [ ] Skript dokáže zistiť aktuálny preset (alebo aspoň manuálne prepnutie)

### DEV06 - Integrácia Klasifikátora Typu Vozidla
**Popis:** Keďže výskum (R&D) ukázal, že rozpoznávanie konkrétnej značky a modelu (napr. Škoda Octavia) je z našich kamier nereálne, integrujeme klasifikátor, ktorý rozlíši **typ karosérie** (napr. sedan, pickup, SUV, hatchback, dodávka). Tento model beží na výrezoch áut a výsledok ukladáme do Qdrant.
- [ ] V Qdrant sú pre autá uložené typy vozidiel (sedan, pickup, atď.)
- [ ] Model beží v rozumnom čase (napr. < 50 ms na výrez)
- [ ] Presnosť modelu je otestovaná na našich výrezoch z RoundaboutHD

### DEV07 - Integrácia Detekcie Ohňa
- [X] Model deteguje oheň na testovacom videu
- [ ] Alert sa zobrazí v dashboarde

### DEV08 - Integrácia Axis LPR
- [ ] Endpoint prijme mock JSON
- [ ] Dáta sa uložia do Qdrant

### DEV09 - Detekcia Nehôd (Pravidlá)
- [ ] Pravidlá bežia na CPU
- [ ] Vygenerujú alert pri simulovanej nehode

### DEV10 - OCR pre Čítanie Presetov
- [ ] OCR prečíta text aspoň na 90 % testovacích snímok
- [ ] Výsledok sa použije na prepnutie trackera

</details>

---

<details>
<summary><h2>DEV Dashboard Tasky (Klikni pre rozbalenie)</h2></summary>

### DEV11 - FastAPI Server
- [X] API beží na localhoste
- [X] Endpointy vracajú dáta z Qdrant

### DEV12 - Interaktívna Mapa (Leaflet)
- [X] Mapa sa načíta
- [X] Vrstvy sa dajú vypnúť/zapnúť
- [X] Kamery sú klikateľné

### DEV13 - Vyhľadávací Dashboard (Frontend)
- [X] Nahrávanie obrázka funguje
- [X] Výsledky sa zobrazia do 2 sekúnd

### DEV14 - Export Výsledkov (PDF/CSV)
- [ ] Export funguje pre mock dáta
- [ ] Súbor sa stiahne do prehliadača

</details>

---

## 📝 Ako pracovať s týmto repozitárom (bez branches)
1. Pred prácou si vždy stiahni najnovšie zmeny: `git pull origin main`.
2. Pracuj IBA vo svojom priečinku pre tvoj pridelený task(napr. `/dev-backend/DEV01-video-parser/`).
3. Ak potrebuješ zmeniť niečo mimo svojho priečinka, najprv sa opýtaj v tímovom chate.
4. Keď skončíš, nahraj zmeny: `git add .`, `git commit -m "Dokončený DEV01"`, `git push origin main`
