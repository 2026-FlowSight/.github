"""Testy bežia nad vlastnou malou Qdrant databázou v dočasnom priečinku (nezávisle od ./qdrant_data)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("qdrant")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_qdrant.py"), "--path", str(db),
                    "--per-day", "300", "--end", "2026-11-17T17:45"], check=True, capture_output=True)
    os.environ["FLOWSIGHT_QDRANT_PATH"] = str(db)
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
