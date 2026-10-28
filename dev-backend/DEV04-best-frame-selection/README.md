# DEV04: Výber Najlepšieho Záberu (First, Middle, Last)

## Cieľ
Implementovať logiku, ktorá pre každé `track_id` sleduje, ktorý výrez auta je najkvalitnejší (napr. najväčšia plocha bboxu, najlepší pomer strán). Uložiť prvý, stredný a posledný záber (alebo aspoň ten najlepší) pre potreby ReID.
Výstup výskumu pre Multi-View-ReID.

## Vstup
- Dáta z DEV03 (priebežné detekcie).

## Výstup
- V Qdrant budú pre jedno auto uložené 1-3 rôzne embeddingy (z rôznych fáz).
- Aktualizácia existujúceho bodu, ak príde lepší záber.

## Postup
1. Sledovať `area` (plochu) pre každé `tid`.
2. Ak príde väčší bbox, prepísať starý embedding v Qdrant.
3. Voliteľne: Uložiť aj "prvý" a "posledný" záber pre multi-view ReID.
4. Zvoliť iné metódy, ktoré boli vyskúmané v R&D.

## Definition of Done
- [ ] V DB sú pre jedno auto rôzne uhly (ak boli dostupné).
- [ ] Staré, nekvalitné zábery sa nahrádzajú lepšími.