# DEV06: Integrácia Klasifikátora Vozidiel

## Cieľ
Keďže výskum (R&D) ukázal, že rozpoznávanie konkrétnej značky a modelu (napr. Škoda Octavia) je z našich kamier nereálne, integrujeme klasifikátor, ktorý rozlíši **typ karosérie** (napr. sedan, pickup, SUV, hatchback, dodávka). Tento model beží len na výrezoch áut (nie na celom obraze) a výsledok ukladáme do Qdrant.

## Vstup
- Výrezy áut (z DEV01 - Core Pipeline, konkrétne z priečinka `crops/`).
- Model z R&D (natrénovaný na klasifikáciu typu karosérie).

## Výstup
- Qdrant payload rozšírený o pole `vehicle_type` (napr. `"sedan"`, `"pickup"`, `"SUV"`, `"van"`).

## Postup
1. Načítať model (napr. MobileNet alebo EfficientNet) z R&D.
2. Spustiť inferenciu na výreze auta.
3. Uložiť výsledný typ (Top-1 alebo Top-3) do Qdrant payloadu.

## Definition of Done
- [ ] V Qdrant sú pre autá uložené typy vozidiel (sedan, pickup, atď.)
- [ ] Model beží v rozumnom čase (napr. < 50 ms na výrez)
- [ ] Presnosť modelu je otestovaná na našich výrezoch z RoundaboutHD
