# DEV09: Počítanie Áut na Parkovisku

## Cieľ
Vytvoriť modul, ktorý definuje zóny (parkovacie miesta) a počíta, koľko áut je v nich. Udržiavať si stav (počet áut v čase) a vedieť, kedy auto odišlo/prišlo.

## Vstup
- Video z parkoviska.
- Definícia parkovacích zón (súradnice v obraze).

## Výstup
- Počet áut na parkovisku v každom čase.
- CSV/JSON s časovou osou obsadenosti.

## Postup
1. Definovať zóny (polygóny) pre parkovacie miesta.
2. Pri každej detekcii zistiť, do ktorej zóny patrí.
3. Udržiavať stav (set áut v zóne).
4. Ak auto zmizne, počkať X sekúnd a potom ho odpočítať.

## Definition of Done
- [ ] Skript spočíta autá na testovacom videu.
- [ ] Výstup je CSV s časom a počtom áut.