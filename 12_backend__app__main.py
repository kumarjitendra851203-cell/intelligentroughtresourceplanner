import csv, io, time
from collections import defaultdict
from datetime import datetime
from typing import Literal, Optional
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from . import config
from .db import Base, engine, get_db
from .models import User, Vehicle, Plan
from .security import hash_pw, check_pw, make_token, read_token
from .algorithms import nearest_neighbor, two_opt, estimate_cost, allocate, route_len, VERSION

Base.metadata.create_all(engine)
app = FastAPI(title="IRRP API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
DEF_SETTINGS = {"unit": "km", "currency": "₹", "fuel_price": 100.0, "tariff": 8.0, "dwell_min": 15, "objective": "distance"}
_hits = defaultdict(list)

def limit(req: Request, key: str, n=20, w=60):
    ip = req.client.host if req.client else "?"; now = time.time()
    h = [t for t in _hits[(key, ip)] if now - t < w]
    if len(h) >= n: raise HTTPException(429, "Too many attempts, try again later")
    h.append(now); _hits[(key, ip)] = h

def user(req: Request, db: Session = Depends(get_db)):
    uid = read_token(req.cookies.get("irrp_token", ""))
    u = db.get(User, uid) if uid else None
    if not u: raise HTTPException(401, "Not authenticated")
    return u

def cfg(u): return {**DEF_SETTINGS, **(u.settings or {})}

# ---------- auth ----------
class Cred(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    password: str = Field(min_length=8, max_length=128)

def _login(resp: Response, u: User):
    resp.set_cookie("irrp_token", make_token(u.id), httponly=True, samesite=config.COOKIE_SAMESITE, secure=config.COOKIE_SECURE, max_age=7 * 86400)
    return {"id": u.id, "email": u.email}

@app.post("/api/auth/register", status_code=201)
def register(c: Cred, req: Request, resp: Response, db: Session = Depends(get_db)):
    limit(req, "auth")
    email = c.email.lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, "Email already registered")
    u = User(email=email, pw=hash_pw(c.password), settings={}); db.add(u); db.commit()
    return _login(resp, u)

@app.post("/api/auth/login")
def login(c: Cred, req: Request, resp: Response, db: Session = Depends(get_db)):
    limit(req, "auth")
    u = db.query(User).filter_by(email=c.email.lower()).first()
    if not u or not check_pw(c.password, u.pw): raise HTTPException(401, "Invalid email or password")
    return _login(resp, u)

@app.post("/api/auth/logout")
def logout(resp: Response):
    resp.delete_cookie("irrp_token"); return {"ok": True}

@app.get("/api/auth/me")
def me(u: User = Depends(user)): return {"id": u.id, "email": u.email}

class SettingsIn(BaseModel):
    unit: Literal["km", "mi"] = "km"; currency: str = Field("₹", max_length=4)
    fuel_price: float = Field(100, ge=0); tariff: float = Field(8, ge=0)
    dwell_min: float = Field(15, ge=0); objective: Literal["distance", "time", "cost"] = "distance"

@app.get("/api/settings")
def get_settings(u: User = Depends(user)): return cfg(u)

@app.put("/api/settings")
def put_settings(s: SettingsIn, u: User = Depends(user), db: Session = Depends(get_db)):
    u.settings = s.model_dump(); db.commit(); return cfg(u)

# ---------- external services ----------
def osrm(path, params=None):
    try:
        r = httpx.get(config.ROUTING_API_URL + path, params=params, timeout=15, headers={"User-Agent": "IRRP/1.0"})
        if r.status_code in (400, 404): return r.json()
        r.raise_for_status(); return r.json()
    except Exception:
        raise HTTPException(502, "Routing service unavailable. Try again later or set ROUTING_API_URL to another OSRM server.")

@app.get("/api/geocode")
def geocode(q: str = Query(min_length=2, max_length=200), u: User = Depends(user), req: Request = None):
    limit(req, "geo", n=30)
    try:
        r = httpx.get(config.GEOCODING_API_URL + "/search", params={"q": q, "format": "json", "limit": 5}, timeout=10, headers={"User-Agent": "IRRP/1.0 (route planner)"})
        r.raise_for_status()
        return [{"name": x["display_name"][:120], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in r.json()]
    except Exception:
        raise HTTPException(502, "Geocoding service unavailable")

# ---------- resources (vehicles) ----------
class VehicleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120); vtype: Literal["fuel", "ev"] = "fuel"
    capacity: float = Field(0, ge=0); efficiency: float = Field(gt=0); cost_per_km: float = Field(0, ge=0)
    status: Literal["available", "maintenance", "unavailable"] = "available"

def vdict(v): return {c: getattr(v, c) for c in ("id", "name", "vtype", "capacity", "efficiency", "cost_per_km", "status")}

def own(db, model, id, u):
    o = db.get(model, id)
    if not o or o.user_id != u.id: raise HTTPException(404, "Not found")
    return o

@app.get("/api/resources")
def list_vehicles(u: User = Depends(user), db: Session = Depends(get_db)):
    vs = db.query(Vehicle).filter_by(user_id=u.id).order_by(Vehicle.id).all()
    out = []
    for v in vs:
        d = vdict(v); d["plans"] = [p.name for p in db.query(Plan).filter(Plan.user_id == u.id, Plan.vehicle_id == v.id, Plan.status != "archived")]; out.append(d)
    return out

@app.post("/api/resources", status_code=201)
def add_vehicle(b: VehicleIn, u: User = Depends(user), db: Session = Depends(get_db)):
    v = Vehicle(user_id=u.id, **b.model_dump()); db.add(v); db.commit(); return vdict(v)

@app.get("/api/resources/{id}")
def get_vehicle(id: int, u: User = Depends(user), db: Session = Depends(get_db)): return vdict(own(db, Vehicle, id, u))

@app.put("/api/resources/{id}")
def put_vehicle(id: int, b: VehicleIn, u: User = Depends(user), db: Session = Depends(get_db)):
    v = own(db, Vehicle, id, u)
    for k, x in b.model_dump().items(): setattr(v, k, x)
    db.commit(); return vdict(v)

@app.delete("/api/resources/{id}", status_code=204)
def del_vehicle(id: int, u: User = Depends(user), db: Session = Depends(get_db)):
    v = own(db, Vehicle, id, u)
    db.query(Plan).filter_by(user_id=u.id, vehicle_id=id).update({"vehicle_id": None}); db.delete(v); db.commit()

# ---------- route planning ----------
class Pt(BaseModel):
    name: str = Field(max_length=120); lat: float = Field(ge=-90, le=90); lon: float = Field(ge=-180, le=180)

class PlanIn(BaseModel):
    points: list[Pt] = Field(min_length=2, max_length=25); optimize: bool = True
    objective: Literal["distance", "time", "cost"] = "distance"; vehicle_id: Optional[int] = None
    toll: float = Field(0, ge=0); other: float = Field(0, ge=0)

def coords(pts): return ";".join(f"{p.lon},{p.lat}" for p in pts)

@app.post("/api/routes/plan")
def plan_route(p: PlanIn, u: User = Depends(user), db: Session = Depends(get_db)):
    s, n, pts = cfg(u), len(p.points), p.points
    v = vdict(own(db, Vehicle, p.vehicle_id, u)) if p.vehicle_id else None
    t = osrm(f"/table/v1/driving/{coords(pts)}", {"annotations": "distance,duration"})
    if t.get("code") != "Ok": raise HTTPException(422, "Could not compute distances between these points")
    D, T = t["distances"], t["durations"]
    if any(x is None for row in D + T for x in row): raise HTTPException(422, "One or more points are unreachable by road")
    order, m = list(range(n)), (T if p.objective == "time" else D)
    if p.optimize and n > 3: order = two_opt(m, 0, nearest_neighbor(m, 0, range(1, n - 1)), n - 1)
    ordered = [pts[i] for i in order]
    r = osrm(f"/route/v1/driving/{coords(ordered)}", {"overview": "full", "geometries": "geojson", "alternatives": "true"})
    if r.get("code") != "Ok": raise HTTPException(422, "No road route found for these points")
    stop_min = (n - 2) * s["dwell_min"]; routes = []
    for x in r["routes"]:
        km = x["distance"] / 1000
        routes.append({"distance_km": round(km, 2), "drive_min": round(x["duration"] / 60, 1), "stop_min": stop_min, "total_min": round(x["duration"] / 60 + stop_min, 1),
                       "cost": estimate_cost(km, v, s["fuel_price"], s["tariff"], p.toll, p.other) if v else None, "geometry": x["geometry"]})
    key, best_by = {"distance": lambda x: x["distance_km"], "time": lambda x: x["drive_min"]}.get(p.objective), p.objective
    if p.objective == "cost":
        if v: key = lambda x: x["cost"]["total"]
        else: key, best_by = (lambda x: x["distance_km"]), "distance (no vehicle selected for cost)"
    best = min(range(len(routes)), key=lambda i: key(routes[i]))
    return {"order": order, "ordered_points": [x.model_dump() for x in ordered], "routes": routes, "best_index": best, "best_by": best_by,
            "original_km": round(route_len(D, list(range(n))) / 1000, 2), "optimized_km": round(route_len(D, order) / 1000, 2),
            "optimized": p.optimize and n > 3, "algorithm": f"nearest-neighbour + 2-opt (heuristic) {VERSION}" if p.optimize and n > 3 else "none (given order)",
            "source": f"OSRM {config.ROUTING_API_URL}", "calculated_at": datetime.utcnow().isoformat() + "Z"}

# ---------- allocation ----------
def conflict(db, uid, vid, st, en, exclude=None):
    q = db.query(Plan).filter(Plan.user_id == uid, Plan.vehicle_id == vid, Plan.status != "archived", Plan.st < en, Plan.en > st)
    if exclude: q = q.filter(Plan.id != exclude)
    c = q.first(); return c.name if c else None

class AllocIn(BaseModel):
    distance_km: float = Field(ge=0); duration_min: float = Field(ge=0); demand: float = Field(0, ge=0)
    depart: datetime; toll: float = Field(0, ge=0); other: float = Field(0, ge=0); exclude_plan_id: Optional[int] = None

@app.post("/api/allocations/optimize")
def alloc(a: AllocIn, u: User = Depends(user), db: Session = Depends(get_db)):
    s, st = cfg(u), a.depart.timestamp(); en = st + a.duration_min * 60
    vs = [{**vdict(v), "conflict": conflict(db, u.id, v.id, st, en, a.exclude_plan_id)} for v in db.query(Vehicle).filter_by(user_id=u.id)]
    return allocate(vs, a.demand, a.distance_km, s["fuel_price"], s["tariff"], a.toll, a.other)

# ---------- saved plans ----------
class PlanSave(BaseModel):
    name: str = Field(min_length=1, max_length=120); status: Literal["planned", "completed", "archived"] = "planned"
    objective: Literal["distance", "time", "cost"] = "distance"; depart: datetime; vehicle_id: Optional[int] = None
    demand: float = Field(0, ge=0); distance_km: float = Field(ge=0); duration_min: float = Field(ge=0)
    cost: Optional[float] = None; data: dict

def pdict(p): return {"id": p.id, "name": p.name, "status": p.status, "objective": p.objective, "vehicle_id": p.vehicle_id, "demand": p.demand,
                      "distance_km": p.distance_km, "duration_min": p.duration_min, "cost": p.cost, "depart": datetime.fromtimestamp(p.st).isoformat(timespec="minutes"),
                      "created": p.created.isoformat(), "data": p.data}

def apply(p, b, u, db):
    st = b.depart.timestamp(); en = st + b.duration_min * 60
    if b.vehicle_id:
        v = own(db, Vehicle, b.vehicle_id, u)
        if v.status != "available": raise HTTPException(409, f"Vehicle is {v.status}")
        if v.capacity < b.demand: raise HTTPException(409, f"Capacity {v.capacity} is less than required {b.demand}")
        c = conflict(db, u.id, v.id, st, en, p.id)
        if c: raise HTTPException(409, f"Vehicle already assigned to '{c}' in an overlapping time window")
    for k in ("name", "status", "objective", "vehicle_id", "demand", "distance_km", "duration_min", "cost", "data"): setattr(p, k, getattr(b, k))
    p.st, p.en = st, en

@app.post("/api/routes", status_code=201)
def save_plan(b: PlanSave, u: User = Depends(user), db: Session = Depends(get_db)):
    p = Plan(user_id=u.id); apply(p, b, u, db); db.add(p); db.commit(); return pdict(p)

@app.get("/api/routes")
def list_plans(search: str = "", status: str = "", skip: int = 0, limit: int = Query(100, le=500), u: User = Depends(user), db: Session = Depends(get_db)):
    q = db.query(Plan).filter_by(user_id=u.id)
    if search: q = q.filter(Plan.name.ilike(f"%{search}%"))
    if status: q = q.filter_by(status=status)
    return [pdict(p) for p in q.order_by(Plan.created.desc()).offset(skip).limit(limit)]

@app.get("/api/routes/{id}")
def get_plan(id: int, u: User = Depends(user), db: Session = Depends(get_db)): return pdict(own(db, Plan, id, u))

@app.put("/api/routes/{id}")
def put_plan(id: int, b: PlanSave, u: User = Depends(user), db: Session = Depends(get_db)):
    p = own(db, Plan, id, u); apply(p, b, u, db); db.commit(); return pdict(p)

@app.delete("/api/routes/{id}", status_code=204)
def del_plan(id: int, u: User = Depends(user), db: Session = Depends(get_db)):
    db.delete(own(db, Plan, id, u)); db.commit()

# ---------- analytics & reports ----------
def filtered(u, db, status, vehicle_id, objective, date_from, date_to):
    q = db.query(Plan).filter_by(user_id=u.id)
    if status: q = q.filter_by(status=status)
    if vehicle_id: q = q.filter_by(vehicle_id=vehicle_id)
    if objective: q = q.filter_by(objective=objective)
    if date_from: q = q.filter(Plan.created >= date_from)
    if date_to: q = q.filter(Plan.created <= date_to)
    return q.order_by(Plan.created).all()

@app.get("/api/analytics/overview")
def overview(status: str = "", vehicle_id: Optional[int] = None, objective: str = "", date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
             u: User = Depends(user), db: Session = Depends(get_db)):
    ps = filtered(u, db, status, vehicle_id, objective, date_from, date_to)
    vs = db.query(Vehicle).filter_by(user_id=u.id).all()
    names = {v.id: v.name for v in vs}; usage, monthly = defaultdict(int), defaultdict(int)
    for p in ps:
        if p.vehicle_id: usage[names.get(p.vehicle_id, "?")] += 1
        monthly[p.created.strftime("%Y-%m")] += 1
    used = {p.vehicle_id for p in db.query(Plan).filter(Plan.user_id == u.id, Plan.status != "archived", Plan.vehicle_id != None)}
    return {"plans": len(ps), "distance_km": round(sum(p.distance_km for p in ps), 2), "duration_min": round(sum(p.duration_min for p in ps), 1),
            "cost": round(sum(p.cost or 0 for p in ps), 2), "vehicles": len(vs), "available_vehicles": sum(v.status == "available" for v in vs),
            "utilization_pct": round(len(used) / len(vs) * 100, 1) if vs else None,
            "by_plan": [{"id": p.id, "name": p.name, "distance_km": p.distance_km, "cost": p.cost, "status": p.status, "objective": p.objective} for p in ps],
            "vehicle_usage": [{"name": k, "plans": v} for k, v in usage.items()], "monthly": [{"month": k, "plans": v} for k, v in sorted(monthly.items())]}

def safe(x):
    x = "" if x is None else str(x)
    return "'" + x if x[:1] in "=+-@" else x

def csv_resp(rows, name):
    b = io.StringIO(); w = csv.writer(b)
    for r in rows: w.writerow([safe(x) for x in r])
    return Response(b.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})

@app.get("/api/reports/routes.csv")
def routes_csv(u: User = Depends(user), db: Session = Depends(get_db)):
    names = {v.id: v.name for v in db.query(Vehicle).filter_by(user_id=u.id)}
    rows = [["name", "status", "objective", "departure", "distance_km", "duration_min", "cost", "vehicle", "demand", "created"]]
    for p in db.query(Plan).filter_by(user_id=u.id).order_by(Plan.created):
        rows.append([p.name, p.status, p.objective, pdict(p)["depart"], p.distance_km, p.duration_min, p.cost, names.get(p.vehicle_id, ""), p.demand, p.created.isoformat()])
    return csv_resp(rows, "routes.csv")

@app.get("/api/reports/resources.csv")
def resources_csv(u: User = Depends(user), db: Session = Depends(get_db)):
    rows = [["name", "type", "capacity", "efficiency", "cost_per_km", "status"]]
    for v in db.query(Vehicle).filter_by(user_id=u.id): rows.append([v.name, v.vtype, v.capacity, v.efficiency, v.cost_per_km, v.status])
    return csv_resp(rows, "resources.csv")
