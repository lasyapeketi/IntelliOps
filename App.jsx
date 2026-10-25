import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend
} from "recharts";

const API = "http://127.0.0.1:8000";
const COLORS = ["#16a34a", "#f59e0b", "#ef4444"];

function Metric({ label, value, note, icon }) {
  return <div className="metric card">
    <div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div>
    <div className="metric-value">{value}</div>
    <div className="metric-note">{note}</div>
  </div>;
}

function App() {
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState(null);
  const [filter, setFilter] = useState("All");

  async function refresh() {
    try {
      const h = await fetch(`${API}/api/health`).then(r => r.json());
      setHealth(h);
      if (h.model_ready) {
        const s = await fetch(`${API}/api/summary`);
        if (s.ok) setSummary(await s.json());
      }
    } catch {
      setError("Backend is not reachable. Start FastAPI at http://127.0.0.1:8000.");
    }
  }
  useEffect(() => { refresh(); }, []);

  async function uploadFile(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setError(""); setBatch(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API}/api/predict-batch`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Prediction failed.");
      setBatch(body);
    } catch (err) {
      setError(err.message || "Could not process the CSV.");
    } finally { setBusy(false); }
  }

  function downloadCsv() {
    if (!batch?.csv) return;
    const url = URL.createObjectURL(new Blob([batch.csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url; a.download = "employee_attrition_predictions.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  const pieData = useMemo(() => batch ? [
    { name: "Low risk", value: batch.low_risk },
    { name: "Medium risk", value: batch.medium_risk },
    { name: "High risk", value: batch.high_risk }
  ] : [], [batch]);

  const shownRows = useMemo(() => {
    if (!batch) return [];
    return batch.results.filter(r => filter === "All" || r.risk_level === filter);
  }, [batch, filter]);

  const features = summary?.feature_importance || [];
  const cm = summary?.confusion_matrix || [[0,0],[0,0]];

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">P</div><div><b>PeoplePulse</b><small>PEOPLE ANALYTICS</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <div className="nav-item active"><span>▦</span> Overview</div>
      <div className="nav-item"><span>◉</span> Attrition prediction</div>
      <div className="nav-item"><span>▤</span> Reports</div>
      <div className="sidebar-bottom"><div className="status-dot" /> Local prototype <small>v1.0</small></div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div><div className="eyebrow">WORKSPACE / OVERVIEW</div><h1>Attrition Intelligence</h1><p>Understand workforce patterns and explore employee retention risk.</p></div>
        <button className="secondary-btn" onClick={refresh}>↻ Refresh</button>
      </header>

      {error && <div className="alert error">{error}<button onClick={() => setError("")}>×</button></div>}
      {!health?.model_ready && <div className="alert warning"><b>Model not ready.</b> Download the public dataset, place it in <code>backend/data/</code>, then run <code>python train_model.py</code>.</div>}

      <section className="metrics-grid">
        <Metric label="Employees in training data" value={summary?.dataset_rows?.toLocaleString() ?? "—"} note="Public sample dataset" icon="♙"/>
        <Metric label="Historical attrition" value={summary ? `${summary.historical_attrition_rate}%` : "—"} note="Observed labels in sample" icon="↗"/>
        <Metric label="Model F1 score" value={summary ? (summary.f1 * 100).toFixed(1) + "%" : "—"} note="Held-out test set" icon="◎"/>
        <Metric label="ROC-AUC" value={summary?.roc_auc != null ? summary.roc_auc.toFixed(3) : "—"} note="Held-out test set" icon="⌁"/>
      </section>

      <section className="content-grid">
        <div className="card panel">
          <div className="section-heading"><div><h2>Run a batch prediction</h2><p>Upload a CSV with the same feature columns as the training dataset.</p></div><span className="pill">CSV · max 10 MB</span></div>
          <form className="upload-box" onSubmit={uploadFile}>
            <div className="upload-icon">↑</div>
            <b>Upload employee data</b>
            <p>Choose your CSV file. The original dataset is accepted; its Attrition column is ignored during prediction.</p>
            <label className="file-btn">Choose CSV<input type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] || null)}/></label>
            <div className="file-name">{file ? file.name : "No file selected"}</div>
            <button className="primary-btn" type="submit" disabled={!file || busy || !health?.model_ready}>{busy ? "Predicting…" : "Run prediction →"}</button>
          </form>
          <div className="privacy-note">🔒 Prototype note: uploads are processed by your local backend. Do not upload real employee data until access controls, security, and retention policies are implemented.</div>
        </div>

        <div className="card panel">
          <div className="section-heading"><div><h2>Risk distribution</h2><p>Predictions for the latest uploaded file</p></div></div>
          {batch ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={230}>
            <PieChart><Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="46%" innerRadius={58} outerRadius={83} paddingAngle={3}>
              {pieData.map((entry, i) => <Cell key={entry.name} fill={COLORS[i]}/>)}
            </Pie><Tooltip/><Legend verticalAlign="bottom" /></PieChart>
          </ResponsiveContainer></div> : <div className="empty-chart"><div className="empty-chart-icon">◔</div><b>No predictions yet</b><span>Upload a CSV to see the risk distribution.</span></div>}
        </div>
      </section>

      <section className="card panel results-panel">
        <div className="section-heading results-heading"><div><h2>Prediction results</h2><p>{batch ? `${batch.count} employees analyzed · estimates only` : "Your batch prediction results will appear here."}</p></div>
          {batch && <button className="secondary-btn" onClick={downloadCsv}>↓ Export CSV</button>}
        </div>
        {batch && <div className="result-summary">
          <div><span className="dot green"/>Low risk <b>{batch.low_risk}</b></div>
          <div><span className="dot amber"/>Medium risk <b>{batch.medium_risk}</b></div>
          <div><span className="dot red"/>High risk <b>{batch.high_risk}</b></div>
        </div>}
        {batch ? <>
          <div className="table-tools"><span>Showing {shownRows.length} rows</span><select value={filter} onChange={e => setFilter(e.target.value)}><option>All</option><option>Low</option><option>Medium</option><option>High</option></select></div>
          <div className="table-scroll"><table><thead><tr><th>CSV row</th><th>Risk score</th><th>Risk level</th><th>Model estimate</th></tr></thead>
            <tbody>{shownRows.slice(0, 100).map(r => <tr key={r.row}><td>Row {r.row}</td><td><div className="score-cell"><div className="score-track"><div className={`score-fill ${r.risk_level.toLowerCase()}`} style={{width: `${r.risk_score}%`}}/></div><b>{r.risk_score.toFixed(1)}%</b></div></td><td><span className={`risk-badge ${r.risk_level.toLowerCase()}`}>{r.risk_level}</span></td><td>{r.predicted_attrition ? "Elevated risk" : "Below threshold"}</td></tr>)}</tbody>
          </table></div>
          {shownRows.length > 100 && <p className="table-footnote">Showing first 100 rows. Export CSV for the complete result set.</p>}
        </> : <div className="table-empty">Prediction table is waiting for your first CSV upload.</div>}
      </section>

      <section className="content-grid lower-grid">
        <div className="card panel">
          <div className="section-heading"><div><h2>Model evaluation</h2><p>Held-out test data · threshold {summary ? summary.threshold : "—"}</p></div></div>
          {summary ? <div className="evaluation">
            {[["Accuracy", summary.accuracy], ["Precision", summary.precision], ["Recall", summary.recall], ["F1 score", summary.f1]].map(([label, value]) => <div className="eval-row" key={label}><span>{label}</span><div className="eval-track"><div style={{width: `${value * 100}%`}}/></div><b>{(value * 100).toFixed(1)}%</b></div>)}
            <div className="cm"><b>Confusion matrix</b><span>Actual No / Actual Yes × predicted No / predicted Yes</span><div className="cm-grid"><span>TN<br/><b>{cm[0]?.[0] ?? 0}</b></span><span>FP<br/><b>{cm[0]?.[1] ?? 0}</b></span><span>FN<br/><b>{cm[1]?.[0] ?? 0}</b></span><span>TP<br/><b>{cm[1]?.[1] ?? 0}</b></span></div></div>
          </div> : <div className="table-empty">Train the model to display evaluation metrics.</div>}
        </div>
        <div className="card panel">
          <div className="section-heading"><div><h2>Model notes</h2><p>How to interpret this prototype</p></div></div>
          <div className="note-list">
            <div><span className="note-number">01</span><p><b>Risk is not certainty</b><br/>A probability is an estimate, not proof someone plans to leave.</p></div>
            <div><span className="note-number">02</span><p><b>Use supportive interventions</b><br/>Discuss workload, growth, and employee experience with care.</p></div>
            <div><span className="note-number">03</span><p><b>Validate before deployment</b><br/>Check recall, calibration, fairness, and drift on relevant data.</p></div>
          </div>
          <div className="dataset-foot">DATA SOURCE <a href="https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset" target="_blank" rel="noreferrer">IBM HR Analytics dataset ↗</a></div>
        </div>
      </section>
      <footer>PeoplePulse · Educational prototype · Not for automated employment decisions</footer>
    </main>
  </div>;
}

export default App;
