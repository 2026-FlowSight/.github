# R&D 12: Detekcia Ohňa a Dymu (Fire & Smoke Detection)

## Cieľ výskumu
Zistiť, či a ako efektívne dokážeme detegovať oheň a dym z mestských kamier. Cieľom nie je nasadenie do produkcie (to je DEV-13), ale **prieskum možností, testovanie presnosti a výpočtovej náročnosti**.

## Čo treba preskúmať (Research)
1.  **Existujúce modely a datasety:** Preštudovať papers o detekcii ohňa (napr. zamerané na CCTV/urbánne prostredie). Nájsť open-source datasety (napr. `MultiFire20K` – ohne v meste, `D-Fire`, alebo datasety na Zenode).
2.  **Prístupy:**
    *   *Klasická detekcia (YOLO):* Dotrénovať YOLO26n (alebo YOLOv8n) na datasete s ohňom. Aká je presnosť? Aké sú falošné poplachy (napr. oranžové svetlá, západy slnka)?
    *   *Klasifikácia (CNN):* Použiť klasifikátor na výrezy, ktoré YOLO označí ako "podozrivé".
    *   *Časová analýza:* Ako rozlíšiť skutočný oheň od statického obrázka (napr. oheň na plagáte)? (Napr. sledovaním, či sa pixely menia v čase).
3.  **Výpočtová náročnosť:** Zmerať, koľko ms zaberie inferencia. Je to realizovateľné na Jetsone popri YOLO pre autá?

## Podklady 
*   Testovacie video s ohňom (napr. z `MultiFire20K` (https://zenodo.org/records/17047113) alebo z YouTube – bezpečné zábery).
*   Negatívne príklady (napr. oranžové auto, západ slnka, červené svetlo), aby model nerobil falošné poplachy. sú napr. v `MS-FSDB` (https://github.com/XiaoyiHan6/MS-FSDB/tree/main) ten obsahuje 9000 negative samples na pomýlenie modelu.
*   Je možné použiť aj iné datasety, je to jedno.

## Výstup 
1.  **Report (Markdown):**
    *   Aké datasety a modely ste našli.
    *   Aká je presnosť (napr. mAP, F1) na testovacích dátach.
    *   Aké sú falošné poplachy a ako ich eliminovať.
    *   Odporúčanie: Má zmysel to nasadiť? Ak áno, s akým modelom a za akých podmienok?
2.  **Prototyp (Python skript / Jupyter notebook):**
    *   Skript, ktorý načíta video, spustí detekciu ohňa a vykreslí bboxy.
    *   Zmeria čas inferencie.
3.  **Prezentácia (5 minút):**
    *   Ukázať demo na videu.
    *   Povedať, či to má zmysel pre TP1 alebo až pre TP2.

## Definition of Done 
- [ ] Preštudované aspoň 2 vedecké papers o detekcii ohňa.
- [ ] Vyskúšaný aspoň 1 model (napr. YOLO dotrénovaný na ohni).
- [ ] Otestované na videu s ohňom a negatívnych príkladoch.
- [ ] Zmeraná výpočtová náročnosť (ms/snímka).
- [ ] Napísaný report a odprezentované na stretku.