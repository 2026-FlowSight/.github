# DEV16: Vyhľadávací Dashboard (Frontend)

## Cieľ
Rozhranie (inšpirácia z AI vizualizácie, ale doplniť funkcie), kde používateľ nahrá obrázok auta (alebo vyberie z galérie) a systém mu vráti zoznam zhôd z Qdrant. Zobrazenie Top-3 výsledkov s časom a kamerou.

## Vstup
- API z DEV14.
- Obrázok od používateľa.

## Výstup
- Webová stránka s výsledkami.

## Postup
1. Vytvoriť HTML formulár na nahratie obrázka.
2. Poslať na API.
3. Zobraziť výsledky (obrázky, čas, kamera).

## Definition of Done
- [x] Nahrávanie obrázka funguje.
- [x] Výsledky sa zobrazia do 2 sekúnd. (cez API z DEV11 a lokálny Qdrant približne 0,2 s aj s načítaním záberov)

---

## Čo je spravené

![Vyhľadávanie](screenshots/vyhladavanie.png)

Frontend je čisté HTML, CSS a JS, nič sa nebuildí.

### Spustenie spolu s backendom

Frontend a backend sú prepojené, celý dashboard beží z jednej adresy cez API z [DEV11](../DEV11-FastAPI-server/):

```
cd dev-dashboard/DEV11-FastAPI-server
pip install -r requirements.txt
python scripts/seed_qdrant.py
uvicorn app.main:app --port 8000
```

Potom stačí otvoriť http://127.0.0.1:8000/. Otvorí sa mapa a cez menu sa dá prejsť na udalosti a vyhľadávanie. Keď stránku servíruje API, vyhľadávanie si jeho adresu nájde samo, netreba nič zadávať:

- kamery vo filtri sú z `GET /api/cameras`, teda rovnaký zoznam ako na mape
- galéria ukazuje posledné prejazdy z Qdrantu (`GET /api/vehicles/recent`)
- fotka ide na `POST /api/search` a výsledky sú z Qdrantu
- „Hľadať vozidlo“ na mape otvorí vyhľadávanie s predvybranou kamerou

Vpravo hore je vidieť, či API odpovedá. Keď nebeží, stránka ostane použiteľná na ukážkových dátach. Adresa API sa pamätá spolu s mapou (rovnaký kľúč v prehliadači).

### Bez backendu

Stačí otvoriť `index.html` alebo spustiť `python -m http.server 8000` z priečinka `dev-dashboard`. Bez API beží stránka na ukážkových dátach. Ukážkové dáta sa dajú vynútiť aj cez API, ak sa do URL pridá `?api=` s prázdnou hodnotou.

- nahratie fotky (presunutím alebo kliknutím), JPG/PNG/WebP do 10 MB, zlý súbor sa odmietne a pôvodná fotka zostane
- alebo výber z galérie posledných detekcií
- filter podľa času a kamier (kamery sú zoradené podľa častí mesta)
- top 3 výsledky s časom, kamerou a skóre podobnosti
- porovnanie hľadaného auta so záberom vedľa seba
- keď sa zmenia filtre, starý výsledok sa označí, aby ho nikto nebral ako aktuálny
- chybové stavy: server nebeží, timeout (15 s), zlá odpoveď, zábery sa nenačítali

Na ukážkových dátach sú zábery z RoundaboutHD, kamery a časy sú vymyslené. Adresa iného API sa dá zadať dole v sekcii „Pre vývojárov“ alebo cez `?api=http://127.0.0.1:8000` v URL.

### Udalosti

![Udalosti](screenshots/udalosti.png)

Navyše je tu stránka `udalosti.html`, zatiaľ iba s ukážkovými udalosťami (požiar, jazda v protismere, dlhé státie...). Zábery ohňa sú z prototypu R&D 12. Je to návrh, ako by mohli vyzerať alerty v dashboarde, keď bude detekcia napojená.

## API (DEV11)

Request: `POST /api/search`, multipart

| pole | čo to je |
|---|---|
| `image` | fotka auta |
| `top_k` | koľko výsledkov (posielam 3) |
| `camera` | id kamery, môže byť viackrát; keď chýba, hľadá sa všade |
| `from` | ISO čas, od kedy hľadať; keď chýba, kedykoľvek |

Response:

```json
{
  "results": [
    {
      "score": 0.91,
      "payload": {
        "original_id": "aaa",
        "frame_path": "frames/aaa_best.jpg",
        "timestamp": "2026-11-17T08:15:00",
        "camera": "msp-21"
      }
    }
  ]
}
```

Prispôsobil som to Jánovej pipeline (`rd-research/02-multi-view-reid`), takže stačí poslať body z Qdrantu tak, ako sú. Ak príde to isté auto viackrát (spredu, zboku...), ukáže sa iba jeho najlepší pohľad. Obrázok berie z `image_url`, `frame_path`, `best_frame_path` alebo `reid_crop_path`. Relatívne cesty sa skladajú s adresou API, takže backend musí tie súbory servírovať.

Čo ešte treba vyriešiť:
- prevod fotky na vektor je na serveri zatiaľ dočasný (farebný histogram), skutočný ReID model príde v DEV16. Stránka to pri výsledkoch napíše.
- pipeline (`rd-research/02`) ukladá čas iba ako `HH:MM:SS` a kameru `demo_cam`. Ukážková databáza z `seed_qdrant.py` už má ISO čas aj id kamier, pipeline to ešte treba upraviť.
- udalosti sú stále iba ukážkové (`data/events.js`), backend pre ne zatiaľ nemá endpoint, lebo chýba detekcia

## Súbory

- `index.html`, `app.js` – vyhľadávanie
- `udalosti.html`, `events.js`, `events.css` – udalosti
- `styles.css` – spoločný vzhľad (rovnaký súbor je aj v DEV12)
- `data/cameras.js` – zoznam 41 mestských kamier (podľa MsP Pezinok)
- `data/events.js` – ukážkové udalosti
- `assets/` – ukážkové zábery

Mapa je v [DEV12](../DEV12-interactive-map/), stránky sú medzi sebou prelinkované.
