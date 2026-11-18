"""Prevod obrázka na vektor pre vyhľadávanie v Qdrante.

PLACEHOLDER do DEV16: skutočný ReID model (TensorRT engine `models/vehicle_reid_fixed.engine`)
beží iba na NVIDIA GPU. Aby sa API dalo vyvíjať a otestovať aj na notebooku, je tu náhradný
embedder – farebný histogram v HSV (8×8×8 = 512 hodnôt, rovnaká dĺžka ako ReID vektor).
Nájde autá podobnej farby, nie to isté auto. Po DEV16 sa vymení iba trieda `Embedder`,
zvyšok API ostáva rovnaký.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

NAME = "hsv-histogram-512 (placeholder, DEV16 dodá ReID model)"


class EmbedError(ValueError):
    pass


class Embedder:
    name = NAME
    size = 512

    def embed_image(self, img: Image.Image) -> np.ndarray:
        img = img.convert("RGB")
        img.thumbnail((256, 256))
        hsv = np.asarray(img.convert("HSV"), dtype=np.uint8).reshape(-1, 3)
        # Stred výrezu nesie auto, okraje skôr cestu – vážime pixely podľa vzdialenosti od stredu.
        w, h = img.size
        yy, xx = np.mgrid[0:h, 0:w]
        weight = 1.0 - 0.7 * np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)).clip(0, 1)
        bins = (hsv // 32).astype(np.int32)  # 256 / 8 = 32
        idx = bins[:, 0] * 64 + bins[:, 1] * 8 + bins[:, 2]
        hist = np.bincount(idx, weights=weight.reshape(-1), minlength=512).astype(np.float32)
        vec = np.sqrt(hist / max(hist.sum(), 1e-9))  # Hellingerova transformácia, aby kosínus dával zmysel
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_bytes(self, data: bytes) -> np.ndarray:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as exc:  # noqa: BLE001 – Pillow hádže rôzne výnimky
            raise EmbedError("Súbor nie je platný obrázok (JPG, PNG, WebP).") from exc
        return self.embed_image(img)


embedder = Embedder()
