# Task 3: Ukladanie a agregácia dát (1TB SSD limit)
**Zadanie:** Ako ukladať 15 dní dát (embeddingy, výskyty, časy) do 1TB SSD bez pretečenia? Ako agregovať dáta?

**Čo treba spraviť:**
- Preštudovať stratégie pre time-series data a vector databases (napr. Qdrant payload indexing).
- Navrhnúť schému: čo ukladať v reálnom čase (len najlepšie embeddingy), čo agregovať (napr. po hodine), čo zahodiť.
- Vypočítať odhad: koľko áut denne, koľko embeddingov, koľko miesta to zaberie.

**Report:** Návrh dátového modelu a retenčnej politiky (napr. mazať staré embeddingy, nechať len časy výskytov).

**Výstup:** Dokument s návrhom + výpočty.