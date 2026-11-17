// Mestský kamerový systém Pezinok – spoločný zoznam pre mapu aj vyhľadávanie.
//
// Zdroj: Mestská polícia Pezinok, „Mestský kamerový systém Pezinok 2024“
//   https://www.pezinok.sk/stranka/kamerovy-system
//   (PDF: /content/files/msp/MESTSKY_KAMEROVY_SYSTEM_PEZINOK_2024_7_3.pdf)
// Dokument uvádza 52 kamier, opisuje 48 (v centre hlavička hovorí o 18, opísaných je 14).
// Tu je 41 vonkajších: kamery 1–38 a 3 vonkajšie pri nájomných bytoch na Zumberskej.
// Vynechané: 7 kamier vo vnútri bytového domu na Zumberskej.
//
// Súradnice v dokumente NIE SÚ. Sú dopočítané z OpenStreetMap podľa opisu umiestnenia:
//   precision = 'križovatka' (stred križovatky dvoch ulíc), 'adresa', 'budova',
//   alebo 'približne' (ulica / areál bez presného bodu). Presnosť rádovo desiatky metrov.
// Kamery na rovnakom mieste sú rozostúpené o ~9 m, aby sa značky neprekrývali.
// type: 'otočná' (PTZ) alebo 'statická'.
// mount: na čom je kamera podľa dokumentu – 'stĺp' (verejné osvetlenie, samostatný, telekomunikačný), 'budova', 'neuvedené'.
// site: čo sleduje – 'ulica' (verejný priestor: ulice, križovatky, námestie, stanica) alebo 'areál' (škola, ihrisko, zberný dvor, bytový dom).
window.FLOWSIGHT_CAMERAS = [
  {"id": "msp-1", "no": "1", "name": "Kamera 1 – Holubyho", "area": "Centrum", "street": "Križovatka Holubyho / Radničné námestie", "type": "otočná", "precision": "križovatka", "lat": 48.286124, "lng": 17.26907, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-2", "no": "2", "name": "Kamera 2 – Radničné námestie", "area": "Centrum", "street": "Budova mestského úradu", "type": "otočná", "precision": "budova", "lat": 48.28584, "lng": 17.27005, "mount": "budova", "site": "ulica"},
  {"id": "msp-3", "no": "3", "name": "Kamera 3 – Kollárova", "area": "Centrum", "street": "Stĺp mestských hodín, Kollárova", "type": "otočná", "precision": "približne", "lat": 48.286245, "lng": 17.270947, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-4", "no": "4", "name": "Kamera 4 – Fortna", "area": "Centrum", "street": "Samostatný stĺp, Holubyho", "type": "otočná", "precision": "križovatka", "lat": 48.28792, "lng": 17.267286, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-5", "no": "5", "name": "Kamera 5 – Mladoboleslavská", "area": "Centrum", "street": "Kruhový objazd Holubyho / Mladoboleslavská", "type": "otočná", "precision": "križovatka", "lat": 48.289127, "lng": 17.266633, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-6", "no": "6", "name": "Kamera 6 – Zámocký park", "area": "Centrum", "street": "Vchod do Zámockého parku, Mladoboleslavská / M. R. Štefánika", "type": "otočná", "precision": "križovatka", "lat": 48.289917, "lng": 17.268525, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-7", "no": "7", "name": "Kamera 7 – Panoráma", "area": "Centrum", "street": "Križovatka Moyzesova / Kollárova", "type": "otočná", "precision": "križovatka", "lat": 48.284892, "lng": 17.271806, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-8", "no": "8", "name": "Kamera 8 – Terminál Tabak", "area": "Centrum", "street": "Vchod na železničnú stanicu, Holubyho", "type": "otočná", "precision": "približne", "lat": 48.283121, "lng": 17.270412, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-9", "no": "9", "name": "Kamera 9 – Terminál aut. zastávka", "area": "Centrum", "street": "Železničná stanica, Holubyho", "type": "otočná", "precision": "približne", "lat": 48.28254, "lng": 17.27038, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-10", "no": "10", "name": "Kamera 10 – Terminál bicykle", "area": "Centrum", "street": "Železničná stanica, Holubyho", "type": "statická", "precision": "približne", "lat": 48.28238, "lng": 17.27038, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-11", "no": "11", "name": "Kamera 11 – Moyzesova", "area": "Centrum", "street": "Križovatka Moyzesova / Kollárova", "type": "otočná", "precision": "križovatka", "lat": 48.284732, "lng": 17.271806, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-12", "no": "12", "name": "Kamera 12 – Katová ulička", "area": "Centrum", "street": "Ulička Fortna", "type": "statická", "precision": "približne", "lat": 48.287901, "lng": 17.267219, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-33", "no": "33", "name": "Kamera 33 – MsÚ", "area": "Centrum", "street": "Budova MsÚ Pezinok", "type": "otočná", "precision": "budova", "lat": 48.28568, "lng": 17.27005, "mount": "budova", "site": "ulica"},
  {"id": "msp-38", "no": "38", "name": "Kamera 38 – Trhovisko", "area": "Centrum", "street": "Pri trhovisku", "type": "otočná", "precision": "budova", "lat": 48.29177, "lng": 17.26393, "mount": "neuvedené", "site": "ulica"},
  {"id": "msp-13", "no": "13", "name": "Kamera 13 – Na bielenisku", "area": "Sever", "street": "Samostatný stĺp na Bielenisku pri SBD", "type": "otočná", "precision": "približne", "lat": 48.295016, "lng": 17.265955, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-14", "no": "14", "name": "Kamera 14 – Svätoplukova", "area": "Sever", "street": "Výmenníková stanica, Svätoplukova 6", "type": "otočná", "precision": "adresa", "lat": 48.2972, "lng": 17.26579, "mount": "budova", "site": "ulica"},
  {"id": "msp-15", "no": "15", "name": "Kamera 15 – Pekáreň", "area": "Sever", "street": "Výmenníková stanica, Svätoplukova 6", "type": "statická", "precision": "adresa", "lat": 48.29704, "lng": 17.26579, "mount": "budova", "site": "ulica"},
  {"id": "msp-16", "no": "16", "name": "Kamera 16 – Terezka pub", "area": "Sever", "street": "Stĺp verejného osvetlenia, Svätoplukova 11", "type": "otočná", "precision": "adresa", "lat": 48.29716, "lng": 17.26495, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-17", "no": "17", "name": "Kamera 17 – Otočisko bus", "area": "Sever", "street": "Výmenníková stanica, Svätoplukova", "type": "otočná", "precision": "približne", "lat": 48.299796, "lng": 17.266365, "mount": "budova", "site": "ulica"},
  {"id": "msp-18", "no": "18", "name": "Kamera 18 – Novomeského CBA", "area": "Sever", "street": "Výmenníková stanica, Svätoplukova", "type": "otočná", "precision": "približne", "lat": 48.299964, "lng": 17.266463, "mount": "budova", "site": "ulica"},
  {"id": "msp-19", "no": "19", "name": "Kamera 19 – Suvorovova", "area": "Sever", "street": "Výmenníková stanica, Svätoplukova", "type": "otočná", "precision": "približne", "lat": 48.296229, "lng": 17.264105, "mount": "budova", "site": "ulica"},
  {"id": "msp-20", "no": "20", "name": "Kamera 20 – Gen. Pekníka", "area": "Muškát", "street": "Stĺp verejného osvetlenia, Gen. Pekníka", "type": "statická", "precision": "približne", "lat": 48.295007, "lng": 17.272419, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-21", "no": "21", "name": "Kamera 21 – Trnavská Tabak", "area": "Muškát", "street": "Križovatka Trnavská / Gen. Pekníka", "type": "otočná", "precision": "križovatka", "lat": 48.294535, "lng": 17.274322, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-22", "no": "22", "name": "Kamera 22 – Trnavská aut. zastávka", "area": "Muškát", "street": "Križovatka Trnavská / Hroznová", "type": "otočná", "precision": "križovatka", "lat": 48.295617, "lng": 17.275326, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-23", "no": "23", "name": "Kamera 23 – Silvánová", "area": "Muškát", "street": "Križovatka Silvánová / Muškátová", "type": "otočná", "precision": "križovatka", "lat": 48.294693, "lng": 17.276859, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-24", "no": "24", "name": "Kamera 24 – Hrnčiarska", "area": "Juh", "street": "Križovatka Hrnčiarska / Fortna", "type": "otočná", "precision": "križovatka", "lat": 48.287512, "lng": 17.266235, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-25", "no": "25", "name": "Kamera 25 – Za hradbami", "area": "Juh", "street": "Parkovisko Hrnčiarska / Za hradbami", "type": "statická", "precision": "križovatka", "lat": 48.28727, "lng": 17.266359, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-26", "no": "26", "name": "Kamera 26 – ZŠ Fándlyho", "area": "Juh", "street": "Budova telocvične ZŠ Fándlyho", "type": "statická", "precision": "budova", "lat": 48.28426, "lng": 17.25991, "mount": "budova", "site": "areál"},
  {"id": "msp-34", "no": "34", "name": "Kamera 34 – Komenského", "area": "Juh", "street": "Stĺp verejného osvetlenia, Komenského", "type": "otočná", "precision": "približne", "lat": 48.284374, "lng": 17.256929, "mount": "stĺp", "site": "ulica"},
  {"id": "msp-35", "no": "35", "name": "Kamera 35 – Plaváreň", "area": "Juh", "street": "Budova plavárne", "type": "statická", "precision": "budova", "lat": 48.28406, "lng": 17.256, "mount": "budova", "site": "ulica"},
  {"id": "msp-27", "no": "27", "name": "Kamera 27 – Glejovka", "area": "Grinava", "street": "Areál futbalového ihriska Grinava, Myslenická", "type": "otočná", "precision": "približne", "lat": 48.27455, "lng": 17.25555, "mount": "stĺp", "site": "areál"},
  {"id": "msp-28", "no": "28", "name": "Kamera 28 – Regena", "area": "Grinava", "street": "Areál Regena v Glejovke, Myslenická", "type": "otočná", "precision": "približne", "lat": 48.273717, "lng": 17.260032, "mount": "stĺp", "site": "areál"},
  {"id": "msp-29", "no": "29", "name": "Kamera 29 – Karanténna", "area": "Karanténna a odchytová stanica", "street": "Zberný dvor, Fajgalská cesta", "type": "statická", "precision": "približne", "lat": 48.29, "lng": 17.24935, "mount": "budova", "site": "areál"},
  {"id": "msp-30", "no": "30", "name": "Kamera 30 – Zberný dvor", "area": "Karanténna a odchytová stanica", "street": "Zberný dvor, Fajgalská cesta", "type": "statická", "precision": "približne", "lat": 48.28984, "lng": 17.24935, "mount": "budova", "site": "areál"},
  {"id": "msp-31", "no": "31", "name": "Kamera 31 – Kupeckého 1", "area": "ZŠ Kupeckého", "street": "Telocvičňa ZŠ Jána Kupeckého", "type": "statická", "precision": "budova", "lat": 48.29449, "lng": 17.26371, "mount": "budova", "site": "areál"},
  {"id": "msp-32", "no": "32", "name": "Kamera 32 – Kupeckého 2", "area": "ZŠ Kupeckého", "street": "Telocvičňa ZŠ Jána Kupeckého", "type": "statická", "precision": "budova", "lat": 48.29433, "lng": 17.26371, "mount": "budova", "site": "areál"},
  {"id": "msp-36", "no": "36", "name": "Kamera 36 – Gorkého", "area": "Starý Dvor", "street": "Bytový dom, Gorkého 12", "type": "otočná", "precision": "adresa", "lat": 48.28843, "lng": 17.25484, "mount": "budova", "site": "ulica"},
  {"id": "msp-37", "no": "37", "name": "Kamera 37 – Puškinova", "area": "Starý Dvor", "street": "Bytový dom, Gorkého 12", "type": "statická", "precision": "adresa", "lat": 48.28827, "lng": 17.25484, "mount": "budova", "site": "ulica"},
  {"id": "msp-z2", "no": "Z2", "name": "Zumberská – vchod", "area": "Nájomné byty Zumberská", "street": "Stĺp verejného osvetlenia, Zumberská", "type": "statická", "precision": "približne", "lat": 48.31494, "lng": 17.25698, "mount": "stĺp", "site": "areál"},
  {"id": "msp-z3", "no": "Z3", "name": "Zumberská – parkovisko", "area": "Nájomné byty Zumberská", "street": "Stĺp verejného osvetlenia, Zumberská", "type": "statická", "precision": "približne", "lat": 48.31482, "lng": 17.257084, "mount": "stĺp", "site": "areál"},
  {"id": "msp-z4", "no": "Z4", "name": "Zumberská – dvor", "area": "Nájomné byty Zumberská", "street": "Telekomunikačný stĺp, Zumberská", "type": "statická", "precision": "približne", "lat": 48.31482, "lng": 17.256876, "mount": "stĺp", "site": "areál"}
];
