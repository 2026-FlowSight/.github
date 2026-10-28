# Task 3: Časová a priestorová kauzalita
**Zadanie:** Ak poznáme mapu kamier a vzdialenosti, ako ohodnotiť, či sa auto stihlo dostať z kamery A na kameru B? Ako to využiť na zlepšenie trackingu (napr. ak ReID zlyhá, ale čas a vzdialenosť sedia, môžeme to spojiť).

**Čo treba spraviť:**
- Preštudovať papers o spatio-temporal reasoning v multi-camera trackingu.
- Navrhnúť jednoduchý graf prechodov (ktorá kamera je odkiaľ dosiahnuteľná za aký čas).

**Podklady:** Keď bude mapa s kamerami, tak spravíme mock mapu.

**Report:** Ako to funguje? Aké sú limity?

**Výstup:** Funkcia is_reachable(cam_a, cam_b, time_diff).