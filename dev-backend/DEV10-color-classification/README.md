# DEV10: Klasifikácia Farieb (HSV)

## Cieľ
Implementovať HSV alebo iný (výsledok R&D) klasifikátor farieb (8 alebo viac kategórií) pre výrezy áut. Uložiť farbu do Qdrant payloadu.

## Vstup
- Výrez auta (obrázok).

## Výstup
- Názov farby (napr. "biela", "čierna", "červená").
- Uloženie do Qdrant payloadu.

## Postup (výsledok R&D)
1. Previesť obrázok do HSV.
2. Zistiť dominantnú farbu (napr. histogram).
3. Priradiť do kategórie.

## Definition of Done
- [ ] Funkcia vráti farbu pre testovacie výrezy.
- [ ] Výsledky sú aspoň na 80 % správne pri jasných farbách.