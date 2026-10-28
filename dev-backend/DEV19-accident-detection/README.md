# DEV19: Detekcia Nehôd (Pravidlá)

## Cieľ
Implementovať pravidlá z R&D Task 9 (napr. prekrytie bboxov + náhle zastavenie) a generovať udalosti.

## Vstup
- Dáta z trackera (trajektórie, rýchlosti).

## Výstup
- Udalosť "podozrenie na nehodu" s časom a kamerou.

## Postup
1. Sledovať rýchlosť auta (zmena polohy).
2. Ak dôjde k náhlemu poklesu rýchlosti + prekrytiu s iným autom -> alert.

## Definition of Done
- [ ] Pravidlá bežia na CPU.
- [ ] Vygenerujú alert pri simulovanej nehode.