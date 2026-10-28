# DEV14: FastAPI Server

## Cieľ
Vytvoriť REST API, ktoré bude slúžiť ako most medzi Qdrant databázou a webovým dashboardom. Endpointy: `/search` (podľa obrázka/vektora), `/stats` (štatistiky), `/cameras` (zoznam kamier).

## Vstup
- Qdrant databáza.
- Požiadavky z frontendu.

## Výstup
- JSON odpovede.

## Postup
1. Vytvoriť FastAPI aplikáciu.
2. Implementovať endpointy.
3. Otestovať cez Swagger UI (`/docs`).

## Definition of Done
- [ ] API beží na localhoste.
- [ ] Endpointy vracajú dáta z Qdrant.