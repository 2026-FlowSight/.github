# DEV12: Integrácia Klasifikátora Vozidiel

## Cieľ
Ak R&D Task 1 preukáže, že model (napr. nejaký európsky) má zmysel, integrovať ho do pipeline. Spustiť ho len na výrezoch áut (nie na celom obraze) a uložiť Top-3 výsledky do Qdrant.

## Vstup
- Výrezy áut (z DEV03).
- Model z R&D.

## Výstup
- Qdrant payload rozšírený o `vehicle_make` a `vehicle_model`.

## Postup
1. Načítať model.
2. Spustiť na výreze.
3. Uložiť Top-3 do payloadu.

## Definition of Done
- [ ] V Qdrant sú značky a modely áut.
- [ ] Model beží v rozumnom čase (napr. < 50 ms na výrez).