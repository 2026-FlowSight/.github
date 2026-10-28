# DEV07: Časová a Priestorová Kauzalita

## Cieľ
Implementovať funkciu, ktorá overí, či sa auto stihlo dostať z kamery A na kameru B za daný čas. Ak áno, a ReID skóre je nízke (ale > 0.5), systém to aj tak spojí (Time-Space Match).

## Vstup
- Zoznam kamier s ich pozíciami (GPS alebo vzdialenosť).
- Čas výskytu na kamere A a B.
- ReID skóre.

## Výstup
- Boolean (True/False), či je prechod reálny.
- Funkcia `is_reachable(cam_a, cam_b, time_diff)`.

## Postup
1. Vytvoriť konfiguračný súbor s mapou kamier (vzdialenosti).
2. Vypočítať maximálnu rýchlosť auta (napr. 130 km/h).
3. Porovnať `time_diff` s minimálnym časom potrebným na prechod.

## Definition of Done
- [ ] Funkcia funguje na mock dátach.
- [ ] Dokáže spojiť auto aj keď ReID zlyhal, ale čas a vzdialenosť sedia.