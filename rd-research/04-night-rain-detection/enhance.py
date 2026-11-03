"""Predspracovanie snímok pre YOLO v noci a v daždi.

Každá metóda je funkcia  bgr_uint8 -> bgr_uint8  (rovnaký tvar ako vstup),
takže sa dá vložiť pred `yolo.predict(frame)` bez ďalších zmien.

Použitie:
    from enhance import get_method, METHODS
    f = get_method("clahe")
    out = f(frame)

Naučené siete (SCI, Zero-DCE++) potrebujú váhy v priečinku `weights/`
(stiahne ich `python download_weights.py`, spolu ~150 kB).
"""
from __future__ import annotations

import os
from functools import lru_cache

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(HERE, "weights")


# ---------------------------------------------------------------------------
# 1. Klasické pixelové operácie (bez GPU)
# ---------------------------------------------------------------------------
def none(img):
    return img


@lru_cache(maxsize=32)
def _gamma_lut(gamma: float):
    x = np.arange(256, dtype=np.float32) / 255.0
    return np.clip((x ** gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def gamma(img, g: float = 0.6):
    """Pevná gama korekcia cez LUT (g<1 zosvetlí tmavé tóny). ~0.3 ms pre 960x540."""
    return cv2.LUT(img, _gamma_lut(g))


def gamma_auto(img, target: float = 0.45):
    """Adaptívna gama: zvolí g tak, aby priemerný jas (0..1) bol ~target.
    Svetlé (denné) snímky nechá skoro bez zmeny, tmavé zosvetlí viac."""
    mean = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean()) / 255.0
    mean = min(max(mean, 1e-3), 0.999)
    g = np.log(target) / np.log(mean)
    g = float(np.clip(g, 0.3, 1.0))  # nikdy nestmavuj, nezosvetľuj extrémne
    return gamma(img, round(g, 2))


def he(img):
    """Globálna ekvalizácia histogramu na jasovom kanáli (Y)."""
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    ycc[..., 0] = cv2.equalizeHist(ycc[..., 0])
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)


@lru_cache(maxsize=4)
def _clahe(clip: float, tile: int):
    return cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))


def clahe(img, clip: float = 2.0, tile: int = 8):
    """CLAHE (lokálna ekvalizácia s obmedzením kontrastu) na L kanáli v LAB."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = _clahe(clip, tile).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def gamma_clahe(img):
    """Kombinácia: adaptívna gama + CLAHE."""
    return clahe(gamma_auto(img))


def msr(img, sigmas=(15, 80, 250), down: int = 4):
    """Multi-Scale Retinex. Osvetlenie sa odhaduje na zmenšenom obrázku (down×)
    kvôli rýchlosti, rozmazanie veľkými sigmami je inak veľmi drahé."""
    f = img.astype(np.float32) + 1.0
    small = cv2.resize(f, (img.shape[1] // down, img.shape[0] // down), interpolation=cv2.INTER_AREA)
    out = np.zeros_like(f)
    for s in sigmas:
        blur = cv2.GaussianBlur(small, (0, 0), s / down)
        blur = cv2.resize(blur, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
        out += np.log(f) - np.log(blur)
    out /= len(sigmas)
    lo, hi = np.percentile(out, (1, 99))
    out = (out - lo) / max(hi - lo, 1e-6)
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def wiener(img, ksize: int = 5):
    """Adaptívny (lokálny) Wienerov filter na potlačenie šumu, per kanál.
    Rovnaký vzorec ako scipy.signal.wiener, ale cez cv2.boxFilter (rýchlejšie):
        out = mu + max(var - noise, 0) / max(var, noise) * (x - mu)
    noise = priemer lokálnych rozptylov (odhad z dát)."""
    x = img.astype(np.float32)
    mu = cv2.boxFilter(x, -1, (ksize, ksize))
    mu2 = cv2.boxFilter(x * x, -1, (ksize, ksize))
    var = np.maximum(mu2 - mu * mu, 0)
    noise = var.reshape(-1, 3).mean(0)
    gain = np.maximum(var - noise, 0) / np.maximum(var, noise)
    return np.clip(mu + gain * (x - mu), 0, 255).astype(np.uint8)


def wiener_gamma(img):
    """Najprv odšumiť (Wiener), potom zosvetliť (adaptívna gama).
    Poradie je dôležité: zosvetlenie by zosilnilo aj šum."""
    return gamma_auto(wiener(img))


def bilateral(img):
    """Bilaterálny filter (odšumenie so zachovaním hrán)."""
    return cv2.bilateralFilter(img, d=5, sigmaColor=40, sigmaSpace=5)


def nlmeans(img):
    """Non-local means odšumenie (kvalitné, ale pomalé, len na porovnanie)."""
    return cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 5, 15)


def _dark_channel(img, size):
    return cv2.erode(img.min(axis=2), cv2.getStructuringElement(cv2.MORPH_RECT, (size, size)))


def dehaze(img, omega: float = 0.85, size: int = 15, down: int = 4):
    """Dark Channel Prior (He et al. 2009), zjednodušený: prenosová mapa sa počíta
    na zmenšenom obrázku a zjemní sa rozmazaním (namiesto guided filtra).
    Pomáha pri hmle/opare, dážď na objektíve to nevyrieši."""
    f = img.astype(np.float32) / 255.0
    small = cv2.resize(f, (img.shape[1] // down, img.shape[0] // down), interpolation=cv2.INTER_AREA)
    dc = _dark_channel(small, max(3, size // down))
    n = max(1, dc.size // 1000)
    idx = np.argsort(dc.ravel())[-n:]
    A = small.reshape(-1, 3)[idx].max(0)
    t = 1.0 - omega * _dark_channel(small / np.maximum(A, 1e-3), max(3, size // down))
    t = cv2.GaussianBlur(t, (0, 0), 3)
    t = cv2.resize(t, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    t = np.maximum(t, 0.25)[..., None]
    out = (f - A) / t + A
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 2. Naučené zosvetľovače (PyTorch), veľmi malé siete
# ---------------------------------------------------------------------------
_torch_cache = {}


def _device():
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_sd(path):
    import torch

    # weights_only=True: načíta len tenzory, nespustí žiadny kód z pickle súboru
    sd = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    return {k[7:] if k.startswith("module.") else k: v for k, v in sd.items()}


def _build_sci():
    """SCI (Ma et al., CVPR 2022). Pri inferencii ostanú len 3 konvolúcie (~300 parametrov)."""
    import torch
    import torch.nn as nn

    class EnhanceNetwork(nn.Module):
        def __init__(self, layers=1, channels=3):
            super().__init__()
            self.in_conv = nn.Sequential(nn.Conv2d(3, channels, 3, 1, 1), nn.ReLU())
            self.conv = nn.Sequential(nn.Conv2d(channels, channels, 3, 1, 1), nn.BatchNorm2d(channels), nn.ReLU())
            self.blocks = nn.ModuleList([self.conv for _ in range(layers)])
            self.out_conv = nn.Sequential(nn.Conv2d(channels, 3, 3, 1, 1), nn.Sigmoid())

        def forward(self, x):
            fea = self.in_conv(x)
            for conv in self.blocks:
                fea = fea + conv(fea)
            return torch.clamp(self.out_conv(fea) + x, 1e-4, 1)

    class SCI(nn.Module):
        def __init__(self):
            super().__init__()
            self.enhance = EnhanceNetwork()

        def forward(self, x):
            return torch.clamp(x / self.enhance(x), 0, 1)

    m = SCI()
    sd = {k: v for k, v in _load_sd(os.path.join(WEIGHTS, "sci_medium.pt")).items() if k.startswith("enhance.")}
    m.load_state_dict(sd, strict=True)
    return m.eval()


def _build_zdce():
    """Zero-DCE++ (Li, Guo, Loy, TPAMI 2021). ~10k parametrov, krivky sa odhadujú
    na 12× zmenšenom obrázku, takže je rýchly aj pre veľké rozlíšenie."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class CSDN(nn.Module):
        def __init__(self, i, o):
            super().__init__()
            self.depth_conv = nn.Conv2d(i, i, 3, 1, 1, groups=i)
            self.point_conv = nn.Conv2d(i, o, 1, 1, 0)

        def forward(self, x):
            return self.point_conv(self.depth_conv(x))

    class ZeroDCEpp(nn.Module):
        def __init__(self, scale=12):
            super().__init__()
            nf = 32
            self.scale = scale
            self.relu = nn.ReLU(inplace=True)
            self.e_conv1, self.e_conv2 = CSDN(3, nf), CSDN(nf, nf)
            self.e_conv3, self.e_conv4 = CSDN(nf, nf), CSDN(nf, nf)
            self.e_conv5, self.e_conv6 = CSDN(2 * nf, nf), CSDN(2 * nf, nf)
            self.e_conv7 = CSDN(2 * nf, 3)

        def forward(self, x):
            H, W = x.shape[-2:]
            xd = F.interpolate(x, scale_factor=1 / self.scale, mode="bilinear")
            x1 = self.relu(self.e_conv1(xd))
            x2 = self.relu(self.e_conv2(x1))
            x3 = self.relu(self.e_conv3(x2))
            x4 = self.relu(self.e_conv4(x3))
            x5 = self.relu(self.e_conv5(torch.cat([x3, x4], 1)))
            x6 = self.relu(self.e_conv6(torch.cat([x2, x5], 1)))
            r = torch.tanh(self.e_conv7(torch.cat([x1, x6], 1)))
            r = F.interpolate(r, size=(H, W), mode="bilinear", align_corners=True)
            for _ in range(8):
                x = x + r * (x * x - x)
            return x.clamp(0, 1)

    m = ZeroDCEpp()
    m.load_state_dict(_load_sd(os.path.join(WEIGHTS, "zerodcepp_Epoch99.pth")), strict=True)
    return m.eval()


def _run_torch(name, builder, img):
    import torch

    if name not in _torch_cache:
        _torch_cache[name] = builder().to(_device())
    m = _torch_cache[name]
    x = torch.from_numpy(img[..., ::-1].copy()).to(_device()).permute(2, 0, 1)[None].float() / 255.0
    with torch.inference_mode():
        y = m(x)
    y = (y[0].permute(1, 2, 0) * 255.0).round().byte().cpu().numpy()
    return np.ascontiguousarray(y[..., ::-1])


def sci(img):
    return _run_torch("sci", _build_sci, img)


def zero_dce(img):
    return _run_torch("zdce", _build_zdce, img)


# ---------------------------------------------------------------------------
METHODS = {
    "none": none,
    "gamma": gamma,
    "gamma_auto": gamma_auto,
    "he": he,
    "clahe": clahe,
    "gamma_clahe": gamma_clahe,
    "msr": msr,
    "wiener": wiener,
    "wiener_gamma": wiener_gamma,
    "bilateral": bilateral,
    "nlmeans": nlmeans,
    "dehaze": dehaze,
    "sci": sci,
    "zero_dce": zero_dce,
}


def get_method(name):
    return METHODS[name]


def macs_per_pixel():
    """Približný počet operácií na pixel pre klasické metódy (odhad, nie meranie).
    Pre CNN sa GFLOPs merajú v benchmark.py (torch flop_counter)."""
    return {
        "gamma": 3,  # 1 lookup na kanál
        "gamma_auto": 4,
        "he": 20,
        "clahe": 30,
        "gamma_clahe": 34,
        "msr": 60,
        "wiener": 40,
        "wiener_gamma": 44,
        "bilateral": 5 * 5 * 3 * 6,
        "nlmeans": 5 * 5 * 15 * 15 * 3,
        "dehaze": 40,
    }
