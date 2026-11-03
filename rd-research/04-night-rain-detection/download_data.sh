#!/bin/bash
# Stiahne testovacie dáta pre úlohu 04 do ./data (mimo gitu). Spolu ~450 MB.
set -e
cd "$(dirname "$0")"; mkdir -p data && cd data
# 1) UA-DETRAC: anotácie test setu (XML, 12 MB, kópia na GitHube) + každý 10. snímok z 29 sekvencií (~280 MB)
curl -sSL -o detrac_xml.zip https://raw.githubusercontent.com/yuktha2165/object-tracking-using-kalman-filter-/main/backend/data/dataset/DETRAC-Test-Annotations-XML.zip
unzip -q -o detrac_xml.zip
SEQS=MVI_40742,MVI_40743,MVI_40761,MVI_40762,MVI_40763,MVI_40771,MVI_40772,MVI_40773,MVI_40774,MVI_40775,MVI_40792,MVI_40793,MVI_40863,MVI_40864,MVI_40891,MVI_40892,MVI_40901,MVI_40902,MVI_40903,MVI_40904,MVI_40905,MVI_40701,MVI_40711,MVI_40851,MVI_40852,MVI_39031,MVI_39211,MVI_39311,MVI_39371
python ../fetch_detrac.py uadetrac_frames 10 $SEQS
# 2) DAWN Rain (200 obrázkov, CC BY-NC 3.0, 30 MB)
curl -sSL -o Rain.zip "https://data.mendeley.com/public-files/datasets/766ygrbt8y/files/7b37087a-db6b-4ce9-8ec4-ee64f963f073/file_downloaded"
unzip -q -o Rain.zip && mkdir -p dawn && ln -sfn ../Rain dawn/images && ln -sfn ../Rain/Rain_YOLO_darknet dawn/labels
# 3) ExDark test (735 obrázkov, YOLO formát, len na výskum, 28 MB)
hf download dronefreak/ExDark --repo-type dataset --include "data/test/**" --local-dir exdark
echo "hotovo"
