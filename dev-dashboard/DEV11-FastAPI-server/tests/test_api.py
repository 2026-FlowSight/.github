"""Overenie Definition of Done pre DEV11: API beží, endpointy vracajú dáta (aj z Qdrantu), Swagger funguje."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT.parents[1] / "data" / "frames"


def seeded_image():
    """Záber auta, ktoré v testovacej DB naozaj je (nie každé auto má pri malom seede prejazd)."""
    from app.main import settings, store
    pts, _ = store.client().scroll(settings.collection_dashboard, limit=1, with_payload=True)
    return FRAMES / Path(pts[0].payload["best_frame_path"]).name


def test_health_and_qdrant(client):
    j = client.get("/api/health").json()
    assert j["status"] == "ok"
    assert j["qdrant"]["ok"] is True
    assert j["qdrant"]["collections"]["vehicles_reid"] > 0
    assert j["config"] == {"cameras": 41, "parking": 12}


def test_swagger(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/search", "/api/cameras", "/api/parking", "/api/stats"):
        assert p in paths
    assert {"get", "post"} <= set(paths["/api/search"])


def test_cameras_have_gps(client):
    j = client.get("/api/cameras").json()
    assert j["count"] == 41
    assert sum(j["summary"].values()) == 41
    assert j["source"]["vehicles_today"] == "qdrant"
    for c in j["cameras"]:
        assert 48.2 < c["lat"] < 48.35 and 17.2 < c["lng"] < 17.35, c["id"]
        assert c["status"] in {"online", "warning", "offline"}
    assert sum(c["vehicles_today"] for c in j["cameras"]) > 0
    assert client.get("/api/cameras", params={"status": "offline"}).json()["count"] == j["summary"]["offline"]
    assert client.get("/api/cameras/msp-12").json()["no"] == "12"
    assert client.get("/api/cameras/neexistuje").status_code == 404


def test_parking(client):
    j = client.get("/api/parking").json()
    assert len(j["parking"]) == 12
    for p in j["parking"]:
        assert 0 <= p["occupied"] <= p["capacity"]
        assert p["free"] == p["capacity"] - p["occupied"]
        assert len(p["polygon"]) >= 4
    s = j["summary"]
    assert s["capacity"] == sum(p["capacity"] for p in j["parking"])
    assert sum(v["spaces"] for v in s["levels"].values()) == s["capacity"]


def test_stats_from_qdrant(client):
    j = client.get("/api/stats").json()
    assert j["source"] == "qdrant"
    assert j["as_of"].startswith("2026-11-17T17:4")
    assert len(j["hourly"]) == 24
    assert j["today"]["detections"] > 0
    # hodiny dnešného dňa spolu = počet dnes
    today = sum(h["count"] for h in j["hourly"] if h["start"].startswith("2026-11-17"))
    assert today == j["today"]["detections"]
    assert sum(r["count"] for r in j["by_camera"]) == j["today"]["detections"]


def test_search_by_image(client):
    img = seeded_image()
    r = client.post("/api/search", files={"image": (img.name, img.read_bytes(), "image/jpeg")}, data={"top_k": "3"})
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    assert len(res) == 3
    assert len({x["payload"]["original_id"] for x in res}) == 3, "Top-3 musia byť 3 rôzne autá"
    assert res[0]["payload"]["original_id"] == img.stem, "Rovnaký záber musí byť prvý"
    assert res[0]["score"] >= res[1]["score"] >= res[2]["score"]
    assert client.get(res[0]["image_url"]).status_code == 200


def test_search_filters(client):
    img = next(FRAMES.glob("*.jpg"))
    r = client.post("/api/search", files={"image": ("q.jpg", img.read_bytes(), "image/jpeg")},
                    data={"top_k": "5", "camera": ["msp-1", "msp-2"], "from": "2026-11-17T12:00:00"})
    res = r.json()["results"]
    assert res and all(x["payload"]["camera"] in {"msp-1", "msp-2"} for x in res)
    assert all(x["payload"]["timestamp"] >= "2026-11-17T12:00" for x in res)


def test_search_by_vehicle(client):
    img = seeded_image()
    r = client.get("/api/search", params={"vehicle_id": img.stem, "top_k": 3})
    assert r.status_code == 200
    assert img.stem not in {x["payload"]["original_id"] for x in r.json()["results"]}
    assert client.get("/api/search", params={"vehicle_id": "nie-je"}).status_code == 404


def test_search_rejects_bad_input(client):
    assert client.post("/api/search", files={"image": ("a.txt", b"hello", "text/plain")}).status_code == 422
    img = next(FRAMES.glob("*.jpg"))
    r = client.post("/api/search", files={"image": ("q.jpg", img.read_bytes(), "image/jpeg")}, data={"from": "včera"})
    assert r.status_code == 422


def test_cors_for_dashboard(client):
    r = client.options("/api/search", headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] in {"*", "http://localhost:5500"}


def test_serves_dashboard(client):
    assert client.get("/dashboard/DEV12-interactive-map/mapa.html").status_code == 200


def test_recent_vehicles(client):
    j = client.get("/api/vehicles/recent", params={"limit": 4}).json()
    assert j["count"] == 4
    times = [v["timestamp"] for v in j["vehicles"]]
    assert times == sorted(times, reverse=True)
    assert len({v["original_id"] for v in j["vehicles"]}) == 4
    assert client.get(j["vehicles"][0]["image_url"]).status_code == 200
    one = client.get("/api/vehicles/recent", params={"camera": "msp-1", "limit": 3}).json()
    assert all(v["camera"] == "msp-1" for v in one["vehicles"])
