# DEV05: Filtrovanie Zlých Bboxov

## Cieľ
Zaviesť filtre, ktoré zabránia ukladaniu nekvalitných alebo neúplných detekcií do Qdrant. Ignorovať bboxy, ktoré sú príliš úzke, príliš vysoké, príliš malé, alebo ktoré zasahujú do okraja snímky.

## Vstup
- Detekcie z DEV02.

## Výstup
- Čistejšie dáta v Qdrant (žiadne polovičné autá, žiadne tiene).

## Postup
1. Pridať podmienky: `bbox_w < 50`, `bbox_h < 40` -> skip.
2. Pridať kontrolu pomeru strán: `aspect_ratio > 4.0` alebo `< 0.2` -> skip.
3. Pridať kontrolu okrajov: `bx1 <= 15` alebo `by1 <= 15` atď. -> skip.
4. Alebo iné lepšie filtre z R&D.

## Definition of Done
- [ ] V DB nie sú autá, ktoré sú len čiastočne v zábere.
- [ ] V DB nie sú príliš rozmazané alebo úzke detekcie.