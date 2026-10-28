# Funkčné demo zo stretnutia #2

Skript **detection_reid** spustí detekciu na zvolené video, trackuje bboxy, zobrazí trail, robí reid a ukladá do Qdrant, výsledné video aj uloží ako **output_reid_demo.mp4**.
Spustí aj live video spomalené na stride=2, ak má originál 15fps, tak stride=2 berie každé druhé fps -> 7.5fps.
Dokáže na základe určených kritérií aktualizovať záber ak je väčší, pre krajší obrázok a ignoruje divné bboxy, ale treba doladiť ešte.
Po stlačení 'q' sa ukončí video a uloží sa, vygeneruje sa aj mock .html s obrázkami.

Používa ByteTrack z knižnice **ultralytics** so zmenenými parametrami.

Skript **generate_html** generuje mock html s nájdenými obrázkami.