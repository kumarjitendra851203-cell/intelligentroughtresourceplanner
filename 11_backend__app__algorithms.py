"""Reusable optimisation modules. Nearest-neighbour + 2-opt are heuristics (not globally optimal)."""
import heapq, math
VERSION = "irrp-algo-1.0"
def haversine(a, b):
    r = math.radians; dl, dn = r(b[0]-a[0]), r(b[1]-a[1])
    h = math.sin(dl/2)**2 + math.cos(r(a[0]))*math.cos(r(b[0]))*math.sin(dn/2)**2
    return 12742 * math.asin(math.sqrt(h))
def dijkstra(graph, src, dst):
    """graph: {u: {v: weight>=0}}. Returns (path, cost) or None if unreachable."""
    dist, prev, done, pq = {src: 0}, {}, set(), [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if u in done: continue
        done.add(u)
        if u == dst: break
        for v, w in graph.get(u, {}).items():
            if w < 0: raise ValueError("negative edge weight")
            if d + w < dist.get(v, math.inf):
                dist[v] = d + w; prev[v] = u; heapq.heappush(pq, (d + w, v))
    if dst not in done: return None
    path = [dst]
    while path[-1] != src: path.append(prev[path[-1]])
    return path[::-1], dist[dst]
def astar(graph, src, dst, h):
    """Optimal only if h is admissible/consistent for the graph's weights."""
    g, prev, closed, pq = {src: 0}, {}, set(), [(h(src), src)]
    while pq:
        _, u = heapq.heappop(pq)
        if u in closed: continue
        if u == dst:
            path = [u]
            while path[-1] != src: path.append(prev[path[-1]])
            return path[::-1], g[u]
        closed.add(u)
        for v, w in graph.get(u, {}).items():
            if w < 0: raise ValueError("negative edge weight")
            if g[u] + w < g.get(v, math.inf):
                g[v] = g[u] + w; prev[v] = u; heapq.heappush(pq, (g[v] + h(v), v))
    return None
def route_len(m, order): return sum(m[a][b] for a, b in zip(order, order[1:]))
def nearest_neighbor(m, start, mid):
    cur, rest, out = start, list(mid), []
    while rest:
        nxt = min(rest, key=lambda x: m[cur][x]); rest.remove(nxt); out.append(nxt); cur = nxt
    return out
def two_opt(m, start, mid, end):
    """Improve order with fixed start/end. Returns full index order."""
    o = [start] + list(mid) + [end]; improved = True
    while improved:
        improved = False
        for i in range(1, len(o) - 2):
            for j in range(i + 1, len(o) - 1):
                n = o[:i] + o[i:j+1][::-1] + o[j+1:]
                if route_len(m, n) < route_len(m, o) - 1e-9: o, improved = n, True
    return o
def estimate_cost(km, v, fuel_price, tariff, toll=0, other=0):
    if v["vtype"] == "ev":
        units, unit, energy = km * v["efficiency"] / 100, "kWh", km * v["efficiency"] / 100 * tariff
    else:
        units, unit = km / v["efficiency"], "L"; energy = units * fuel_price
    per_km = km * (v.get("cost_per_km") or 0)
    return {"units": round(units, 3), "unit": unit, "energy_cost": round(energy, 2), "per_km_cost": round(per_km, 2),
            "toll": toll, "other": other, "total": round(energy + per_km + toll + other, 2)}
def allocate(vehicles, demand, km, fuel_price, tariff, toll=0, other=0):
    """vehicles: dicts with id,name,vtype,capacity,efficiency,cost_per_km,status,conflict(None|str)."""
    cands, best = [], None
    for v in vehicles:
        why = None
        if v["status"] != "available": why = f"status is {v['status']}"
        elif v["capacity"] < demand: why = f"capacity {v['capacity']} < required {demand}"
        elif v.get("conflict"): why = f"already assigned to '{v['conflict']}' in an overlapping time window"
        c = None if why else estimate_cost(km, v, fuel_price, tariff, toll, other)
        cands.append({"vehicle_id": v["id"], "name": v["name"], "feasible": why is None, "reason": why, "cost": c and c["total"]})
        if c and (best is None or c["total"] < best[1]["total"]): best = (v, c)
    if not best:
        return {"assigned": None, "candidates": cands, "reason": "No feasible vehicle: " + ("; ".join(f"{c['name']}: {c['reason']}" for c in cands) or "no vehicles configured")}
    v, c = best
    return {"assigned": {"vehicle_id": v["id"], "name": v["name"], "cost": c, "utilization_pct": round(demand / v["capacity"] * 100, 1) if v["capacity"] else 0},
            "candidates": cands, "reason": "Lowest estimated cost among feasible vehicles"}
