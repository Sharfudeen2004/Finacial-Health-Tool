import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar,
} from "recharts";

const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const api = axios.create({ baseURL: API });

/* ---------------- UI helpers ---------------- */
function Card({ title, right, children }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 16,
        padding: 16,
        boxShadow: "0 2px 10px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 10,
        }}
      >
        <div style={{ fontWeight: 800, color: "#111827" }}>{title}</div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Button({ children, onClick, disabled, variant = "primary", type = "button" }) {
  const base = {
    padding: "10px 12px",
    borderRadius: 12,
    border: "1px solid transparent",
    fontWeight: 700,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.6 : 1,
    transition: "all 120ms ease",
  };

  const styles =
    variant === "primary"
      ? { background: "#111827", color: "white", borderColor: "#111827" }
      : variant === "ghost"
        ? { background: "white", color: "#111827", borderColor: "#e5e7eb" }
        : { background: "#2563eb", color: "white", borderColor: "#2563eb" };

  return (
    <button type={type} onClick={onClick} disabled={disabled} style={{ ...base, ...styles }}>
      {children}
    </button>
  );
}

function Pill({ text, tone = "green" }) {
  const map = {
    green: { bg: "#dcfce7", fg: "#166534" },
    yellow: { bg: "#fef9c3", fg: "#854d0e" },
    red: { bg: "#fee2e2", fg: "#991b1b" },
    gray: { bg: "#f3f4f6", fg: "#111827" },
    blue: { bg: "#dbeafe", fg: "#1e40af" },
  };
  const t = map[tone] || map.gray;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "4px 10px",
        borderRadius: 999,
        background: t.bg,
        color: t.fg,
        fontSize: 12,
        fontWeight: 800,
      }}
    >
      {text}
    </span>
  );
}

function Input({ value, onChange, placeholder, type = "text" }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      type={type}
      style={{
        width: "100%",
        padding: "10px 12px",
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        outline: "none",
      }}
    />
  );
}

function currencyINR(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/* ---------------- App ---------------- */
export default function App() {
  // AUTH
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [authMode, setAuthMode] = useState("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // BUSINESS
  const [businesses, setBusinesses] = useState([]);
  const [businessId, setBusinessId] = useState(null);

  // DATA
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const [kpis, setKpis] = useState(null);
  const [score, setScore] = useState(null);
  const [monthly, setMonthly] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [risks, setRisks] = useState([]);
  const [recs, setRecs] = useState([]);
  const [aiSummary, setAiSummary] = useState("");
  const [gstSummary, setGstSummary] = useState([]);

  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  // attach auth header
  useEffect(() => {
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      fetchBusinesses();
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function fetchBusinesses() {
    try {
      const res = await api.get("/auth/businesses");
      setBusinesses(res.data || []);
      if (!businessId && res.data?.length) setBusinessId(res.data[0].id);
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
      if (e?.response?.status === 401) logout();
    }
  }

  useEffect(() => {
    if (businessId) fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId]);

  async function fetchAll() {
    setLoading(true);
    setMsg("");
    try {
      const [k, s, m, f, r, rc, ai, gst] = await Promise.all([
        api.get("/kpis", { params: { business_id: businessId } }),
        api.get("/score", { params: { business_id: businessId } }),
        api.get("/kpis/monthly", { params: { business_id: businessId } }),
        api.get("/forecast", { params: { business_id: businessId, months: 3 } }),
        api.get("/risks", { params: { business_id: businessId } }),
        api.get("/recommendations", { params: { business_id: businessId } }),
        api.get("/ai/summary", { params: { business_id: businessId } }),
        api.get("/gst/summary", { params: { business_id: businessId } }),
      ]);

      setKpis(k.data);
      setScore(s.data);
      setMonthly(m.data || []);
      setForecast(f.data?.forecast || []);
      setRisks(r.data || []);
      setRecs(rc.data || []);
      setAiSummary(ai.data?.summary || "");
      setGstSummary(gst.data || []);
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
      if (e?.response?.status === 401) logout();
    } finally {
      setLoading(false);
    }
  }

  // AUTH actions
  async function doLogin(e) {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      const res = await api.post("/auth/login", { email, password });
      localStorage.setItem("token", res.data.access_token);
      setToken(res.data.access_token);
      setEmail("");
      setPassword("");
    } catch (e2) {
      setMsg(e2?.response?.data?.detail || e2.message);
    } finally {
      setLoading(false);
    }
  }

  async function doRegister(e) {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      const res = await api.post("/auth/register", {
        full_name: fullName,
        email,
        password,
      });
      localStorage.setItem("token", res.data.access_token);
      setToken(res.data.access_token);
      setFullName("");
      setEmail("");
      setPassword("");
    } catch (e2) {
      setMsg(e2?.response?.data?.detail || e2.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setToken("");
    setBusinesses([]);
    setBusinessId(null);
  }

  async function createBusiness() {
    const name = prompt("Business name?");
    if (!name) return;
    setLoading(true);
    setMsg("");
    try {
      await api.post("/auth/businesses", { name });
      await fetchBusinesses();
      await fetchAll();
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  // Upload preview/commit (supports PDF endpoints too)
  async function handlePreview() {
    if (!file) return;
    setLoading(true);
    setMsg("");
    try {
      const form = new FormData();
      form.append("file", file);
      const isPdf = file.name.toLowerCase().endsWith(".pdf");
      const url = isPdf ? "/upload/pdf/preview" : "/upload/preview";
      const res = await api.post(url, form, {
        params: { business_id: businessId },
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPreview(res.data);
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCommit() {
    if (!file) return;
    setLoading(true);
    setMsg("");
    try {
      const form = new FormData();
      form.append("file", file);
      const isPdf = file.name.toLowerCase().endsWith(".pdf");
      const url = isPdf ? "/upload/pdf/commit" : "/upload/commit";
      const res = await api.post(url, form, {
        params: { business_id: businessId },
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMsg(`Inserted ${res.data.inserted} rows ✅`);
      setFile(null);
      setPreview(null);
      await fetchAll();
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  async function bankSync() {
    setLoading(true);
    setMsg("");
    try {
      const res = await api.post("/bank/sync", null, {
        params: { business_id: businessId },
      });
      setMsg(`Bank synced ${res.data.synced} txns ✅`);
      await fetchAll();
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  const ratingTone = useMemo(() => {
    const r = (score?.rating || "").toLowerCase();
    if (r.includes("excellent")) return "green";
    if (r.includes("good")) return "blue";
    if (r.includes("average")) return "yellow";
    if (r.includes("poor")) return "red";
    return "gray";
  }, [score]);

  const chartData = useMemo(() => {
    // combine monthly + forecast by month key
    const map = new Map();
    (monthly || []).forEach((x) => map.set(x.month, { ...x }));
    (forecast || []).forEach((x) => {
      const prev = map.get(x.month) || { month: x.month };
      map.set(x.month, { ...prev, ...x });
    });
    return Array.from(map.values()).sort((a, b) => (a.month > b.month ? 1 : -1));
  }, [monthly, forecast]);

  // ---------- LOGIN UI ----------
  if (!token) {
    return (
      <div style={{ minHeight: "100vh", background: "#f9fafb" }}>
        <div style={{ maxWidth: 980, margin: "0 auto", padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 900, color: "#111827" }}>SME Financial Health</div>
              <div style={{ color: "#6b7280", marginTop: 6 }}>
                Backend: <code>{API}</code>
              </div>
            </div>
            <Pill text="MVP Dashboard" tone="blue" />
          </div>

          {msg && (
            <div style={{ marginTop: 14, padding: 12, borderRadius: 12, background: "#fff7ed", border: "1px solid #fed7aa", color: "#9a3412" }}>
              {msg}
            </div>
          )}

          <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Card
              title={authMode === "login" ? "Login" : "Register"}
              right={
                <div style={{ display: "flex", gap: 8 }}>
                  <Button variant={authMode === "login" ? "primary" : "ghost"} onClick={() => setAuthMode("login")}>
                    Login
                  </Button>
                  <Button variant={authMode === "register" ? "primary" : "ghost"} onClick={() => setAuthMode("register")}>
                    Register
                  </Button>
                </div>
              }
            >
              <form onSubmit={authMode === "login" ? doLogin : doRegister}>
                {authMode === "register" && (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#6b7280", marginBottom: 6 }}>Full name</div>
                    <Input value={fullName} onChange={setFullName} placeholder="Your name" />
                  </div>
                )}

                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#6b7280", marginBottom: 6 }}>Email</div>
                  <Input value={email} onChange={setEmail} placeholder="you@gmail.com" />
                </div>

                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#6b7280", marginBottom: 6 }}>Password</div>
                  <Input value={password} onChange={setPassword} placeholder="••••••••" type="password" />
                </div>

                <Button
                  type="submit"
                  disabled={
                    loading ||
                    !email ||
                    !password ||
                    (authMode === "register" && !fullName)
                  }
                >
                  {loading ? "Please wait..." : authMode === "login" ? "Login" : "Create account"}
                </Button>
              </form>

              <div style={{ marginTop: 10, fontSize: 12, color: "#6b7280" }}>
                Register creates a default business automatically (from backend).
              </div>
            </Card>

            <Card title="What you can do">
              <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, color: "#374151" }}>
                <li>Upload CSV/XLSX or PDF (text PDF) to add transactions</li>
                <li>Auto bank sync (demo) to add transactions</li>
                <li>KPIs, score, risks, recommendations, forecast</li>
                <li>GST monthly summary chart/table</li>
              </ul>
              <div style={{ marginTop: 10, fontSize: 12, color: "#6b7280" }}>
                Tip: If you see CORS issues, ensure backend allow_origins includes <code>http://localhost:5173</code>.
              </div>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  // ---------- DASHBOARD UI ----------
  return (
    <div style={{ minHeight: "100vh", background: "#f9fafb" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: 20 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 26, fontWeight: 900, color: "#111827" }}>Dashboard</div>
            <div style={{ marginTop: 4, color: "#6b7280" }}>
              Backend: <code>{API}</code>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Button variant="ghost" onClick={fetchAll} disabled={loading}>
              Refresh
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.open(`${API}/reports/pdf?business_id=${businessId}`, "_blank")}
            >
              Export PDF
            </Button>

            <Button variant="ghost" onClick={logout}>
              Logout
            </Button>

          </div>
        </div>

        {msg && (
          <div style={{ marginTop: 14, padding: 12, borderRadius: 12, background: "#fff7ed", border: "1px solid #fed7aa", color: "#9a3412" }}>
            {msg}
          </div>
        )}

        {/* Business + Upload */}
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 14 }}>
          <Card title="Business">
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <select
                value={businessId || ""}
                onChange={(e) => setBusinessId(Number(e.target.value))}
                style={{
                  padding: "10px 12px",
                  borderRadius: 12,
                  border: "1px solid #e5e7eb",
                  minWidth: 260,
                  background: "white",
                  fontWeight: 700,
                }}
              >
                {businesses.map((b) => (
                  <option key={b.id} value={b.id}>
                    #{b.id} — {b.name}
                  </option>
                ))}
              </select>

              <Button variant="ghost" onClick={createBusiness} disabled={loading}>
                + New Business
              </Button>

              {score?.rating && (
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <Pill text={`Score: ${score.health_score ?? "-"}`} tone={ratingTone} />
                  <Pill text={score.rating} tone={ratingTone} />
                </div>
              )}
            </div>

            <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <input
                type="file"
                accept=".csv,.xlsx,.xls,.pdf"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setPreview(null);
                }}
              />
              <Button variant="ghost" onClick={handlePreview} disabled={!file || loading}>
                Preview
              </Button>
              <Button onClick={handleCommit} disabled={!file || loading}>
                Commit
              </Button>
              <Button variant="ghost" onClick={bankSync} disabled={loading}>
                Bank Sync
              </Button>
            </div>

            {preview && (
              <div style={{ marginTop: 12, overflow: "auto", maxHeight: 240, border: "1px solid #f3f4f6", borderRadius: 12 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      {preview.columns.map((c) => (
                        <th key={c} style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #e5e7eb", background: "#fafafa" }}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row, idx) => (
                      <tr key={idx}>
                        {preview.columns.map((c) => (
                          <td key={c} style={{ padding: 10, borderBottom: "1px solid #f3f4f6" }}>
                            {String(row[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="AI Summary" right={<Pill text={loading ? "Loading..." : "Live"} tone={loading ? "yellow" : "green"} />}>
            <div style={{ color: "#111827", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {aiSummary || "No summary yet. Upload transactions first."}
            </div>
          </Card>
        </div>

        {/* KPI Cards */}
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
          <Card title="Total Revenue">
            <div style={{ fontSize: 26, fontWeight: 900 }}>{currencyINR(kpis?.total_revenue)}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>Category: revenue (credit)</div>
          </Card>

          <Card title="Total Expenses">
            <div style={{ fontSize: 26, fontWeight: 900 }}>{currencyINR(kpis?.total_expenses)}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>
              Expense ratio: {kpis?.expense_ratio != null ? `${Number(kpis.expense_ratio).toFixed(2)}%` : "-"}
            </div>
          </Card>

          <Card title="Net Cashflow">
            <div style={{ fontSize: 26, fontWeight: 900 }}>{currencyINR(kpis?.net_cashflow)}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>
              In: {currencyINR(kpis?.total_inflow)} • Out: {currencyINR(kpis?.total_outflow)}
            </div>
          </Card>

          <Card title="Transactions">
            <div style={{ fontSize: 26, fontWeight: 900 }}>{kpis?.total_transactions ?? "-"}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>Latest 500 tracked</div>
          </Card>
        </div>

        {/* Charts row */}
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <Card title="Monthly Trend (Actual + Forecast)">
            {!chartData.length ? (
              <div style={{ color: "#6b7280" }}>No data yet.</div>
            ) : (
              <div style={{ width: "100%", height: 340 }}>
                <ResponsiveContainer>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="revenue" name="Revenue (actual)" />
                    <Line type="monotone" dataKey="expenses" name="Expenses (actual)" />
                    <Line type="monotone" dataKey="profit_simple" name="Profit (actual)" />
                    <Line type="monotone" dataKey="forecast_revenue" name="Revenue (forecast)" strokeDasharray="6 4" />
                    <Line type="monotone" dataKey="forecast_net_cashflow" name="Profit (forecast)" strokeDasharray="6 4" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <Card title="GST Monthly Summary">
            {!gstSummary?.length ? (
              <div style={{ color: "#6b7280" }}>No GST summary yet. Import GST JSON first.</div>
            ) : (
              <>
                <div style={{ width: "100%", height: 220 }}>
                  <ResponsiveContainer>
                    <BarChart data={gstSummary}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="gst_sales" name="GST Sales" />
                      <Bar dataKey="gst_purchases" name="GST Purchases" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ marginTop: 10, overflow: "auto", maxHeight: 120, borderRadius: 12, border: "1px solid #f3f4f6" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #e5e7eb", background: "#fafafa" }}>Month</th>
                        <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #e5e7eb", background: "#fafafa" }}>Sales</th>
                        <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #e5e7eb", background: "#fafafa" }}>Purchases</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gstSummary.map((x, i) => (
                        <tr key={i}>
                          <td style={{ padding: 10, borderBottom: "1px solid #f3f4f6" }}>{x.month}</td>
                          <td style={{ padding: 10, borderBottom: "1px solid #f3f4f6" }}>{currencyINR(x.gst_sales)}</td>
                          <td style={{ padding: 10, borderBottom: "1px solid #f3f4f6" }}>{currencyINR(x.gst_purchases)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>
        </div>

        {/* Risks + Recommendations */}
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <Card title="Risks" right={<Pill text={`${risks?.length || 0} items`} tone="yellow" />}>
            {!risks?.length ? (
              <div style={{ color: "#6b7280" }}>No risks.</div>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                {risks.map((r, i) => (
                  <li key={i}>{typeof r === "string" ? r : `${r.type}: ${r.message}`}</li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Recommendations" right={<Pill text={`${recs?.length || 0} items`} tone="green" />}>
            {!recs?.length ? (
              <div style={{ color: "#6b7280" }}>No recommendations.</div>
            ) : (
              <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                {recs.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ol>
            )}
          </Card>
        </div>

        <div style={{ marginTop: 16, color: "#6b7280", fontSize: 12 }}>
          Next: Invoice OCR UI, Audit Logs table, RBAC roles, real bank API integration.
        </div>
      </div>
    </div>
  );
}
