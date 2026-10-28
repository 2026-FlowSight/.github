# DEV20: OCR pre Čítanie Presetov

## Cieľ
Ak sa nedá získať preset z API, použiť OCR (napr. EasyOCR) na prečítanie textu z obrazu (napr. "Preset 2").

## Vstup
- Snímka z kamery (s textom presetu).

## Výstup
- Prečítaný text (napr. "Preset 2").

## Postup
1. Orezať oblasť s textom (definovať v konfigurácii).
2. Spustiť OCR.
3. Porovnať s očakávaným textom.

## Definition of Done
- [ ] OCR prečíta text aspoň na 90 % testovacích snímok.
- [ ] Výsledok sa použije na prepnutie trackera.