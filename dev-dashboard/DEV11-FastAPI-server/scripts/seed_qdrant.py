"""Naplní lokálnu Qdrant databázu ukážkovými prejazdmi, aby sa API dalo vyskúšať bez GPU a bez videa.

Zábery sú skutočné (data/frames – autá z RoundaboutHD, ktoré našla naša YOLO pipeline),
ale kamery a časy prejazdov sú vymyslené: ~1 200 prejazdov za deň, posledných 48 hodín,
rozložené podľa dennej doby (ranná a popoludňajšia špička).
Vektory počíta placeholder embedder (app/embedder.py), rovnaký ako pri vyhľadávaní cez API.

Formát bodov je rovnaký ako v pipeline rd-research/02-multi-view-reid, navyše s `ts` (unix čas)
a ISO dátumom v `timestamp`. Keď pobeží skutočná pipeline, tento skript netreba.

    python scripts/seed_qdrant.py            # vytvorí ./qdrant_data (prepíše existujúce kolekcie)
    python scripts/seed_qdrant.py --per-day 600
    python scripts/seed_qdrant.py --url http://localhost:6333   # Qdrant v Dockeri
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import mock  # noqa: E402
from app.config import get_settings, load_cameras  # noqa: E402
from app.embedder import embedder  # noqa: E402


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=s.qdrant_url, help="Qdrant server (inak lokálny súbor z settings.yaml)")
    ap.add_argument("--path", default=str(s.qdrant_path) if s.qdrant_path else None)
    ap.add_argument("--per-day", type=int, default=1200, help="Približný počet prejazdov za deň")
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--end", help="Koniec dát (ISO čas), predvolene teraz. Napr. 2026-11-18T14:30")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)

    frames = sorted((s.media_dir / "frames").glob("*.jpg"))
    if not frames:
        sys.exit(f"V {s.media_dir / 'frames'} nie sú žiadne zábery.")
    crops_dir = s.media_dir / "crops"
    print(f"Počítam vektory pre {len(frames)} áut ({embedder.name})...")
    vehicles = []
    for f in frames:
        vid = f.stem
        crop = crops_dir / f"{vid}.jpg"
        vehicles.append({
            "id": vid,
            "frame": f"frames/{f.name}",
            "crop": f"crops/{crop.name}" if crop.exists() else f"frames/{f.name}",
            "vec": embedder.embed_image(Image.open(f)),
            # niektoré autá jazdia často (rezidenti), iné raz
            "weight": rng.choice([1, 1, 1, 2, 3, 6]),
        })

    cams = [c for c in load_cameras() if mock.camera_status(c["id"])[0] != "offline"]
    # Kamery na hlavných ťahoch vidia viac áut ako kamery v areáloch škôl.
    cam_weights = [3.0 if c.get("site") == "ulica" else 0.6 for c in cams]

    now = datetime.fromisoformat(args.end) if args.end else datetime.now(s.timezone)
    now = (now if now.tzinfo else now.replace(tzinfo=s.timezone)).replace(microsecond=0)
    start = now - timedelta(hours=args.hours)
    hours = [start + timedelta(hours=i) for i in range(args.hours + 1)]
    mean_curve = np.mean([mock.traffic_curve(h + 0.5) for h in range(24)])
    sightings = []
    for h in hours:
        n = np_rng.poisson(args.per_day / 24 * mock.traffic_curve(h.hour + 0.5) / mean_curve)
        for _ in range(n):
            t = h + timedelta(seconds=rng.randrange(3600))
            if t > now:
                continue
            v = rng.choices(vehicles, weights=[x["weight"] for x in vehicles])[0]
            cam = rng.choices(cams, weights=cam_weights)[0]
            sightings.append((t, v, cam))
    sightings.sort(key=lambda x: x[0])

    client = QdrantClient(url=args.url) if args.url else QdrantClient(path=args.path)
    for name in (s.collection_reid, s.collection_dashboard):
        if client.collection_exists(name):
            client.delete_collection(name)
        client.create_collection(name, vectors_config=models.VectorParams(size=s.vector_size, distance=models.Distance.COSINE))
        for field, schema in (("ts", models.PayloadSchemaType.FLOAT), ("camera", models.PayloadSchemaType.KEYWORD),
                              ("original_id", models.PayloadSchemaType.KEYWORD)):
            client.create_payload_index(name, field, schema)

    points, last_seen = [], {}
    for t, v, cam in sightings:
        # Každý prejazd je iný pohľad na auto → vektor sa mierne líši.
        vec = v["vec"] + np_rng.normal(0, 0.015, size=v["vec"].shape)
        vec = (vec / np.linalg.norm(vec)).astype(np.float32)
        points.append(models.PointStruct(id=str(uuid.uuid4()), vector=vec.tolist(), payload={
            "original_id": v["id"],
            "slot": rng.choice(["first", "best", "last"]),
            "frame_path": v["frame"],
            "reid_crop_path": v["crop"],
            "timestamp": t.isoformat(),
            "ts": t.timestamp(),
            "camera": cam["id"],
            "area": cam.get("area"),
        }))
        last_seen[v["id"]] = (t, cam["id"], vec)
    for i in range(0, len(points), 512):
        client.upsert(s.collection_reid, points[i:i + 512])

    dash = []
    for v in vehicles:
        if v["id"] not in last_seen:
            continue
        t, cam, vec = last_seen[v["id"]]
        dash.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_DNS, v["id"])), vector=vec.tolist(), payload={
            "original_id": v["id"], "best_frame_path": v["frame"], "timestamp": t.isoformat(), "ts": t.timestamp(),
            "camera": cam, "views": [{"slot": "best", "reid_crop_path": v["crop"]}],
        }))
    client.upsert(s.collection_dashboard, dash)
    client.close()

    today = sum(1 for t, _, _ in sightings if t.date() == now.date())
    where = args.url or args.path
    print(f"Hotovo → {where}\n  {s.collection_reid}: {len(points)} prejazdov ({today} dnes)\n"
          f"  {s.collection_dashboard}: {len(dash)} áut\n  kamery: {len(cams)} (offline kamery bez dát)\n"
          f"Dáta končia {now:%d.%m. %H:%M} – pred prezentáciou spusti skript znova, nech je „dnes“ aktuálne.")


if __name__ == "__main__":
    main()
