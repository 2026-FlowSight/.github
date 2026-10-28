# DEV13: Integrácia Detekcie Ohňa

## Cieľ
Ak R&D Task 5 preukáže, že dotrénovaný YOLO funguje, integrovať ho do pipeline. Upozornenie na dashboarde.

## Vstup
- Video stream.
- Dotrénovaný YOLO model (z R&D).

## Výstup
- Detekcia ohňa/dymu v reálnom čase.
- Udalosť do dashboardu.

## Postup
1. Načítať model.
2. Spustiť na snímkach (napr. každú 5. snímku).
3. Ak sa nájde oheň, poslať alert.

## Definition of Done
- [ ] Model deteguje oheň na testovacom videu.
- [ ] Alert sa zobrazí v dashboarde.