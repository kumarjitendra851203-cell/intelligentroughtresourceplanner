import os, tempfile
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
import pytest
from fastapi.testclient import TestClient
from app import main
from app.algorithms import dijkstra, astar, nearest_neighbor, two_opt, estimate_cost, haversine

def fake_osrm(path, params=None):
    cs = [tuple(map(float, c.split(","))) for c in path.split("/")[-1].split(";")]
    if any(c[0] > 170 for c in cs): raise main.HTTPException(502, "Routing service unavailable")
    if path.startswith("/table"):
        d = [[haversine((a[1], a[0]), (b[1], b[0])) * 1000 for b in cs] for a in cs]
        return {"code": "Ok", "distances": d, "durations": [[x / 15 for x in r] for r in d]}
    km = sum(haversine((a[1], a[0]), (b[1], b[0])) for a, b in zip(cs, cs[1:]))
    return {"code": "Ok", "routes": [{"distance": km * 1000, "duration": km * 60, "geometry": {"type": "LineString", "coordinates": [list(c) for c in cs]}}]}

@pytest.fixture()
def c(monkeypatch):
    monkeypatch.setattr(main, "osrm", fake_osrm); main._hits.clear(); return TestClient(main.app)

def reg(c, email="a@x.com"):
    r = c.post("/api/auth/register", json={"email": email, "password": "password123"}); assert r.status_code == 201

def test_algorithms():
    g = {"a": {"b": 1, "c": 4}, "b": {"c": 1}, "c": {}}
    assert dijkstra(g, "a", "c") == (["a", "b", "c"], 2) and astar(g, "a", "c", lambda n: 0)[1] == 2 and dijkstra(g, "c", "a") is None
    m = [[0, 1, 9, 9], [1, 0, 1, 9], [9, 1, 0, 1], [9, 9, 1, 0]]
    assert two_opt(m, 0, nearest_neighbor(m, 0, [2, 1]), 3) == [0, 1, 2, 3]
    assert estimate_cost(100, {"vtype": "fuel", "efficiency": 10, "cost_per_km": 1}, 100, 8, 50, 20)["total"] == 1000 + 100 + 70
    assert estimate_cost(100, {"vtype": "ev", "efficiency": 15}, 100, 8)["total"] == 120

def test_auth_and_protection(c):
    assert c.get("/api/routes").status_code == 401
    reg(c); assert c.get("/api/auth/me").json()["email"] == "a@x.com"
    c.post("/api/auth/logout"); c.cookies.clear()
    assert c.post("/api/auth/login", json={"email": "a@x.com", "password": "wrongpass1"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"}).status_code == 200

def test_vehicle_allocation_and_conflicts(c):
    reg(c)
    small = c.post("/api/resources", json={"name": "S", "capacity": 10, "efficiency": 10}).json()
    big = c.post("/api/resources", json={"name": "B", "capacity": 100, "efficiency": 5}).json()
    body = {"distance_km": 100, "duration_min": 120, "demand": 50, "depart": "2026-11-01T09:00"}
    a = c.post("/api/allocations/optimize", json=body).json(); assert a["assigned"]["vehicle_id"] == big["id"]
    plan = {"name": "P1", "depart": "2026-11-01T09:00", "vehicle_id": big["id"], "demand": 50, "distance_km": 100, "duration_min": 120, "cost": 1, "data": {}}
    assert c.post("/api/routes", json=plan).status_code == 201
    assert c.post("/api/routes", json={**plan, "name": "P2"}).status_code == 409           # double booking
    assert c.post("/api/routes", json={**plan, "vehicle_id": small["id"]}).status_code == 409  # capacity
    a = c.post("/api/allocations/optimize", json=body).json(); assert a["assigned"] is None and "overlapping" in a["reason"]

def test_plan_route_save_isolation_csv(c):
    reg(c)
    pts = [{"name": n, "lat": la, "lon": lo} for n, la, lo in [("A", 23.2, 77.4), ("B", 22.7, 75.8), ("C", 23.1, 76.9), ("D", 21.1, 79.0)]]
    r = c.post("/api/routes/plan", json={"points": pts}).json()
    assert len(r["routes"]) == 1 and r["optimized_km"] <= r["original_km"] and r["order"][0] == 0 and r["order"][-1] == 3
    assert c.post("/api/routes/plan", json={"points": pts[:1]}).status_code == 422
    assert c.post("/api/routes/plan", json={"points": [pts[0], {"name": "X", "lat": 0, "lon": 175}]}).status_code == 502   # provider failure
    pid = c.post("/api/routes", json={"name": "Trip", "depart": "2026-11-02T08:00", "distance_km": 5, "duration_min": 10, "data": {"x": 1}}).json()["id"]
    assert "Trip" in c.get("/api/reports/routes.csv").text and c.get("/api/analytics/overview").json()["plans"] == 1
    c.post("/api/auth/logout"); c.cookies.clear(); reg(c, "b@x.com")
    assert c.get(f"/api/routes/{pid}").status_code == 404 and c.get("/api/routes").json() == []
