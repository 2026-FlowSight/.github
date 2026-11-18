# DEV12: Interaktívna Mapa (Leaflet)

## Cieľ
Mapa Pezinka s vrstvami **Kamery** (klikateľné) a **Parkoviská** (s aktuálnou obsadenosťou). Vrstvy sa dajú vypnúť/zapnúť, súradnice kamier a parkovísk sa ťahajú z konfiguračných súborov. Vzhľad podľa tímovej AI vizualizácie (`dashboard vizualizacia.png`).

## Vstup
- API (DEV11): `/api/cameras`, `/api/parking`
- Konfiguračné súbory `DEV11-FastAPI-server/config/cameras.yaml`, `config/parking.yaml`
- Hranica mesta z gis.pezinok.sk, mapový podklad Stadia Maps (OpenStreetMap)

## Výstup
- HTML/JS stránka `mapa.html`

## Definition of Done
- [x] Mapa sa načíta.
- [x] Vrstvy sa dajú vypnúť/zapnúť.
- [x] Kamery sú klikateľné.
- [x] Súradnice kamier a parkovísk sú z konfiguračných súborov.

---

## Čo je spravené

![Mapa](screenshots/mapa.png)

Na stránke je iba to, čo zadanie chce: mapa, kamery, parkoviská a prepínanie vrstiev.

**Mapa**
- Pezinok so svetlým podkladom ako vo vizualizácii. Okolie mimo hranice mesta je stlmené.
- **Kamery (41, MsP Pezinok)** – špendlík s ikonou kamery, farba podľa stavu:
  - zelená = online
  - oranžová = podozrivé
  - červená = offline
  - Prerušovaný obrys = poloha je známa len približne.
  - Od priblíženia 15 sa ukazujú čísla kamier. Pri oddialení sa blízke kamery zlúčia do krúžku s počtom; jeho farba je najhorší stav v skupine.
- **Parkoviská (12)** – skutočné plochy z OpenStreetMap, farba podľa obsadenosti (voľné / takmer plné / plné), odznak `P 34/40` ako vo vizualizácii. Keď by sa odznaky susedných parkovísk prekrývali, menšie ukáže iba `P`.
- **Klik na kameru** otvorí kartu: stav, typ, časť mesta, prípadný poplach, tlačidlo **Hľadať vozidlo** (otvorí DEV13 s predvybranou kamerou). Živý prenos príde neskôr.
- **Klik na parkovisko** otvorí kartu: voľné miesta, obsadenosť, kedy bola aktualizovaná a kamery, ktoré parkovisko sledujú (klik ich ukáže).

**Bočný panel**
- **Hľadanie** – číslo kamery, ulica, časť mesta alebo parkovisko, aj bez diakritiky („zamocky“ nájde Zámocký park). Klávesa `/` skočí do hľadania.
- **Vrstvy na mape** – Kamery, Parkoviská, Hranica mesta (prepínače).
- **Záložka Kamery** – filter podľa stavu (online / podozrivé / offline) platí pre zoznam aj mapu; zoznam je zoskupený podľa častí mesta.
- **Záložka Parkoviská** – voľné miesta a obsadenosť, zoradenie podľa voľných miest alebo názvu.
- Zoznam a mapa sú prepojené: prejdenie myšou zvýrazní prvok na mape, klik ho priblíži a otvorí kartu.

**Ďalšie**
- Odkazy priamo na kameru alebo parkovisko: `mapa.html?camera=msp-25`, `?kamera=25`, `?parkovisko=p-7`.
- Obsadenosť sa obnovuje každých 30 s, stav kamier každých 60 s. V pravom hornom rohu je vidno, či sú dáta aktuálne.
- Esc zavrie kartu.
- Funguje aj na mobile (mapa hore, zoznam pod ňou).

### Spustenie
```bash
cd dev-dashboard/DEV11-FastAPI-server
source .venv/bin/activate
uvicorn app.main:app --port 8000
```
a otvoriť http://127.0.0.1:8000/dashboard/DEV12-interactive-map/mapa.html

Bez API (`python -m http.server 8000` v priečinku `dev-dashboard`) mapa načíta kamery a parkoviská priamo z YAML súborov, ale bez stavu kamier a obsadenosti. Ak beží API na inej adrese, použi `mapa.html?api=http://…`.

### Odkiaľ sú dáta
| Čo | Zdroj |
|---|---|
| polohy kamier | `config/cameras.yaml` – zoznam MsP Pezinok 2024, polohy dohľadané v OpenStreetMap a overené (kamera 3 opravená na stĺp mestských hodín) |
| parkoviská | `config/parking.yaml` – 12 plôch `amenity=parking` z OpenStreetMap (OSM ich v Pezinku nemá pomenované, preto sú pomenované podľa ulice alebo obchodu). Kapacita je z OSM, z tlačovej správy k P+R (291 miest) alebo odhad z plochy. |
| stav kamier, obsadenosť | API (DEV11) – zatiaľ ukážkové hodnoty, kým nebude napojenie na Milestone a DEV03 |
| hranica mesta | gis.pezinok.sk (`data/pezinok-layers.js`) |

Mapový podklad je Stadia Maps „Alidade Smooth“, ktorý na localhoste funguje bez kľúča. Pri nasadení na verejnú doménu treba bezplatný účet Stadia Maps; ak podklad nejde, mapa sa sama prepne na OSM HOT.

### Čo ešte chýba
- živý prenos z kamery (podľa zadania neskôr)
- skutočná obsadenosť parkovísk (DEV03) a stav kamier (Milestone)
- kapacity parkovísk overiť v teréne – pri väčšine je to odhad

## Súbory
- `mapa.html`, `map.css`, `map.js` – stránka, vzhľad, logika mapy
- `api.js` – načítanie z API, záložne z YAML konfigurácie
- `data/pezinok-layers.js` – hranica mesta (gis.pezinok.sk)

Vyhľadávanie vozidiel je v [DEV13](../DEV13-db-search-frontend/), API v [DEV11](../DEV11-FastAPI-server/).
