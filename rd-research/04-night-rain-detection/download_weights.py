"""Stiahne malé predtrénované váhy zosvetľovačov z oficiálnych GitHub repozitárov autorov (~100 kB).
Váhy nie sú v gite (licencie: SCI = MIT, Zero-DCE++ = CC BY-NC 4.0, len na výskum)."""
import os
import sys
import urllib.request

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0)

URLS = {
    "sci_medium.pt": "https://raw.githubusercontent.com/vis-opt-group/SCI/main/CVPR/weights/medium.pt",
    "zerodcepp_Epoch99.pth": "https://raw.githubusercontent.com/Li-Chongyi/Zero-DCE_extension/main/"
                             "Zero-DCE%2B%2B/snapshots_Zero_DCE%2B%2B/Epoch99.pth",
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")
os.makedirs(out, exist_ok=True)
for name, url in URLS.items():
    dst = os.path.join(out, name)
    if not os.path.exists(dst):
        print("sťahujem", name)
        urllib.request.urlretrieve(url, dst)
print("hotovo:", sorted(os.listdir(out)))
