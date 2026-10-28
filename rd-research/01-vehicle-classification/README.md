# Task 1: Klasifikácia značky a modelu auta (EU)

## Cieľ výskumu
Zistiť, či existujú použiteľné modely na rozpoznávanie **európskych** áut (Škoda, VW, Kia, atď.) a či majú zmysel pre naše kamery. (Pozor: TwinCar a Jordo23 sú trénované na amerických dátach a na našich cestách zlyhávajú).

## Čo treba preskúmať
1.  **Papers a datasety:** Preštudovať papers o Fine-grained Vehicle Classification zameraných na európsky trh. Nájsť európske datasety (napr. DaSCI, VMMRdb alebo akademické datasety z 2026).
2.  **Modely:** Vyskúšať aspoň 2 modely (napr. MobileNet dotrénovaný na európskych dátach alebo hotové modely z Hugging Face).
3.  **Testovanie:** Otestovať na výrezoch z našich kamier (deň/noc, HD/substream). Zistiť, či model zlyháva na zlom uhle alebo rozpixelovanom obraze.

## Podklady 
*   Testovacie výrezy áut z našich kamier sú v **data/crops** prípadne **data/frames** alebo v datasete **RoundaboutHD_ReID_subset**.

## Výstup
1.  **Report:** Aká je presnosť (Top-1, Top-5)? Funguje to na naše kamery? Aké sú problémy?
2.  **Prototyp:** Skript, ktorý na výreze vráti Top-5 značiek a modelov.
3.  **Prezentácia:** Ukázať demo a odporúčať, či to má zmysel nasadiť.

## Definition of Done
- [ ] Preštudované aspoň 2 papers o európskych autách.
- [ ] Vyskúšané aspoň 2 modely.
- [ ] Otestované na našich výrezoch.
- [ ] Napísaný report a odprezentované na stretku.