/**
 * IntelliOps — Sales & Revenue Forecasting
 * Frontend Application Logic
 *
 * Connects to the FastAPI backend at /api/v1/predict/sales_revenue_forecasting
 */

// ── Constants ──────────────────────────────────────────────────
const API_ENDPOINT = '/api/v1/predict/sales_revenue_forecasting';
const HEALTH_ENDPOINT = '/health';
const USE_CASE = 'sales_revenue_forecasting';

// ── State ──────────────────────────────────────────────────────
let forecastChartInstance = null;
let miniChartInstance = null;

// ── DOM Helpers ────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ── API Health Check ───────────────────────────────────────────
async function checkApiHealth() {
  const statusEl = $('apiStatus');
  try {
    const res = await fetch(HEALTH_ENDPOINT, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      statusEl.className = 'api-status online';
      statusEl.querySelector('.status-text').textContent = 'API Online';
    } else {
      throw new Error('not ok');
    }
  } catch {
    statusEl.className = 'api-status offline';
    statusEl.querySelector('.status-text').textContent = 'API Offline';
  }
}

// ── Historical Sales: Parse & Count ────────────────────────────
function parseSalesArray(raw) {
  return raw
    .split(',')
    .map((v) => parseFloat(v.trim()))
    .filter((v) => !isNaN(v) && v >= 0);
}

function updateSalesCount() {
  const raw = $('historicalSales').value;
  const arr = parseSalesArray(raw);
  const countEl = $('salesCount');
  countEl.textContent = arr.length === 1 ? '1 value' : `${arr.length} values`;
  countEl.style.color = arr.length < 3 ? '#ef4444' : '#06b6d4';
  renderMiniChart(arr);
}

// ── Mini Historical Chart (Input Preview) ─────────────────────
function renderMiniChart(data) {
  const ctx = $('historicalMiniChart').getContext('2d');

  if (miniChartInstance) {
    miniChartInstance.destroy();
    miniChartInstance = null;
  }

  if (data.length === 0) return;

  const labels = data.map((_, i) => `M${i + 1}`);

  miniChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          data,
          borderColor: '#06b6d4',
          borderWidth: 1.5,
          pointRadius: 2,
          pointBackgroundColor: '#06b6d4',
          fill: true,
          backgroundColor: (ctx) => {
            const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 70);
            g.addColorStop(0, 'rgba(6,182,212,0.2)');
            g.addColorStop(1, 'rgba(6,182,212,0)');
            return g;
          },
          tension: 0.4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    },
  });
}

// ── Load Sample Data ───────────────────────────────────────────
function loadSampleData() {
  $('historicalSales').value = '14200, 15100, 14800, 16200, 17500, 18300, 19100';
  $('forecastHorizon').value = 4;
  $('marketingBudget').value = 4500;
  $('seasonalityFactor').value = 1.15;
  $('discountRate').value = 4.0;
  $('includeExplanation').checked = true;

  updateSalesCount();

  // Update pill active states
  document.querySelectorAll('.pill').forEach((p) => p.classList.remove('active'));
}

// ── Seasonality Pill Setter ────────────────────────────────────
function setSeasonality(value) {
  $('seasonalityFactor').value = value;
  document.querySelectorAll('.pill').forEach((p) => {
    const v = parseFloat(p.getAttribute('onclick').match(/[\d.]+/)[0]);
    p.classList.toggle('active', v === value);
  });
}

// ── Main Forecast Handler ──────────────────────────────────────
async function handleForecast(e) {
  e.preventDefault();

  const errBox = $('errorBox');
  const btn = $('btnSubmit');
  const spinner = $('btnSpinner');

  // Reset UI
  errBox.style.display = 'none';
  btn.classList.add('loading');
  btn.disabled = true;

  // Parse & validate historical sales
  const rawSales = $('historicalSales').value;
  const salesArray = parseSalesArray(rawSales);

  if (salesArray.length < 3) {
    showError('Please provide at least 3 valid historical sales values separated by commas.');
    resetBtn(btn);
    return;
  }

  // Build request payload
  const payload = {
    use_case: USE_CASE,
    request_id: `req-${Date.now()}`,
    input: {
      historical_sales: salesArray,
      forecast_horizon_months: parseInt($('forecastHorizon').value, 10) || 3,
      marketing_budget: parseFloat($('marketingBudget').value) || 0,
      seasonality_factor: parseFloat($('seasonalityFactor').value) || 1.0,
      discount_rate_pct: parseFloat($('discountRate').value) || 0,
    },
    options: {
      include_explanation: $('includeExplanation').checked,
    },
  };

  try {
    const res = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      const msg =
        data.errors && data.errors.length > 0
          ? data.errors[0].message
          : `Request failed (HTTP ${res.status})`;
      throw new Error(msg);
    }

    renderResults(data, salesArray);
  } catch (err) {
    showError(err.message || 'An unexpected error occurred. Is the backend running?');
  } finally {
    resetBtn(btn);
  }
}

function showError(message) {
  const errBox = $('errorBox');
  errBox.textContent = message;
  errBox.style.display = 'block';
}

function resetBtn(btn) {
  btn.classList.remove('loading');
  btn.disabled = false;
}

// ── Render All Results ─────────────────────────────────────────
function renderResults(data, historicalSales) {
  const pred = data.prediction;
  const exp = data.explanation;
  const model = data.model;

  // Show results panel
  $('emptyState').style.display = 'none';
  $('resultsContent').style.display = 'block';

  renderKPIs(pred);
  renderForecastChart(pred, historicalSales);
  renderBreakdownTable(pred);
  renderModelMeta(model, pred);
  renderExplanation(exp);
  renderRawJson(data);
}

// ── KPI Cards ─────────────────────────────────────────────────
function renderKPIs(pred) {
  const growth = pred.projected_growth_rate_pct;
  const isPositive = growth >= 0;
  const slope = pred.trend_slope_per_period;

  const kpis = [
    {
      label: 'Total Forecasted Revenue',
      value: formatCurrency(pred.total_forecasted_revenue),
      sub: `${isPositive ? '▲ +' : '▼ '}${growth}% vs recent history`,
      subClass: isPositive ? 'positive' : 'negative',
    },
    {
      label: 'Monthly Trend Slope',
      value: `${slope >= 0 ? '+' : ''}${formatCurrency(slope, 0)}`,
      sub: 'per period (OLS linear trend)',
      subClass: '',
    },
    {
      label: 'In-Sample MAE',
      value: formatCurrency(pred.metrics.in_sample_mae, 0),
      sub: `RMSE: ${formatCurrency(pred.metrics.in_sample_rmse, 0)}`,
      subClass: '',
    },
    {
      label: 'Observations',
      value: pred.metrics.observations_count,
      sub: `${pred.forecast_breakdown.length} period${pred.forecast_breakdown.length > 1 ? 's' : ''} forecasted`,
      subClass: '',
    },
  ];

  $('kpiRow').innerHTML = kpis
    .map(
      (k) => `
    <div class="kpi-card">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
      <div class="kpi-sub ${k.subClass}">${k.sub}</div>
    </div>
  `
    )
    .join('');
}

// ── Forecast Chart ─────────────────────────────────────────────
function renderForecastChart(pred, historicalSales) {
  if (forecastChartInstance) {
    forecastChartInstance.destroy();
    forecastChartInstance = null;
  }

  const breakdown = pred.forecast_breakdown;
  const histLabels = historicalSales.map((_, i) => `Hist M${i + 1}`);
  const forecastLabels = breakdown.map((b) => b.period);
  const allLabels = [...histLabels, ...forecastLabels];

  // Historical padded with nulls for forecast slots
  const histData = [
    ...historicalSales,
    ...new Array(forecastLabels.length).fill(null),
  ];

  // Forecast padded with nulls for hist slots
  const histPad = new Array(historicalSales.length).fill(null);
  const forecastData  = [...histPad, ...breakdown.map((b) => b.forecasted_revenue)];
  const upperBound    = [...histPad, ...breakdown.map((b) => b.upper_bound)];
  const lowerBound    = [...histPad, ...breakdown.map((b) => b.lower_bound)];

  // Connect last historical point to first forecast point
  if (historicalSales.length > 0 && forecastData[historicalSales.length] != null) {
    forecastData[historicalSales.length - 1] = historicalSales[historicalSales.length - 1];
    upperBound[historicalSales.length - 1]   = historicalSales[historicalSales.length - 1];
    lowerBound[historicalSales.length - 1]   = historicalSales[historicalSales.length - 1];
  }

  const ctx = $('forecastChart').getContext('2d');

  forecastChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        // Upper Bound (invisible, for fill reference)
        {
          label: 'Upper 95%',
          data: upperBound,
          borderColor: 'transparent',
          pointRadius: 0,
          fill: false,
          tension: 0.4,
        },
        // Lower Bound filled up to upper
        {
          label: '95% Interval',
          data: lowerBound,
          borderColor: 'transparent',
          pointRadius: 0,
          fill: '-1',
          backgroundColor: 'rgba(99,102,241,0.12)',
          tension: 0.4,
        },
        // Forecasted line
        {
          label: 'Forecasted Revenue',
          data: forecastData,
          borderColor: '#6366f1',
          borderWidth: 2.5,
          pointBackgroundColor: '#6366f1',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: (ctx) => {
            const i = ctx.dataIndex;
            return i >= historicalSales.length ? 5 : 0;
          },
          fill: false,
          tension: 0.4,
        },
        // Historical line
        {
          label: 'Historical Sales',
          data: histData,
          borderColor: '#06b6d4',
          borderWidth: 2,
          borderDash: [],
          pointBackgroundColor: '#06b6d4',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: (ctx) => (ctx.dataIndex < historicalSales.length ? 4 : 0),
          fill: false,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0d1521',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#8899b4',
          padding: 12,
          callbacks: {
            label: (ctx) => {
              if (ctx.parsed.y == null) return null;
              return ` ${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#4f6280', font: { size: 11 } },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#4f6280',
            font: { size: 11 },
            callback: (v) => `$${(v / 1000).toFixed(0)}k`,
          },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
      },
    },
  });
}

// ── Breakdown Table ────────────────────────────────────────────
function renderBreakdownTable(pred) {
  const breakdown = pred.forecast_breakdown;

  $('breakdownTag').textContent = `${breakdown.length} period${breakdown.length > 1 ? 's' : ''}`;

  $('breakdownBody').innerHTML = breakdown
    .map(
      (item) => `
    <tr>
      <td class="td-period">${item.period}</td>
      <td class="td-forecasted">${formatCurrency(item.forecasted_revenue)}</td>
      <td class="td-base">${formatCurrency(item.base_revenue)}</td>
      <td class="td-interval">[${formatCurrency(item.lower_bound, 0)} – ${formatCurrency(item.upper_bound, 0)}]</td>
    </tr>
  `
    )
    .join('');
}

// ── Model Metadata ─────────────────────────────────────────────
function renderModelMeta(model, pred) {
  if (!model) {
    $('metaCard').innerHTML = '';
    return;
  }

  $('metaCard').innerHTML = `
    <div class="meta-card-title">Model Info</div>
    <div class="meta-row">
      <div class="meta-item">
        <span class="meta-item-key">Name</span>
        <span class="meta-item-val">${model.name}</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-key">Version</span>
        <span class="meta-item-val">${model.version}</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-key">Methodology</span>
        <span class="meta-item-val">${model.methodology}</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-key">In-sample RMSE</span>
        <span class="meta-item-val">${formatCurrency(pred.metrics.in_sample_rmse)}</span>
      </div>
    </div>
  `;
}

// ── AI Explanation ─────────────────────────────────────────────
function renderExplanation(exp) {
  const card = $('explanationCard');

  if (!exp) {
    card.style.display = 'none';
    return;
  }

  const factorsHtml = (exp.key_factors || [])
    .map(
      (f) => `
    <div class="factor-item">
      <div class="factor-name">${f.factor}</div>
      <div class="factor-impact">${f.impact}</div>
    </div>
  `
    )
    .join('');

  card.innerHTML = `
    <div class="explanation-title">
      <span>✦</span>
      AI Analysis
    </div>
    <div class="explanation-summary">${exp.summary}</div>
    ${factorsHtml ? `<div class="factor-list">${factorsHtml}</div>` : ''}
  `;

  card.style.display = 'block';
}

// ── Raw JSON ───────────────────────────────────────────────────
function renderRawJson(data) {
  const pre = $('rawJson');
  pre.textContent = JSON.stringify(data, null, 2);
  pre.style.display = 'none';
  $('rawToggle').textContent = '';
  $('rawToggle').innerHTML = `
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
    </svg>
    View Raw JSON Response
  `;
}

function toggleRaw() {
  const pre = $('rawJson');
  const btn = $('rawToggle');
  const isHidden = pre.style.display === 'none';
  pre.style.display = isHidden ? 'block' : 'none';
  btn.querySelector('svg').style.opacity = isHidden ? '1' : '0.5';
}

// ── Formatters ─────────────────────────────────────────────────
function formatCurrency(value, decimals = 2) {
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Health check
  checkApiHealth();
  setInterval(checkApiHealth, 30000); // Recheck every 30s

  // Historical sales count + mini chart
  const histInput = $('historicalSales');
  histInput.addEventListener('input', updateSalesCount);
  updateSalesCount(); // Initial render

  // Auto-run forecast on load with default data
  const form = $('forecastForm');
  if (form) {
    form.dispatchEvent(new Event('submit', { cancelable: true }));
  }
});
