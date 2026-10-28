# Task 5: Klasifikátor farieb a features auta
**Zadanie:** Ako z výrezu auta opísať farbu a iné features (napr. typ kolesá, poškodenie)? Čo všetko vieme povedať o autu z jeho výrezu (také, ktoré by pomohlo pri jeho identifikácii, vyhľadávaní v DB). Pozrite sa do praxe, ako to robia iné systémy.

**Čo treba spraviť:**
- Preštudovať papers o Vehicle Color Recognition a Feature Extraction.
- Vyskúšať metódy: HSV analýza (dominantná farba), alebo malý klasifikátor (MobileNet).
- Zistiť, aké kategórie farieb sú najlepšie (napr. 8 základných, alebo "svetlá/tmavá").

**Podklady:** Testovacie výrezy áut z našich kamier sú v **data/crops** prípadne **data/frames** alebo v datasete **RoundaboutHD_ReID_subset**.

**Report:** Aká metóda je najpresnejšia a najrýchlejšia?

**Výstup:** Funkcia get_color(crop) + porovnanie metód.