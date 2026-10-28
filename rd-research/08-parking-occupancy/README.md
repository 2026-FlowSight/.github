# Task 8: Počítanie obsadenosti parkovísk (Mini-projekt)
**Zadanie:** Preskúmať metódy pre spoľahlivé počítanie áut na parkovisku v reálnom čase (nielen prejazdov, ale trvalo stojacich áut). Nájsť spôsob, ako si udržať stav (koľko áut tam je), aj keď auto na chvíľu zmizne (napr. za stromom alebo ho zakryje iné auto).

**Čo treba spraviť:**
- Preštudovať papers a riešenia z praxe (napr. ako to rieši Frigate NVR, alebo komerčné systémy ako Park Assist).
- Vyskúšať prístup: detekcia áut v definovaných zónach (parkovacie miesta) + logika, ktorá si pamätá, že auto tam bolo aj keď ho YOLO na pár snímok stratí.
- Otestovať na videu ktoré bude v podkladoch.

**Podklady:** Napr. https://www.youtube.com/watch?v=U7HRKjlXK-Y podobné tomu čo budeme mať v praxi alebo si nájdite iné.

**Report:** 
- Aké sú obtiažnosti (tiene, prekrytie, autá na okraji)? 
- Ako zlepšiť model, aby počítal presnejšie? 
- Aká je presnosť (napr. 85 %)? 
- Ako často stačí robiť detekciu?

**Výstup:** Skript, ktorý na videu spočíta autá a vypíše, ako sa počet v čase menil (napr. „O 14:00 tam bolo 12 áut, o 14:30 15 áut“).