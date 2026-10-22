# IRRP – Intelligent Route & Resource Planner
Plan Smarter. Travel Better. Optimize Everything.

React + Vite + Leaflet/OpenStreetMap + Recharts (frontend) · FastAPI + SQLAlchemy + SQLite/PostgreSQL (backend) · OSRM (road routing) · Nominatim (geocoding).

## Run locally
Backend (Python 3.10+):
    cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env          # set SECRET_KEY
    uvicorn app.main:app --reload --port 8000     # API docs: http://localhost:8000/docs
    pytest -q                     # tests (external routing is mocked)
Frontend (Node 18+), in a second terminal:
    cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8000)

## How it works (honest notes)
- Roads, distances, durations, alternatives: OSRM (`ROUTING_API_URL`, default public demo server — for development only, no traffic data; self-host or switch provider for production).
- Address search: Nominatim via the backend (max ~1 request/sec, attribution required, do not bulk-geocode).
- Stop ordering: nearest-neighbour + 2-opt on the OSRM distance/duration matrix. HEURISTIC, not guaranteed optimal.
- Dijkstra and A* live in `app/algorithms.py` for graph routing (tested; the road planner itself uses OSRM).
- Allocation: constraint checks (status, capacity, time overlap) then cheapest feasible vehicle. No machine learning, no live traffic, no AI API anywhere.
- Costs: fuel = km / (km/l) × price; EV = km × kWh/100km / 100 × tariff; plus per-km cost, tolls and driver cost you enter.
- If OSRM fails you get a clear 502 error; the app never draws an invented straight-line road route.

## Not implemented yet
Drivers module, stop priorities/time windows, OR-Tools, Alembic migrations (tables are auto-created), Tailwind/Lucide, frontend tests, printable PDF report, password reset, profile editing.

## Deploy
Backend (Render): see `render.yaml`; set DATABASE_URL (managed PostgreSQL), SECRET_KEY, CORS_ORIGINS=https://your-frontend, COOKIE_SAMESITE=none, COOKIE_SECURE=true.
Frontend (Vercel): root `frontend`, env `VITE_API_URL=https://your-backend`. Nothing here has been deployed or tested live.
