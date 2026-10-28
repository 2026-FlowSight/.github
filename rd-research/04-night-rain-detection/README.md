# Task 4: YOLO v nepriaznivých podmienkach (Noc, dážď)
**Zadanie:** Ako zlepšiť detekciu YOLO v noci a v daždi? Čo je najrýchlejšie výpočtovo?

**Čo treba spraviť:**
- nájsť a stiahnuť videá z ciest, kamier za zlých podmienok napr. 
- Preštudovať papers o Low-light Object Detection, štúdia YOLO v nepriaznivých podmienkách.
- Vyskúšať metódy: zosvetlenie pixelov (napr. gama korekcia), Wienerov filter, alebo dotrénovanie YOLO na nočných dátach.
- Vyskúmať iné metódy detekcie v nepriaznivých podmienkách, nastavenia kamier, ktoré by zlepšili viditeľnosť.
- Zmerať, koľko ms/GFLOPS to zaberie (aby sme neplytvali výkonom).

**Podklady:** Dataset 4 ročné obdobia veľa obrázkov https://github.com/SKKUAutoLab/TSBOW dá sa použiť aj iné.

**Report:** Porovnanie metód (tabuľka: metóda, zlepšenie detekcie, časová náročnosť).

**Výstup:** Skript, ktorý zoberie nočný záber a zlepší ho pre YOLO.