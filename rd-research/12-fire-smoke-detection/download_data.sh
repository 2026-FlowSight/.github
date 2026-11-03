#!/bin/bash
# Stiahne D-Fire (21 527 obrázkov, YOLO formát, CC0) z HF mirroru a overí SHA256. ~3,1 GB zip, ~6,3 GB pri rozbaľovaní.
# Oficiálny zdroj je OneDrive (https://github.com/gaia-solutions-on-demand/DFireDataset), nedá sa sťahovať skriptom.
set -e
cd "$(dirname "$0")"; mkdir -p data && cd data
curl -fL -C - -o dfire_yolo.zip https://huggingface.co/datasets/Stevebirth/fire-ulm-dfire/resolve/main/dfire_yolo_20261016.zip \
  || { echo "Stiahnutie z HF mirroru zlyhalo. Stiahni D-Fire ručne z OneDrive: https://github.com/gaia-solutions-on-demand/DFireDataset"; exit 1; }
echo "a128a072a0b17dc538c4c6660053fa37a5c29bbf6aef1c3b93885127adf51663  dfire_yolo.zip" | shasum -a 256 -c
unzip -q dfire_yolo.zip && rm dfire_yolo.zip
# zmenšenie na 512 px (rýchlejší tréning na Macu, labely ostávajú rovnaké)
python ../resize_dfire.py dfire_yolo dfire512
sed "s|PATH|$(pwd)/dfire512|" ../dfire.yaml.example > ../dfire512.yaml
echo "hotovo: ../dfire512.yaml"
