"""Stiahne každý N-tý snímok vybraných sekvencií UA-DETRAC (test set) z HF mirroru cez HTTP range
(netreba sťahovať celý 4,2 GB zip). Použitie: python fetch_detrac.py <out_dir> 10 MVI_40742,MVI_40743,..."""
import sys, os, re
from concurrent.futures import ThreadPoolExecutor
from remotezip import RemoteZip

URL = "https://huggingface.co/datasets/abhineet123/ua_detrac/resolve/main/ua_detrac_test_set.zip"
import argparse

_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("out_dir")
_ap.add_argument("step", type=int, help="každá N-tá snímka")
_ap.add_argument("seqs", help="čiarkou oddelené sekvencie, napr. MVI_40742,MVI_40743")
_a = _ap.parse_args()
OUT, STEP, SEQS = _a.out_dir, _a.step, _a.seqs.split(",")

with RemoteZip(URL) as z:
    names = z.namelist()
want = []
for n in names:
    m = re.match(r"detrac_\d+_(MVI_\d+)/img(\d+)\.jpg$", n)
    if m and m.group(1) in SEQS and (int(m.group(2)) - 1) % STEP == 0:
        dst = os.path.join(OUT, m.group(1), f"img{m.group(2)}.jpg")
        if not os.path.exists(dst):
            want.append((n, dst))
print("to fetch:", len(want), flush=True)

def work(chunk):
    with RemoteZip(URL) as z:
        for n, dst in chunk:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data = z.read(n)  # najprv celé stiahnuť, potom atomicky zapísať (žiadne polovičné súbory)
            with open(dst + ".part", "wb") as f:
                f.write(data)
            os.replace(dst + ".part", dst)
    return len(chunk)

chunks = [want[i::12] for i in range(12)]
with ThreadPoolExecutor(12) as ex:
    print("done:", sum(ex.map(work, chunks)))
