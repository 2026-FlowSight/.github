# Task 2: Multi-view ReID (Rôzne uhly a časy)
**Zadanie:** Preskúmať, ako riešiť ReID, keď máme to isté auto z rôznych uhlov (spredu, zboku, zozadu) a z rôznych kamier. Ako ukladať embeddingy v čase (prvý, stredný, posledný záber).

**Čo treba spraviť:**
- Preštudovať papers o Multi-view Vehicle ReID (napr. z NVIDIA AI City Challenge).
- Zistiť, či funguje priemerovanie embeddingov alebo "Max-pooling" (stačí, ak sedí aspoň jeden).
- Navrhnúť dátovú štruktúru pre Qdrant: ako ukladať viacero vektorov pod jedno original_id.

**Podklady:** Je možné použiť videá z datasetu RoundaboutHD sú v **data/videos/RoundaboutHD/kamera1-4_hd_1min.mp4**. Je tam aj layout, tento dataset je veľmi blízko skutočným záznamom z kamier.

**Report:** Aké sú možnosti? Čo funguje najlepšie pre náš scenár?

**Výstup:** Prototyp, ktorý uloží 3 embeddingy pre jedno auto a pri hľadaní vráti zhodu, ak sedí aspoň jeden.