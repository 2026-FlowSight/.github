# DEV08: Smer Jazdy Vozidla

## Cieľ
Z trajektórie (stredov bboxov) vypočítať vektor pohybu. Určiť, či auto ide dopredu, dozadu, alebo sa otáča (napr. na kruháči).

## Vstup
- Trajektória (trail) z DEV02.

## Výstup
- Uhol (v stupňoch) alebo textový popis (napr. "ide doprava", "otáča sa").

## Postup
1. Zobrať prvý a posledný bod trajektórie.
2. Vypočítať vektor (dx, dy).
3. Prepočítať na uhol.

## Definition of Done
- [ ] Funkcia vráti správny smer na testovacom videu.
- [ ] Je odolná voči šumu (napr. použiť priemer z viacerých bodov).