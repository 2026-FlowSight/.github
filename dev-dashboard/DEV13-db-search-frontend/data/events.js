// Ukážkové udalosti pre modul Udalosti. NIČ Z TOHO SA NESTALO.
// Zábery vozidiel sú z projektového datasetu (RoundaboutHD, nie Pezinok), kamery a časy sú vymyslené.
// Zábery ohňa (assets/events) sú výrezy z výstupu prototypu R&D 12 (detekcia ohňa a dymu, Peter Štefanec):
// rd-research/12-fire-smoke-detection/results/figures/video_demo.jpg. Zdroj videa je v poli `credit`.
//
// Polia: id, type, severity ('kritická' | 'varovanie' | 'info'), status ('nová' | 'rieši sa' | 'vyriešená'),
// minutesAgo (čas vzniku voči načítaniu stránky), camera (id z data/cameras.js), image, box ([x, y, w, h] v % záberu),
// label (čo model videl), confidence (0–1), text, history ([{ minutesAgo, text }]).
(function () {
  const R = 'assets/records/';
  window.FLOWSIGHT_EVENTS = [
    {
      id: 'ev-1041', type: 'Požiar vozidla', severity: 'kritická', status: 'nová', minutesAgo: 3,
      camera: 'msp-25', image: 'assets/events/fire-car.jpg', label: 'dym', confidence: 0.71,
      credit: 'Výstup prototypu R&D 12 · video: Car Fire Perth Amboy FD, Wikimedia Commons, CC BY 3.0',
      text: 'Na parkovisku Za hradbami model zachytil hustý dym pri zaparkovanom vozidle. Poplach je potvrdený: dym vydržal v zábere viac ako polovicu z posledných 3 sekúnd a hýbe sa, takže nejde o statický obrázok.',
      history: [
        { minutesAgo: 3, text: 'Prvá detekcia dymu' },
        { minutesAgo: 3, text: 'Potvrdený poplach: dym, perzistencia a pohyb splnené' },
      ],
    },
    {
      id: 'ev-1040', type: 'Jazda v protismere', severity: 'kritická', status: 'nová', minutesAgo: 9,
      camera: 'msp-5', image: `${R}5b220606-965a-4505-9112-9b043a772a68.jpg`, box: [18, 12, 78, 73], label: 'osobné auto', confidence: 0.93,
      text: 'Strieborné SUV vošlo na kruhový objazd Holubyho / Mladoboleslavská proti smeru jazdy. Trajektória z 12 snímok.',
      history: [{ minutesAgo: 9, text: 'Smer jazdy opačný ako povolený, 12 snímok' }],
      vehicle: true,
    },
    {
      id: 'ev-1039', type: 'Hľadané vozidlo', severity: 'varovanie', status: 'nová', minutesAgo: 17,
      camera: 'msp-21', image: `${R}7cd82cd2-6b4c-47a3-a043-89939be894b9.jpg`, box: [15, 18, 70, 62], label: 'dodávka', confidence: 0.91,
      text: 'Biela dodávka s rebríkmi sa podobá vozidlu, ktoré operátor hľadal ráno (skóre podobnosti 0,91). Treba overiť porovnaním záberov.',
      history: [{ minutesAgo: 17, text: 'Zhoda s uloženým hľadaním „Biela dodávka s rebríkmi“' }],
      vehicle: true,
    },
    {
      id: 'ev-1038', type: 'Nákladné vozidlo v centre', severity: 'varovanie', status: 'nová', minutesAgo: 34,
      camera: 'msp-1', image: `${R}c35e9162-0575-47be-8b8c-16a092f0b8b2.jpg`, box: [14, 18, 72, 60], label: 'nákladné auto', confidence: 0.95,
      text: 'Sklápač prešiel križovatkou Holubyho / Radničné námestie mimo času povoleného zásobovania (6:00–10:00).',
      history: [{ minutesAgo: 34, text: 'Nákladné vozidlo nad 3,5 t v zóne s obmedzením' }],
      vehicle: true,
    },
    {
      id: 'ev-1037', type: 'Vozidlo na priechode', severity: 'varovanie', status: 'rieši sa', minutesAgo: 52,
      camera: 'msp-11', image: `${R}7c3822c1-0d68-4ef1-b752-9e2b2f849938.jpg`, box: [20, 13, 68, 67], label: 'osobné auto', confidence: 0.9,
      text: 'Biele SUV stojí na priechode pre chodcov na križovatke Moyzesova / Kollárova dlhšie ako 4 minúty.',
      history: [
        { minutesAgo: 52, text: 'Vozidlo stojí na priechode 4 min' },
        { minutesAgo: 47, text: 'Prevzal operátor, hliadka na ceste' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1036', type: 'Dlhé státie', severity: 'info', status: 'rieši sa', minutesAgo: 75,
      camera: 'msp-38', image: `${R}1b916e01-9f85-489c-93ff-041bdfc74649.jpg`, box: [18, 15, 68, 67], label: 'dodávka', confidence: 0.86,
      text: 'Biela dodávka stojí pri trhovisku 3 h 40 min na mieste s limitom 2 hodiny.',
      history: [
        { minutesAgo: 75, text: 'Prekročený limit státia o 1 h 40 min' },
        { minutesAgo: 60, text: 'Prevzal operátor' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1035', type: 'Kamera bez obrazu', severity: 'info', status: 'nová', minutesAgo: 96,
      camera: 'msp-17', image: null,
      text: 'Kamera 17 neposlala obraz 12 minút. Spracovanie pre ňu je pozastavené, kým sa signál neobnoví.',
      history: [{ minutesAgo: 96, text: 'Výpadok signálu z Milestone' }],
    },
    {
      id: 'ev-1034', type: 'Požiar budovy', severity: 'kritická', status: 'vyriešená', minutesAgo: 60 * 5 + 20,
      camera: 'msp-36', image: 'assets/events/fire-building.jpg', label: 'oheň', confidence: 0.63,
      credit: 'Výstup prototypu R&D 12 · video: Pexels 4116863, Pexels License',
      text: 'Oheň a dym na streche bytového domu na Gorkého ulici. Poplach prišiel 2 sekundy po prvej detekcii. Na mieste zasahovali hasiči.',
      history: [
        { minutesAgo: 60 * 5 + 20, text: 'Potvrdený poplach: oheň a dym' },
        { minutesAgo: 60 * 5 + 17, text: 'Prevzal operátor, privolaný HaZZ' },
        { minutesAgo: 60 * 4 + 30, text: 'Vyriešené: požiar uhasený' },
      ],
    },
    {
      id: 'ev-1033b', type: 'Zamietnutý poplach: oheň', severity: 'info', status: 'vyriešená', minutesAgo: 60 * 6 + 10,
      camera: 'msp-5', image: 'assets/events/fire-poster.jpg', label: 'oheň', confidence: 0.82,
      credit: 'Syntetický test R&D 12 · RoundaboutHD + vložená fotka ohňa',
      text: 'Model videl oheň na každej snímke, no obsah boxu sa nehýbal. Filter preto poplach nespustil a operátora nerušil. Takto sa odfiltrujú plagáty, billboardy a obrazovky.',
      history: [
        { minutesAgo: 60 * 6 + 10, text: 'Detekcia ohňa bez pohybu 60 s' },
        { minutesAgo: 60 * 6 + 9, text: 'Automaticky zamietnuté: statický obrázok' },
      ],
    },
    {
      id: 'ev-1033', type: 'Nákladné vozidlo v centre', severity: 'varovanie', status: 'vyriešená', minutesAgo: 60 * 7,
      camera: 'msp-8', image: `${R}f0368b01-a2dc-47e0-bbd9-95e7df7a530b.jpg`, box: [8, 15, 72, 83], label: 'nákladné auto', confidence: 0.97,
      text: 'Skriňové nákladné auto pri vchode na železničnú stanicu mimo času zásobovania.',
      history: [
        { minutesAgo: 60 * 7, text: 'Nákladné vozidlo nad 3,5 t v zóne s obmedzením' },
        { minutesAgo: 60 * 7 - 10, text: 'Vyriešené: zásobovanie s povolením' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1032', type: 'Jazda v protismere', severity: 'kritická', status: 'vyriešená', minutesAgo: 60 * 9 + 5,
      camera: 'msp-24', image: `${R}d6cf536e-f592-4060-baf4-055b19d17a3c.jpg`, box: [10, 15, 85, 75], label: 'osobné auto', confidence: 0.74,
      text: 'Model vyhodnotil pohyb proti smeru jazdy na križovatke Hrnčiarska / Fortna.',
      history: [
        { minutesAgo: 60 * 9 + 5, text: 'Smer jazdy opačný ako povolený, 5 snímok' },
        { minutesAgo: 60 * 9, text: 'Vyriešené: planý poplach, vozidlo cúvalo z parkovacieho miesta' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1031', type: 'Vozidlo na chodníku', severity: 'varovanie', status: 'vyriešená', minutesAgo: 60 * 26,
      camera: 'msp-3', image: `${R}a5cc9185-2da8-4bbb-94b4-658594554902.jpg`, box: [15, 12, 75, 80], label: 'nákladné auto', confidence: 0.89,
      text: 'Servisné vozidlo s plošinou stojí na chodníku pri mestských hodinách na Kollárovej.',
      history: [
        { minutesAgo: 60 * 26, text: 'Vozidlo stojí mimo vozovky 6 min' },
        { minutesAgo: 60 * 26 - 4, text: 'Vyriešené: údržba verejného osvetlenia, ohlásená' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1030', type: 'Hľadané vozidlo', severity: 'varovanie', status: 'vyriešená', minutesAgo: 60 * 29,
      camera: 'msp-22', image: `${R}58fa6645-e014-4956-b873-e17e6793627a.jpg`, box: [15, 15, 60, 60], label: 'osobné auto', confidence: 0.72,
      text: 'Biely sedan sa podobal hľadanému vozidlu (skóre podobnosti 0,72).',
      history: [
        { minutesAgo: 60 * 29, text: 'Zhoda s uloženým hľadaním „Biely sedan“' },
        { minutesAgo: 60 * 29 - 15, text: 'Vyriešené: po porovnaní záberov iné vozidlo' },
      ],
      vehicle: true,
    },
    {
      id: 'ev-1029', type: 'Dlhé státie', severity: 'info', status: 'vyriešená', minutesAgo: 60 * 31,
      camera: 'msp-z3', image: `${R}9f9c3ce1-28f0-4e09-aa44-ce078969fe18.jpg`, box: [12, 18, 63, 74], label: 'osobné auto', confidence: 0.84,
      text: 'Čierne SUV na parkovisku pri nájomných bytoch Zumberská stojí 26 hodín.',
      history: [
        { minutesAgo: 60 * 31, text: 'Vozidlo stojí na rovnakom mieste 24 h' },
        { minutesAgo: 60 * 30, text: 'Vyriešené: vozidlo nájomcu, bez porušenia' },
      ],
      vehicle: true,
    },
  ];
})();
