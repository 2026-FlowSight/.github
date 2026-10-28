# DEV06: Multi-query ReID Vyhľadávanie

## Cieľ
Implementovať vyhľadávanie v Qdrant tak, že pri novom ID pošleme vektor a hľadáme `limit=5`. Ak sa nájde zhoda s už známym `original_id` (skóre > threshold), priradíme ho. Tým sa snažíme spojiť auto z kamery 1 a kamery 2.

## Vstup
- Nový ReID embedding (z DEV03).
- Existujúca Qdrant kolekcia.

## Výstup
- Ak sa nájde zhoda: `track_id` sa namapuje na existujúce `original_id`.
- Ak nie: vytvorí sa nové `original_id`.

## Postup
1. Spustiť `query_points` s `limit=5`.
2. Prejsť výsledky a nájsť najvyššie skóre.
3. Ak je skóre > 0.70 (alebo podľa R&D), priradiť `original_id`.

## Definition of Done
- [ ] Pri prechode auta z kamery 1 na kameru 2 sa vypíše "REID MATCH".
- [ ] Threshold je nastaviteľný v konfigurácii.