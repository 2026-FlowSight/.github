# DEV18: Integrácia Axis LPR

## Cieľ
Prijímať HTTP POST z Axis kamier s ŠPZ a obrázkom, ukladať do Qdrant.

## Vstup
- HTTP POST z Axis LPR (JSON).

## Výstup
- Uložená ŠPZ a obrázok v Qdrant.

## Postup
1. Vytvoriť Flask/FastAPI endpoint `/axis-lpr`.
2. Parsovať JSON.
3. Uložiť do Qdrant.

## Definition of Done
- [ ] Endpoint prijme mock JSON.
- [ ] Dáta sa uložia do Qdrant.