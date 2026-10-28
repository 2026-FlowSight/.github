# DEV11: Mapovanie Presetov (PTZ)

## Cieľ
Vytvoriť konfiguračný súbor (YAML/JSON), kde bude pre každú PTZ kameru zoznam presetov (názov, pan/tilt hodnoty, čo zaberá). Skript, ktorý sleduje zmeny presetov (cez API alebo manuálne).

## Vstup
- Zoznam kamier a ich presetov.
- Prístup k API kamery (VAPIX) alebo manuálne zadanie.

## Výstup
- Konfigurácia presetov.
- Modul, ktorý povie, v akom presete kamera je.

## Postup
1. Vytvoriť `presets.yaml` so štruktúrou.
2. Implementovať čítanie aktuálneho presetu z kamery.
3. Otestovať na jednej PTZ kamere (ak je dostupná).

## Definition of Done
- [ ] Konfigurácia existuje.
- [ ] Skript dokáže zistiť aktuálny preset (alebo aspoň manuálne prepnutie).