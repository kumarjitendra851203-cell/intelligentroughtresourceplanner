import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api, download } from "./api";

const n1 = (x, d = 1) => Number(x ?? 0).toFixed(d);
const hm = (m) => `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`;
const Err = ({ m }) => (m ? <div className="er" role="alert">{m}</div> : null);

export default function App() {
  const [me, setMe] = useState(undefined), [tab, setTab] = useState("home"), [edit, setEdit] = useState(null), [dark, setDark] = useState(false), [sm, setSm] = useState(false);
  useEffect(() => { api("/auth/me").then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  if (me === undefined) return <p style={{ padding: 20 }}>Loading…</p>;
  if (!me) return <Auth onDone={setMe} />;
  const T = [["home", "Dashboard"], ["plan", "Planner"], ["res", "Resources"], ["plans", "Saved plans"], ["ana", "Analytics"], ["set", "Settings"]];
  const View = { home: Home, plan: Planner, res: Resources, plans: Plans, ana: Analytics, set: Settings }[tab];
  return (
    <div className="app">
      <nav className={sm ? "sm" : ""}>
        <button onClick={() => setSm(!sm)} aria-label="Toggle sidebar">☰ {sm ? "" : "IRRP"}</button>
        {T.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)} title={l}>{sm ? l[0] : l}</button>)}
        <button onClick={() => setDark(!dark)}>{sm ? "◐" : dark ? "Light mode" : "Dark mode"}</button>
        <button onClick={async () => { await api("/auth/logout", { method: "POST" }); setMe(null); }}>{sm ? "⏻" : "Log out"}</button>
      </nav>
      <main><View edit={edit} setEdit={setEdit} onEdit={(p) => { setEdit(p); setTab("plan"); }} /></main>
    </div>
  );
}

function Auth({ onDone }) {
  const [mode, setMode] = useState("login"), [email, setE] = useState(""), [password, setP] = useState(""), [err, setErr] = useState(""), [busy, setB] = useState(false);
  const go = async (e) => { e.preventDefault(); setB(true); setErr(""); try { onDone(await api("/auth/" + mode, { body: { email, password } })); } catch (x) { setErr(x.message); } setB(false); };
  return (
    <div style={{ maxWidth: 380, margin: "8vh auto", padding: 16 }}>
      <h1 style={{ marginBottom: 0 }}>IRRP</h1><p className="mu">Plan Smarter. Travel Better. Optimize Everything.</p>
      <form className="cd" onSubmit={go}>
        <h3>{mode === "login" ? "Log in" : "Create account"}</h3>
        <label>Email<input type="email" required value={email} onChange={(e) => setE(e.target.value)} /></label>
        <label>Password (min 8 characters)<input type="password" required minLength={8} value={password} onChange={(e) => setP(e.target.value)} /></label>
        <Err m={err} /><div className="row"><button className="b" disabled={busy}>{mode === "login" ? "Log in" : "Register"}</button>
          <button type="button" className="b s" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Need an account?" : "Have an account?"}</button></div>
      </form>
    </div>
  );
}

function Home({ onEdit }) {
  const [o, setO] = useState(null), [ps, setPs] = useState([]), [s, setS] = useState({ currency: "₹" });
  useEffect(() => { api("/analytics/overview").then(setO); api("/routes?limit=5").then(setPs); api("/settings").then(setS); }, []);
  if (!o) return <p>Loading…</p>;
  const K = [["Saved plans", o.plans], ["Planned distance", n1(o.distance_km) + " km"], ["Est. duration", hm(o.duration_min)], ["Est. cost", s.currency + n1(o.cost, 2)], ["Available vehicles", `${o.available_vehicles}/${o.vehicles}`], ["Utilization", o.utilization_pct == null ? "—" : o.utilization_pct + "%"]];
  return (<><h2>Dashboard</h2><div className="kp">{K.map(([a, b]) => <div className="cd" key={a}><div className="mu">{a}</div><div className="k">{b}</div></div>)}</div>
    <div className="cd"><h3>Recent plans</h3>{ps.length ? ps.map((p) => <div className="row" key={p.id}><b>{p.name}</b><span className="mu">{n1(p.distance_km)} km · {p.status}</span><button className="b s" onClick={() => onEdit(p)}>Open</button></div>) : <p className="mu">No plans yet — open the Planner to create one.</p>}</div></>);
}

function Planner({ edit, setEdit }) {
  const [pts, setPts] = useState([]), [q, setQ] = useState(""), [hits, setHits] = useState([]), [veh, setVeh] = useState([]), [s, setS] = useState({ currency: "₹", objective: "distance" });
  const [f, setF] = useState({ name: "", depart: new Date(Date.now() + 36e5).toISOString().slice(0, 16), demand: 0, toll: 0, other: 0, vid: "", optimize: true, objective: "distance" });
  const [res, setRes] = useState(null), [sel, setSel] = useState(0), [al, setAl] = useState(null), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false), [eid, setEid] = useState(null);
  const el = useRef(), map = useRef(), layer = useRef(), set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  useEffect(() => { api("/resources").then(setVeh).catch(() => {}); api("/settings").then((x) => { setS(x); set("objective", x.objective); }).catch(() => {}); }, []);
  useEffect(() => {
    map.current = L.map(el.current).setView([22.9, 78.6], 5);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current); return () => map.current.remove();
  }, []);
  useEffect(() => {
    if (!edit) return; const d = edit.data || {};
    setPts(d.points || []); setRes(d.result || null); setSel(d.selected || 0); setEid(edit.id); setAl(null);
    setF((x) => ({ ...x, name: edit.name, depart: edit.depart, demand: edit.demand, vid: edit.vehicle_id || "", objective: edit.objective, toll: d.toll || 0, other: d.other || 0, optimize: false })); setEdit(null);
  }, [edit]);
  useEffect(() => {
    const g = layer.current; g.clearLayers(); const shown = res ? res.ordered_points : pts, b = [];
    shown.forEach((p, i) => { L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "", html: `<div class="pin">${i === 0 ? "S" : i === shown.length - 1 ? "E" : i}</div>`, iconSize: [24, 24] }) }).bindTooltip(p.name).addTo(g); b.push([p.lat, p.lon]); });
    res?.routes.forEach((r, i) => { const c = r.geometry.coordinates.map(([lo, la]) => [la, lo]); L.polyline(c, { color: i === sel ? "#1d4ed8" : "#94a3b8", weight: i === sel ? 5 : 3 }).addTo(g); if (i === sel) b.push(...c); });
    if (b.length) map.current.fitBounds(b, { padding: [30, 30] });
  }, [pts, res, sel]);
  const search = async () => { setMsg(""); try { setHits(await api("/geocode?q=" + encodeURIComponent(q))); } catch (e) { setMsg(e.message); } };
  const mv = (i, d) => { const a = [...pts], j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; setPts(a); setRes(null); };
  const calc = async () => {
    if (pts.length < 2) return setMsg("Add at least a start and a destination."); setBusy(true); setMsg(""); setAl(null);
    try { const r = await api("/routes/plan", { body: { points: pts, optimize: f.optimize, objective: f.objective, vehicle_id: f.vid ? +f.vid : null, toll: +f.toll, other: +f.other } }); setRes(r); setSel(r.best_index); }
    catch (e) { setMsg(e.message); } setBusy(false);
  };
  const cur = res?.routes[sel];
  const allocate = async () => {
    if (!cur) return setMsg("Calculate a route first."); setMsg("");
    try { const a = await api("/allocations/optimize", { body: { distance_km: cur.distance_km, duration_min: cur.total_min, demand: +f.demand, depart: f.depart, toll: +f.toll, other: +f.other, exclude_plan_id: eid } }); setAl(a); if (a.assigned) set("vid", a.assigned.vehicle_id); } catch (e) { setMsg(e.message); }
  };
  const save = async () => {
    if (!cur) return setMsg("Calculate a route first."); if (!f.name.trim()) return setMsg("Give the plan a name.");
    const v = veh.find((x) => x.id == f.vid), body = { name: f.name, objective: f.objective, depart: f.depart, vehicle_id: f.vid ? +f.vid : null, demand: +f.demand, distance_km: cur.distance_km, duration_min: cur.total_min,
      cost: v && cur.cost ? cur.cost.total : null, data: { points: res.ordered_points, result: res, selected: sel, toll: +f.toll, other: +f.other } };
    try { const p = await api(eid ? "/routes/" + eid : "/routes", { method: eid ? "PUT" : "POST", body }); setEid(p.id); setMsg("Plan saved ✓"); } catch (e) { setMsg(e.message); }
  };
  return (<><h2>{eid ? "Edit plan" : "Route planner"}</h2>
    <div className="g2"><div>
      <div className="cd"><h3>Places (first = start, last = destination)</h3>
        <div className="row"><input placeholder="Search an address or place" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} style={{ flex: 1 }} /><button className="b s" onClick={search}>Search</button></div>
        {hits.map((h, i) => <div className="row" key={i}><span style={{ flex: 1 }}>{h.name}</span><button className="b s" onClick={() => { setPts([...pts, h]); setHits([]); setRes(null); }}>Add</button></div>)}
        {pts.map((p, i) => <div className="row" key={i}><b>{i === 0 ? "S" : i === pts.length - 1 ? "E" : i}</b><span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{p.name}</span>
          <button className="b s" aria-label="Up" onClick={() => mv(i, -1)}>↑</button><button className="b s" aria-label="Down" onClick={() => mv(i, 1)}>↓</button><button className="b s" aria-label="Remove" onClick={() => { setPts(pts.filter((_, j) => j !== i)); setRes(null); }}>✕</button></div>)}
        {!pts.length && <p className="mu">Search and add at least two places.</p>}
      </div>
      <div className="cd"><h3>Plan settings</h3><div className="f">
        <label>Plan name<input value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
        <label>Departure<input type="datetime-local" value={f.depart} onChange={(e) => set("depart", e.target.value)} /></label>
        <label>Objective<select value={f.objective} onChange={(e) => set("objective", e.target.value)}><option value="distance">Shortest distance</option><option value="time">Fastest</option><option value="cost">Lowest cost</option></select></label>
        <label>Vehicle<select value={f.vid} onChange={(e) => set("vid", e.target.value)}><option value="">None</option>{veh.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
        <label>Load required<input type="number" min="0" value={f.demand} onChange={(e) => set("demand", e.target.value)} /></label>
        <label>Tolls ({s.currency}, your input)<input type="number" min="0" value={f.toll} onChange={(e) => set("toll", e.target.value)} /></label>
        <label>Driver/service ({s.currency})<input type="number" min="0" value={f.other} onChange={(e) => set("other", e.target.value)} /></label></div>
        <label className="row"><input type="checkbox" style={{ width: "auto" }} checked={f.optimize} onChange={(e) => set("optimize", e.target.checked)} /> Optimize stop order (heuristic)</label>
        <div className="row"><button className="b" disabled={busy} onClick={calc}>{busy ? "Calculating…" : "Calculate route"}</button><button className="b s" onClick={allocate}>Allocate vehicle</button><button className="b" onClick={save}>{eid ? "Update" : "Save"} plan</button></div>
        <Err m={msg.endsWith("✓") ? "" : msg} />{msg.endsWith("✓") && <div className="ok">{msg}</div>}
        {al && <div>{al.assigned ? <p className="ok">Assigned: <b>{al.assigned.name}</b> — {al.reason}. Utilization {al.assigned.utilization_pct}%, cost {s.currency}{al.assigned.cost.total}</p> : <p className="er">{al.reason}</p>}
          {al.candidates.map((c) => <div key={c.vehicle_id} className="mu">{c.feasible ? "✓" : "✗"} {c.name}: {c.feasible ? `${s.currency}${c.cost}` : c.reason}</div>)}</div>}
      </div></div>
      <div><div className="map" ref={el} />
        {res && <div className="cd"><h3>Routes {res.routes.length > 1 ? "(click to select)" : ""}</h3><div className="w"><table><thead><tr><th>#</th><th>Distance</th><th>Driving</th><th>Stops</th><th>Total</th><th>Cost</th><th></th></tr></thead><tbody>
          {res.routes.map((r, i) => <tr key={i} className={i === sel ? "sel" : ""} onClick={() => setSel(i)} style={{ cursor: "pointer" }}><td>{i + 1}</td><td>{n1(r.distance_km)} km</td><td>{hm(r.drive_min)}</td><td>{hm(r.stop_min)}</td><td>{hm(r.total_min)}</td><td>{r.cost ? s.currency + r.cost.total : "—"}</td><td>{i === res.best_index ? `Best by ${res.best_by}` : ""}</td></tr>)}</tbody></table></div>
          {cur?.cost && <p className="mu">{cur.cost.unit === "kWh" ? "Electricity" : "Fuel"}: {cur.cost.units} {cur.cost.unit} → {s.currency}{cur.cost.energy_cost} · per-km cost {s.currency}{cur.cost.per_km_cost} · tolls {s.currency}{cur.cost.toll} (yours) · other {s.currency}{cur.cost.other} (yours)</p>}
          <p className="mu">Order: {res.ordered_points.map((p) => p.name.split(",")[0]).join(" → ")}. Original {n1(res.original_km)} km → {n1(res.optimized_km)} km. Algorithm: {res.algorithm}. Source: {res.source}, {res.calculated_at}. No live traffic included.</p></div>}
      </div></div></>);
}

function Resources() {
  const [v, setV] = useState([]), [f, setF] = useState({ name: "", vtype: "fuel", capacity: 0, efficiency: 10, cost_per_km: 0, status: "available" }), [err, setErr] = useState("");
  const load = () => api("/resources").then(setV); useEffect(() => { load(); }, []);
  const add = async () => { try { await api("/resources", { body: { ...f, capacity: +f.capacity, efficiency: +f.efficiency, cost_per_km: +f.cost_per_km } }); setErr(""); load(); } catch (e) { setErr(e.message); } };
  const upd = async (x, ch) => { const { id, plans, ...b } = { ...x, ...ch }; try { await api("/resources/" + id, { method: "PUT", body: b }); load(); } catch (e) { setErr(e.message); } };
  const set = (k, val) => setF({ ...f, [k]: val });
  return (<><h2>Resources</h2><div className="cd"><h3>Add vehicle</h3><div className="f">
    <label>Name<input value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
    <label>Type<select value={f.vtype} onChange={(e) => set("vtype", e.target.value)}><option value="fuel">Fuel</option><option value="ev">Electric</option></select></label>
    <label>Capacity<input type="number" min="0" value={f.capacity} onChange={(e) => set("capacity", e.target.value)} /></label>
    <label>{f.vtype === "ev" ? "kWh/100 km" : "km per litre"}<input type="number" min="0.1" step="0.1" value={f.efficiency} onChange={(e) => set("efficiency", e.target.value)} /></label>
    <label>Other cost / km<input type="number" min="0" value={f.cost_per_km} onChange={(e) => set("cost_per_km", e.target.value)} /></label></div>
    <Err m={err} /><button className="b" onClick={add}>Add vehicle</button></div>
    <div className="cd w"><table><thead><tr><th>Name</th><th>Type</th><th>Capacity</th><th>Efficiency</th><th>Cost/km</th><th>Status</th><th>Assigned plans</th><th></th></tr></thead><tbody>
      {v.map((x) => <tr key={x.id}><td>{x.name}</td><td>{x.vtype}</td><td>{x.capacity}</td><td>{x.efficiency}</td><td>{x.cost_per_km}</td>
        <td><select value={x.status} onChange={(e) => upd(x, { status: e.target.value })}>{["available", "maintenance", "unavailable"].map((s) => <option key={s}>{s}</option>)}</select></td><td>{x.plans.join(", ") || "—"}</td>
        <td><button className="b s" onClick={() => { const n = prompt("Name", x.name), c = prompt("Capacity", x.capacity); if (n) upd(x, { name: n, capacity: +c >= 0 ? +c : x.capacity }); }}>Edit</button> <button className="b d" onClick={async () => { if (confirm("Delete this vehicle?")) { await api("/resources/" + x.id, { method: "DELETE" }); load(); } }}>Delete</button></td></tr>)}
      {!v.length && <tr><td colSpan="8" className="mu">No vehicles yet.</td></tr>}</tbody></table></div></>);
}

function Plans({ onEdit }) {
  const [p, setP] = useState([]), [q, setQ] = useState(""), [st, setSt] = useState(""), [err, setErr] = useState("");
  const load = () => api(`/routes?search=${encodeURIComponent(q)}&status=${st}`).then(setP).catch((e) => setErr(e.message)); useEffect(() => { load(); }, [q, st]);
  const put = async (x, ch) => { const { id, created, ...b } = { ...x, ...ch }; try { await api("/routes/" + x.id, { method: "PUT", body: b }); load(); } catch (e) { setErr(e.message); } };
  const dup = async (x) => { try { await api("/routes", { body: { name: x.name + " (copy)", objective: x.objective, depart: x.depart, demand: x.demand, distance_km: x.distance_km, duration_min: x.duration_min, cost: x.cost, data: x.data } }); load(); } catch (e) { setErr(e.message); } };
  return (<><h2>Saved plans</h2><div className="row"><input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 220 }} />
    <select value={st} onChange={(e) => setSt(e.target.value)} style={{ maxWidth: 150 }}><option value="">All</option><option>planned</option><option>completed</option><option>archived</option></select>
    <button className="b s" onClick={() => download("/reports/routes.csv", "routes.csv").catch((e) => setErr(e.message))}>Export CSV</button></div><Err m={err} />
    <div className="cd w"><table><thead><tr><th>Name</th><th>Departure</th><th>Distance</th><th>Duration</th><th>Cost</th><th>Status</th><th></th></tr></thead><tbody>
      {p.map((x) => <tr key={x.id}><td>{x.name}</td><td>{x.depart.replace("T", " ")}</td><td>{n1(x.distance_km)} km</td><td>{hm(x.duration_min)}</td><td>{x.cost ?? "—"}</td>
        <td><select value={x.status} onChange={(e) => put(x, { status: e.target.value })}>{["planned", "completed", "archived"].map((s) => <option key={s}>{s}</option>)}</select></td>
        <td><button className="b s" onClick={() => onEdit(x)}>Open/Edit</button> <button className="b s" onClick={() => dup(x)}>Duplicate</button> <button className="b d" onClick={async () => { if (confirm("Delete this plan?")) { await api("/routes/" + x.id, { method: "DELETE" }); load(); } }}>Delete</button></td></tr>)}
      {!p.length && <tr><td colSpan="7" className="mu">No plans found.</td></tr>}</tbody></table></div></>);
}

function Analytics() {
  const [o, setO] = useState(null), [fl, setFl] = useState({ status: "", objective: "", date_from: "", date_to: "" }), [err, setErr] = useState("");
  useEffect(() => { const q = new URLSearchParams(Object.entries(fl).filter(([, v]) => v)).toString(); api("/analytics/overview?" + q).then(setO).catch((e) => setErr(e.message)); }, [fl]);
  const set = (k, v) => setFl({ ...fl, [k]: v }), C = ({ t, d, k, x }) => <div className="cd"><h3>{t}</h3><ResponsiveContainer width="100%" height={220}><BarChart data={d}><XAxis dataKey={x} /><YAxis /><Tooltip /><Bar dataKey={k} fill="#0d9488" /></BarChart></ResponsiveContainer></div>;
  return (<><h2>Analytics</h2><div className="f cd"><label>Status<select value={fl.status} onChange={(e) => set("status", e.target.value)}><option value="">All</option><option>planned</option><option>completed</option><option>archived</option></select></label>
    <label>Objective<select value={fl.objective} onChange={(e) => set("objective", e.target.value)}><option value="">All</option><option>distance</option><option>time</option><option>cost</option></select></label>
    <label>From<input type="date" value={fl.date_from} onChange={(e) => set("date_from", e.target.value)} /></label><label>To<input type="date" value={fl.date_to} onChange={(e) => set("date_to", e.target.value)} /></label></div>
    <div className="row"><button className="b s" onClick={() => download("/reports/routes.csv", "routes.csv")}>Routes CSV</button><button className="b s" onClick={() => download("/reports/resources.csv", "resources.csv")}>Resources CSV</button></div><Err m={err} />
    {o && (o.plans ? <div className="g2"><C t="Distance by plan (km)" d={o.by_plan} k="distance_km" x="name" /><C t="Cost by plan" d={o.by_plan.filter((p) => p.cost != null)} k="cost" x="name" /><C t="Vehicle usage (plans)" d={o.vehicle_usage} k="plans" x="name" /><C t="Plans per month" d={o.monthly} k="plans" x="month" /></div> : <p className="mu">No saved plans match. Charts are built only from your saved data.</p>)}</>);
}

function Settings() {
  const [s, setS] = useState(null), [m, setM] = useState(""); useEffect(() => { api("/settings").then(setS); }, []);
  if (!s) return null; const set = (k, v) => setS({ ...s, [k]: v });
  const save = async () => { try { setS(await api("/settings", { method: "PUT", body: { ...s, fuel_price: +s.fuel_price, tariff: +s.tariff, dwell_min: +s.dwell_min } })); setM("Saved ✓"); } catch (e) { setM(e.message); } };
  return (<><h2>Settings</h2><div className="cd"><div className="f">
    <label>Currency<input value={s.currency} onChange={(e) => set("currency", e.target.value)} /></label><label>Fuel price / litre<input type="number" min="0" value={s.fuel_price} onChange={(e) => set("fuel_price", e.target.value)} /></label>
    <label>Electricity tariff / kWh<input type="number" min="0" value={s.tariff} onChange={(e) => set("tariff", e.target.value)} /></label><label>Minutes per stop<input type="number" min="0" value={s.dwell_min} onChange={(e) => set("dwell_min", e.target.value)} /></label>
    <label>Default objective<select value={s.objective} onChange={(e) => set("objective", e.target.value)}><option value="distance">distance</option><option value="time">time</option><option value="cost">cost</option></select></label></div>
    <div className="row"><button className="b" onClick={save}>Save settings</button><span className={m.endsWith("✓") ? "ok" : "er"}>{m}</span></div></div></>);
}
