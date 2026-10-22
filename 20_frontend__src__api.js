const B = import.meta.env.VITE_API_URL || "";
export async function api(path, opt = {}) {
  const { body, method = body ? "POST" : "GET" } = opt;
  const r = await fetch(B + "/api" + path, { method, credentials: "include", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    let m = r.statusText;
    try { const j = await r.json(); m = typeof j.detail === "string" ? j.detail : "Please check the form values."; } catch {}
    throw new Error(m);
  }
  if (r.status === 204) return null;
  return (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}
export async function download(path, name) {
  const r = await fetch(B + "/api" + path, { credentials: "include" });
  if (!r.ok) throw new Error("Export failed");
  const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = name; a.click();
}
