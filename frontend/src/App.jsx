import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, ArrowDownRight, ArrowUpRight, BarChart3, Building2, CheckCircle2,
  ChevronDown, CircleHelp, Compass, Download, FileUp, Gauge, Info, MapPin,
  Menu, Plus, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Sparkles,
  Trash2, TrendingUp, Wallet, X, Database, Layers, UploadCloud, FileText,
  Filter, AlertTriangle, Eye, ArrowRight
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { api } from './api'

const money = value => value == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
const fmt = v => v == null ? 'Not supplied' : `${Math.round(v)} / 100`
const cleanProfile = p => ({
  ...p,
  budget: Number(p.budget) || 100000,
  required_space_sqm: p.required_space_sqm === '' || p.required_space_sqm == null ? null : Number(p.required_space_sqm)
})

export default function App() {
  // Navigation & Active Recommendation Method
  const [activeTab, setActiveTab] = useState('Overview')
  const [recMethod, setRecMethod] = useState('default') // 'default' | 'custom'
  const [locationSubSection, setLocationSubSection] = useState('default') // 'default' | 'custom'

  // Global Business Profile
  const [profile, setProfile] = useState({
    business_name: 'My Business',
    category: 'Restaurant',
    target_customer: 'General public',
    budget: 100000,
    preferred_city: '',
    required_space_sqm: '',
    parking_required: false
  })
  const [categories, setCategories] = useState([
    'Restaurant', 'Cafe', 'Grocery Store', 'Clothing Store', 'Pharmacy',
    'Bakery', 'Gym', 'Electronics Store', 'Salon', 'Stationery Store', 'Other'
  ])

  // Method 1: Default Recommendations State
  const [defaultCategories, setDefaultCategories] = useState([])
  const [defaultSelectedEnv, setDefaultSelectedEnv] = useState('All')
  const [defaultResults, setDefaultResults] = useState(null)
  const [defaultBaseline, setDefaultBaseline] = useState(null)
  const [defaultWeights, setDefaultWeights] = useState({
    affinity: 0.30, footfall: 0.20, accessibility: 0.15,
    customer_fit: 0.15, competition: 0.10, cost_viability: 0.10
  })

  // Method 2: Based on Your Data Input State
  const [uploadedDataset, setUploadedDataset] = useState(null)
  const [customBusinessType, setCustomBusinessType] = useState('')
  const [customResults, setCustomResults] = useState(null)
  const [customBaseline, setCustomBaseline] = useState(null)
  const [customScenarioParams, setCustomScenarioParams] = useState({
    min_occurrences: 1, weight_frequency: 0.6, weight_metrics: 0.4, budget_filter: ''
  })

  // Shared UI & Status State
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [apiOnline, setApiOnline] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)

  // Initialize data on mount
  useEffect(() => {
    api.health()
      .then(() => {
        setApiOnline(true)
        return Promise.all([api.options(), api.defaultCategories()])
      })
      .then(([opts, catRes]) => {
        if (opts?.business_categories) setCategories(opts.business_categories)
        if (catRes?.categories) {
          setDefaultCategories(catRes.categories)
          // Run initial default analysis automatically
          return api.recommendDefault({
            business_type: profile.category,
            profile: cleanProfile(profile),
            weights: defaultWeights
          })
        }
      })
      .then(res => {
        if (res) {
          setDefaultResults(res)
          setDefaultBaseline(res)
        }
      })
      .catch(err => {
        api.health().catch(() => setApiOnline(false))
        setError(err.message)
      })
  }, [])

  // Sync profile category when changed in Profile or Custom dataset
  const updateProfile = (key, value) => {
    setProfile(p => ({ ...p, [key]: value }))
  }

  // Handle switching method
  const handleMethodSwitch = method => {
    setRecMethod(method)
    setLocationSubSection(method)
    setSelectedIds([])
  }

  // Execute Default Recommendations
  const runDefaultAnalysis = async (isScenario = false, scenarioProfile = null, scenarioWeights = null) => {
    setBusy(true); setError(''); setNotice('')
    const targetProfile = cleanProfile(scenarioProfile || profile)
    const targetWeights = scenarioWeights || defaultWeights
    try {
      const payload = {
        business_type: targetProfile.category,
        profile: targetProfile,
        weights: targetWeights,
        environments: defaultSelectedEnv === 'All' ? null : [defaultSelectedEnv]
      }
      const response = isScenario ? await api.scenarioDefault(payload) : await api.recommendDefault(payload)
      setDefaultResults(response)
      if (!isScenario || !defaultBaseline) setDefaultBaseline(response)
      setNotice(isScenario ? 'Default scenario recalculated with revised assumptions.' : `Default recommendations updated for ${targetProfile.category}.`)
      setApiOnline(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Handle File Upload for Based on Your Data Input
  const handleFileUpload = async file => {
    if (!file) return
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await api.uploadCustom(file)
      setUploadedDataset(response)
      const bTypes = response.summary.available_business_types
      const defaultBt = bTypes.includes(profile.category) ? profile.category : (bTypes[0] || '')
      setCustomBusinessType(defaultBt)

      // Add uploaded business types to categories dropdown if not present
      setCategories(prev => {
        const set = new Set([...prev, ...bTypes])
        return Array.from(set)
      })

      // Automatically run recommendation for the first/matching business type
      if (defaultBt) {
        const recRes = await api.recommendCustom({
          dataset_id: response.summary.dataset_id,
          rows: response.rows,
          selected_business_type: defaultBt
        })
        setCustomResults(recRes)
        setCustomBaseline(recRes)
      }

      setNotice(`Dataset '${file.name}' processed: ${response.summary.accepted_rows} rows accepted across ${bTypes.length} business types.`)
      setRecMethod('custom')
      setLocationSubSection('custom')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Execute Custom Data-Driven Recommendations
  const runCustomAnalysis = async (isScenario = false, scenarioParams = null) => {
    if (!uploadedDataset) {
      setError('Upload a dataset containing "Business Type" and "Location Name" first.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    const p = scenarioParams || customScenarioParams
    try {
      const payload = {
        dataset_id: uploadedDataset.summary.dataset_id,
        rows: uploadedDataset.rows,
        selected_business_type: customBusinessType,
        min_occurrences: Number(p.min_occurrences) || 1,
        weight_frequency: Number(p.weight_frequency) || 0.6,
        weight_metrics: Number(p.weight_metrics) || 0.4,
        budget_filter: p.budget_filter ? Number(p.budget_filter) : null
      }
      const response = isScenario ? await api.scenarioCustom(payload) : await api.recommendCustom(payload)
      setCustomResults(response)
      if (!isScenario || !customBaseline) setCustomBaseline(response)
      setNotice(isScenario ? 'Data-driven scenario recalculated.' : `Recommendations updated for '${customBusinessType}' from dataset.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Drag and Drop handlers
  const handleDrag = e => {
    e.preventDefault(); e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }
  const handleDrop = e => {
    e.preventDefault(); e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  // Active results and metrics according to active method
  const activeResults = recMethod === 'default' ? defaultResults : customResults
  const activeBaseline = recMethod === 'default' ? defaultBaseline : customBaseline
  const activeRecommendations = activeResults?.recommendations || []
  const activeBest = activeRecommendations[0] || null
  const activeAverage = activeRecommendations.length
    ? activeRecommendations.reduce((s, r) => s + r.score, 0) / activeRecommendations.length
    : 0

  const navItems = [
    { name: 'Overview', icon: Gauge },
    { name: 'Business Profile', icon: Building2 },
    { name: 'Location', icon: MapPin },
    { name: 'Compare', icon: BarChart3 },
    { name: 'Scenario Lab', icon: SlidersHorizontal },
    { name: 'Methodology', icon: CircleHelp }
  ]

  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={21} /></div>
          <div>
            <strong>IntelliOps</strong>
            <span>LOCATION INTELLIGENCE</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {navItems.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${activeTab === name ? 'active' : ''}`}
              onClick={() => setActiveTab(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === 'Location' && (
                <b className="nav-count">{activeRecommendations.length}</b>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="mini-shield">
            <ShieldCheck size={18} />
            <div>
              <b>Dual-Engine Intelligence</b>
              <span>Default &amp; Data-Driven</span>
            </div>
          </div>
          <div className="sidebar-version">
            INTELLIOPS · MODULE 10 <span>v2.0.0</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main">
        {/* Topbar with Method Switcher */}
        <header className="topbar">
          <div className="crumb">
            <span>IntelliOps</span>
            <span className="slash">/</span>
            <strong>Business Location Recommendation</strong>
          </div>

          <div className="top-actions">
            {/* Global Recommendation Method Switcher */}
            <div className="method-switcher">
              <button
                type="button"
                className={`method-btn ${recMethod === 'default' ? 'active' : ''}`}
                onClick={() => handleMethodSwitch('default')}
              >
                <Layers size={13} />
                Default Recommendations
              </button>
              <button
                type="button"
                className={`method-btn ${recMethod === 'custom' ? 'active' : ''}`}
                onClick={() => handleMethodSwitch('custom')}
              >
                <Database size={13} />
                Based on Your Data Input
              </button>
            </div>

            <span className={`api-status ${apiOnline ? 'online' : ''}`}>
              <i />
              {apiOnline ? 'API connected' : 'API offline'}
            </span>
            <div className="avatar">IO</div>
          </div>
        </header>

        <div className="page-wrap">
          {/* Page Heading */}
          <div className="page-heading">
            <div>
              <div className="eyebrow">INTELLIGENT BUSINESS OPERATIONS · MODULE 10</div>
              <h1>{activeTab === 'Overview' ? 'Location Decision Workspace' : activeTab}</h1>
              <p>
                {activeTab === 'Overview'
                  ? 'Evaluate commercial categories, benchmark user datasets, and explore location trade-offs with explainable decision support.'
                  : pageSubtitle(activeTab, recMethod)}
              </p>
            </div>

            <div className="heading-actions">
              <span className={`method-badge ${recMethod}`}>
                {recMethod === 'default' ? (
                  <>
                    <Layers size={12} /> Default Knowledge-Base
                  </>
                ) : (
                  <>
                    <Database size={12} /> Data-Driven:{' '}
                    {uploadedDataset ? uploadedDataset.summary.filename : 'No File'}
                  </>
                )}
              </span>

              {activeTab === 'Location' && recMethod === 'default' && (
                <button
                  className="btn btn-primary"
                  onClick={() => runDefaultAnalysis()}
                  disabled={busy}
                >
                  <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
                  {busy ? 'Evaluating…' : 'Run Default Analysis'}
                </button>
              )}

              {activeTab === 'Location' && recMethod === 'custom' && (
                <button
                  className="btn btn-primary"
                  onClick={() => runCustomAnalysis()}
                  disabled={busy || !uploadedDataset}
                >
                  <Sparkles size={14} />
                  {busy ? 'Analyzing…' : 'Analyze Dataset'}
                </button>
              )}
            </div>
          </div>

          {/* Feedback Alerts */}
          {error && (
            <div className="alert alert-error">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button onClick={() => setError('')}><X size={15} /></button>
            </div>
          )}
          {notice && (
            <div className="alert alert-success">
              <CheckCircle2 size={18} />
              <span>{notice}</span>
              <button onClick={() => setNotice('')}><X size={15} /></button>
            </div>
          )}
          {!apiOnline && (
            <div className="alert alert-info">
              <Info size={18} />
              <span>FastAPI backend is offline. Run <code>uvicorn app.main:app --reload</code> in the backend directory.</span>
            </div>
          )}

          {/* Workspace Views */}
          {activeTab === 'Overview' && (
            <OverviewPanel
              recMethod={recMethod}
              setRecMethod={handleMethodSwitch}
              best={activeBest}
              average={activeAverage}
              count={activeRecommendations.length}
              results={activeResults}
              profile={profile}
              uploadedDataset={uploadedDataset}
              setTab={setActiveTab}
              runDefault={() => runDefaultAnalysis()}
              runCustom={() => runCustomAnalysis()}
              busy={busy}
            />
          )}

          {activeTab === 'Business Profile' && (
            <ProfilePanel
              profile={profile}
              update={updateProfile}
              categories={categories}
              recMethod={recMethod}
              setRecMethod={handleMethodSwitch}
              uploadedDataset={uploadedDataset}
              defaultWeights={defaultWeights}
              setDefaultWeights={setDefaultWeights}
              runDefault={() => runDefaultAnalysis()}
            />
          )}

          {activeTab === 'Location' && (
            <LocationWorkspace
              recMethod={recMethod}
              setRecMethod={handleMethodSwitch}
              subSection={locationSubSection}
              setSubSection={setLocationSubSection}
              profile={profile}
              updateProfile={updateProfile}
              categories={categories}
              defaultCategories={defaultCategories}
              defaultSelectedEnv={defaultSelectedEnv}
              setDefaultSelectedEnv={setDefaultSelectedEnv}
              defaultResults={defaultResults}
              runDefault={() => runDefaultAnalysis()}
              uploadedDataset={uploadedDataset}
              customBusinessType={customBusinessType}
              setCustomBusinessType={setCustomBusinessType}
              customResults={customResults}
              runCustom={() => runCustomAnalysis()}
              fileInputRef={fileInputRef}
              handleFileUpload={handleFileUpload}
              handleDrag={handleDrag}
              handleDrop={handleDrop}
              dragActive={dragActive}
              busy={busy}
              search={search}
              setSearch={setSearch}
            />
          )}

          {activeTab === 'Compare' && (
            <ComparePanel
              recMethod={recMethod}
              defaultResults={defaultResults}
              customResults={customResults}
              selectedIds={selectedIds}
              setSelectedIds={setSelectedIds}
              setTab={setActiveTab}
            />
          )}

          {activeTab === 'Scenario Lab' && (
            <ScenarioLabPanel
              recMethod={recMethod}
              profile={profile}
              defaultResults={defaultResults}
              defaultBaseline={defaultBaseline}
              defaultWeights={defaultWeights}
              runDefaultScenario={runDefaultAnalysis}
              uploadedDataset={uploadedDataset}
              customBusinessType={customBusinessType}
              customResults={customResults}
              customBaseline={customBaseline}
              customParams={customScenarioParams}
              setCustomParams={setCustomScenarioParams}
              runCustomScenario={runCustomAnalysis}
              busy={busy}
            />
          )}

          {activeTab === 'Methodology' && (
            <MethodologyPanel />
          )}

          {/* Footer */}
          <footer className="footer">
            <span>IntelliOps · Business Location Recommendation Module</span>
            <span>
              <ShieldCheck size={13} />
              Comparative decision-support indicators. Verify micro-market evidence before lease execution.
            </span>
          </footer>
        </div>
      </main>
    </div>
  )
}

function pageSubtitle(tab, method) {
  if (tab === 'Location') {
    return method === 'default'
      ? 'Section 4.1: Default recommendations based on predefined location categories and transparent MCDA.'
      : 'Section 4.2: Data-driven recommendations computed from your uploaded CSV or Excel dataset.'
  }
  return ({
    'Business Profile': 'Configure venture constraints, target customers, and factor priorities.',
    'Compare': 'Side-by-side comparative analysis of shortlisted candidate locations or archetypes.',
    'Scenario Lab': 'Simulate what-if changes and observe comparative score deltas without corrupting saved data.',
    'Methodology': 'Complete mathematical formulations, data-handling policies, and limitations.'
  })[tab] || ''
}

// ===========================================================================
// Overview Workspace
// ===========================================================================
function OverviewPanel({
  recMethod, setRecMethod, best, average, count, results, profile,
  uploadedDataset, setTab, runDefault, runCustom, busy
}) {
  return (
    <div className="stack">
      {/* Hero Banner */}
      <section className="hero-card">
        <div className="hero-copy">
          <div className="hero-tag">
            <span className="pulse-dot" /> DUAL-METHOD LOCATION INTELLIGENCE
          </div>
          <h2>Find the right place<br />for your next business move.</h2>
          <p>
            Choose between general category suitability guidance or upload your proprietary dataset
            to discover high-association locations tailored to your venture.
          </p>
          <div className="hero-buttons">
            <button className="btn btn-white" onClick={() => setTab('Location')}>
              Explore Location Recommendations <ArrowUpRight size={16} />
            </button>
            <button className="text-button" onClick={() => setTab('Methodology')}>
              How scoring works <ArrowRight size={14} />
            </button>
          </div>
        </div>

        <div className="hero-art">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="map-pin pin-a"><MapPin size={23} /></div>
          <div className="map-pin pin-b"><MapPin size={21} /></div>
          <div className="map-pin pin-c"><MapPin size={19} /></div>
          <div className="map-center"><Compass size={36} /></div>
          <div className="map-label label-a">Market Road <b>88</b></div>
          <div className="map-label label-b">College Road <b>85</b></div>
        </div>
      </section>

      {/* Method Banner Indicator */}
      <div className="guidance-banner" style={{ background: recMethod === 'default' ? '#eef2ff' : '#ecfdf5', borderColor: recMethod === 'default' ? '#c7d2fe' : '#a7f3d0', color: recMethod === 'default' ? '#3730a3' : '#065f46' }}>
        <Info size={18} />
        <div>
          <b>Active Recommendation Method: {recMethod === 'default' ? 'Default Recommendations (Knowledge-Base MCDA)' : `Based on Your Data Input (${uploadedDataset ? uploadedDataset.summary.filename : 'Upload Pending'})`}</b>
          <p style={{ margin: '3px 0 0', fontSize: '11px', opacity: 0.9 }}>
            {recMethod === 'default'
              ? 'Displaying general suitability guidance across 31+ location categories for ' + profile.category + '.'
              : (uploadedDataset ? `Displaying data-driven associations derived from ${uploadedDataset.summary.accepted_rows} rows in ${uploadedDataset.summary.filename}.` : 'No dataset uploaded yet. Go to Location to upload a CSV/Excel file.')}
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="metric-grid">
        <Metric
          icon={MapPin}
          label={recMethod === 'default' ? 'Evaluated Categories' : 'Locations in Dataset'}
          value={count || 0}
          detail={recMethod === 'default' ? 'Extensible archetypes' : 'From uploaded file'}
          tint="blue"
        />
        <Metric
          icon={Gauge}
          label="Average Suitability"
          value={results ? `${average.toFixed(1)}` : '—'}
          detail={results ? 'Across current matches' : 'Run analysis to compute'}
          tint="purple"
        />
        <Metric
          icon={TrendingUp}
          label="Top Ranked Option"
          value={best ? `${best.score.toFixed(1)}` : '—'}
          detail={best ? (best.name || best.location_name) : 'Awaiting evaluation'}
          tint="green"
        />
        <Metric
          icon={Wallet}
          label="Monthly Budget"
          value={money(profile.budget)}
          detail={`Venture: ${profile.category}`}
          tint="amber"
        />
      </div>

      {/* Content Grid */}
      <div className="content-grid">
        {/* Decision Workflow */}
        <section className="panel process-panel">
          <PanelTitle
            title="Recommendation Process"
            subtitle="Repeatable evaluation workflow across both methods"
          />
          <div className="workflow">
            {[
              ['01', 'Define Business Profile', 'Specify your category, budget ceiling, target customer, and space.'],
              ['02', 'Choose Recommendation Method', 'Use Default Categories or upload your own CSV/Excel dataset.'],
              ['03', 'Inspect Evidence & Compare', 'Review factor utility scores, co-locations, and due diligence checks.']
            ].map(([num, title, desc]) => (
              <div className="workflow-row" key={num}>
                <div className="step-num">{num}</div>
                <div>
                  <b>{title}</b>
                  <p>{desc}</p>
                </div>
                <ArrowUpRight size={16} />
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              onClick={recMethod === 'default' ? runDefault : runCustom}
              disabled={busy || (recMethod === 'custom' && !uploadedDataset)}
            >
              <Sparkles size={16} />
              {busy ? 'Evaluating…' : `Re-evaluate ${recMethod === 'default' ? 'Default Categories' : 'User Dataset'}`}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setTab('Location')}
            >
              View Full Shortlist
            </button>
          </div>
        </section>

        {/* Latest Top Recommendation Card */}
        <section className="panel">
          <PanelTitle
            title="Top Recommendation Highlight"
            subtitle={`Highest ranked for ${profile.category}`}
            right={
              <button className="subtle-link" onClick={() => setTab('Location')}>
                Inspect all <ArrowUpRight size={14} />
              </button>
            }
          />
          {best ? (
            <div className="best-card">
              <div className="best-top">
                <div className="best-location-icon"><MapPin size={21} /></div>
                <span className="rank-pill">RANK #1 · {best.classification}</span>
              </div>
              <h3>{best.name || best.location_name}</h3>
              <p className="muted">
                {recMethod === 'default'
                  ? `${best.environment} · Est. Benchmark ₹${best.typical_cost_estimate?.toLocaleString()}/mo`
                  : `${best.occurrence_count} recorded occurrence(s) · ${best.association_percentage}% of ${best.business_type} records`}
              </p>

              <div className="score-row">
                <div>
                  <span>Suitability score</span>
                  <strong>{best.score.toFixed(1)}<small>/100</small></strong>
                </div>
                <ScoreRing score={best.score} />
              </div>

              <div className="progress"><span style={{ width: `${best.score}%` }} /></div>
              <div className="best-class">{best.classification}</div>

              {best.strengths && best.strengths.slice(0, 2).map((s, i) => (
                <div className="reason" key={i}>
                  <CheckCircle2 size={15} />
                  <span>{s}</span>
                </div>
              ))}

              {recMethod === 'default' && best.factors && (
                <div className="mini-factor-breakdown">
                  <div className="mini-factor-title">Top Factor Utilities:</div>
                  <div className="mini-factor-chips">
                    {best.factors.slice(0, 4).map(f => (
                      <span key={f.key} className="mini-factor-chip">
                        {f.label}: <b>{Math.round(f.utility_score)}</b>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {recMethod === 'custom' && best.co_located_business_types && best.co_located_business_types.length > 0 && (
                <div className="mini-factor-breakdown">
                  <div className="mini-factor-title">Co-located Business Types in Dataset:</div>
                  <div className="mini-factor-chips">
                    {best.co_located_business_types.map(bt => (
                      <span key={bt} className="mini-factor-chip">{bt}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon"><Sparkles size={22} /></div>
              <b>No recommendations calculated yet</b>
              <p>Run the analysis or upload a dataset to generate candidate matches.</p>
              <button
                className="btn btn-secondary"
                onClick={recMethod === 'default' ? runDefault : () => setTab('Location')}
              >
                {recMethod === 'default' ? 'Analyze Categories' : 'Go to Location Upload'}
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Metric({ icon: Icon, label, value, detail, tint }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tint}`}><Icon size={19} /></div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  )
}
function PanelTitle({ title, subtitle, right }) {
  return (
    <div className="panel-title">
      <div>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}
function ScoreRing({ score }) {
  return (
    <div className="score-ring" style={{ '--score': `${score * 3.6}deg` }}>
      <div>
        <b>{Math.round(score)}</b>
        <span>score</span>
      </div>
    </div>
  )
}

// ===========================================================================
// Business Profile Workspace
// ===========================================================================
function ProfilePanel({
  profile, update, categories, recMethod, setRecMethod, uploadedDataset,
  defaultWeights, setDefaultWeights, runDefault
}) {
  const [showWeights, setShowWeights] = useState(false)
  const weightKeys = [
    ['affinity', 'Business Category Fit'],
    ['footfall', 'Customer Footfall Index'],
    ['accessibility', 'Transit & Road Access'],
    ['customer_fit', 'Target Demographics Match'],
    ['competition', 'Competitive Clustering'],
    ['cost_viability', 'Cost Affordability']
  ]

  const updateWeight = (key, val) => {
    setDefaultWeights(w => ({ ...w, [key]: Number(val) }))
  }

  return (
    <div className="form-layout">
      <section className="panel form-panel">
        <PanelTitle
          title="Business Profile &amp; Constraints"
          subtitle="Preferences defined here guide both Default and Data-Driven recommendation evaluations."
        />
        <div className="form-grid">
          <Field label="Business / Venture Name">
            <input
              value={profile.business_name}
              onChange={e => update('business_name', e.target.value)}
              placeholder="e.g. Cornerstone Café"
            />
          </Field>

          <Field label="Business Category" required hint="Synced across both recommendation methods">
            <select
              value={profile.category}
              onChange={e => update('category', e.target.value)}
            >
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>

          <Field label="Monthly Budget (₹)" required hint="Rent plus operating overheads">
            <input
              type="number"
              min="1"
              value={profile.budget}
              onChange={e => update('budget', e.target.value)}
            />
          </Field>

          <Field label="Preferred City / Region">
            <input
              value={profile.preferred_city}
              onChange={e => update('preferred_city', e.target.value)}
              placeholder="e.g. Hyderabad, Rajahmundry, Pune"
            />
          </Field>

          <Field label="Target Customer Group" hint="e.g. Students, Office workers, Families">
            <input
              value={profile.target_customer}
              onChange={e => update('target_customer', e.target.value)}
              placeholder="e.g. college students, corporate executives"
            />
          </Field>

          <Field label="Required Commercial Space (m²)" hint="Optional minimum footprint">
            <input
              type="number"
              min="0"
              value={profile.required_space_sqm}
              onChange={e => update('required_space_sqm', e.target.value)}
              placeholder="e.g. 120"
            />
          </Field>

          <label className="check-field">
            <input
              type="checkbox"
              checked={profile.parking_required}
              onChange={e => update('parking_required', e.target.checked)}
            />
            <span>
              <b>Dedicated Customer Parking is Essential</b>
              <small>Locations and categories lacking dedicated parking will receive warnings and ranking penalties.</small>
            </span>
          </label>
        </div>

        {/* Priority Factor Sliders for Default Engine */}
        <div className="weight-toggle-box">
          <div className="weight-toggle-head">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowWeights(!showWeights)}
            >
              <SlidersHorizontal size={14} />
              {showWeights ? 'Hide Factor Weights' : 'Customize Default Factor Priorities'}
            </button>
            {showWeights && (
              <button
                type="button"
                className="subtle-link"
                onClick={() => setDefaultWeights({ affinity: 0.30, footfall: 0.20, accessibility: 0.15, customer_fit: 0.15, competition: 0.10, cost_viability: 0.10 })}
              >
                Reset to Standard Defaults
              </button>
            )}
          </div>

          {showWeights && (
            <div className="weight-slider-grid">
              {weightKeys.map(([k, label]) => (
                <div key={k} className="weight-slider-row">
                  <div className="weight-slider-label">
                    <span>{label}</span>
                    <b>{((defaultWeights[k] || 0) * 100).toFixed(0)}%</b>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={defaultWeights[k] || 0}
                    onChange={e => updateWeight(k, e.target.value)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="form-note">
          <Info size={16} />
          <span>
            Changes to your business category and budget update your recommendation results across both
            the Default Recommendations catalogue and user-uploaded datasets.
          </span>
        </div>
      </section>

      {/* Side Information Note */}
      <section className="panel side-note">
        <div className="side-note-icon"><Building2 size={21} /></div>
        <h3>Cross-Feature Integration</h3>
        <p>
          IntelliOps keeps your business profile synchronized. When you select a business type or upload
          a custom dataset, candidate suitability scores adapt deterministically.
        </p>

        <div className="note-stat">
          <span>Active Method</span>
          <b>{recMethod === 'default' ? 'Default Catalogue' : 'Data-Driven'}</b>
        </div>
        <div className="note-stat">
          <span>Target Category</span>
          <b>{profile.category}</b>
        </div>
        <div className="note-stat">
          <span>Budget Ceiling</span>
          <b>{money(profile.budget)}</b>
        </div>
        <div className="note-stat">
          <span>Trained ML Claim</span>
          <b>None (Explainable Heuristics)</b>
        </div>
      </section>
    </div>
  )
}
function Field({ label, children, hint, required }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required && <em> *</em>}
      </span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

// ===========================================================================
// Location Workspace (Divided into 2 Subsections: Section 4.1 & 4.2)
// ===========================================================================
function LocationWorkspace({
  recMethod, setRecMethod, subSection, setSubSection,
  profile, updateProfile, categories, defaultCategories, defaultSelectedEnv,
  setDefaultSelectedEnv, defaultResults, runDefault,
  uploadedDataset, customBusinessType, setCustomBusinessType, customResults,
  runCustom, fileInputRef, handleFileUpload, handleDrag, handleDrop,
  dragActive, busy, search, setSearch
}) {
  const envs = [
    'All', 'Commercial & Retail', 'Transit & Transport', 'Education & Student',
    'Office & Corporate', 'Industrial & Logistics', 'Healthcare & Community',
    'Leisure & Hospitality', 'Civic & Mixed-Use'
  ]

  // Filter default recommendations
  const defaultRecs = defaultResults?.recommendations || []
  const filteredDefault = defaultRecs.filter(r =>
    `${r.name} ${r.environment} ${r.description}`.toLowerCase().includes(search.toLowerCase())
  )

  // Filter custom recommendations
  const customRecs = customResults?.recommendations || []
  const filteredCustom = customRecs.filter(r =>
    `${r.location_name} ${r.business_type}`.toLowerCase().includes(search.toLowerCase())
  )

  const downloadMinimalTemplate = () => {
    window.location.href = api.getTemplateUrl('minimal')
  }
  const downloadFullTemplate = () => {
    window.location.href = api.getTemplateUrl('full')
  }

  const exportCustomData = async () => {
    if (!uploadedDataset) return
    try {
      const blob = await api.exportCustom({
        dataset_id: uploadedDataset.summary.dataset_id,
        rows: uploadedDataset.rows,
        selected_business_type: customBusinessType
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `intelliops-${customBusinessType.toLowerCase()}-recommendations.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(`Export failed: ${e.message}`)
    }
  }

  return (
    <div className="stack">
      {/* Location Subnavigation Tabs */}
      <div className="location-subnav">
        <button
          type="button"
          className={`location-tab-btn ${subSection === 'default' ? 'active' : ''}`}
          onClick={() => { setSubSection('default'); setRecMethod('default') }}
        >
          <Layers size={17} />
          4.1 Default Recommendations (Knowledge-Base)
        </button>

        <button
          type="button"
          className={`location-tab-btn ${subSection === 'custom' ? 'active' : ''}`}
          onClick={() => { setSubSection('custom'); setRecMethod('custom') }}
        >
          <Database size={17} />
          4.2 Based on Your Data Input (Dataset Upload)
        </button>
      </div>

      {/* =================================================================== */}
      {/* SUBSECTION 4.1: Default Recommendations                             */}
      {/* =================================================================== */}
      {subSection === 'default' && (
        <div className="stack">
          {/* Controls Panel */}
          <section className="panel">
            <div className="panel-title">
              <div>
                <h3>General Location-Category Suitability Catalogue</h3>
                <p>
                  Explore pre-defined commercial category archetypes evaluated using an explainable
                  Multi-Criteria Decision Analysis (MCDA) model.
                </p>
              </div>

              <div className="inline-actions">
                <div className="search-box">
                  <Search size={15} />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search category archetypes…"
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={runDefault}
                  disabled={busy}
                >
                  <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
                  {busy ? 'Evaluating…' : 'Run Default Analysis'}
                </button>
              </div>
            </div>

            {/* Business Category and Macro Environment Filters */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', alignItems: 'center', marginBottom: '14px' }}>
              <Field label="Business Type for Evaluation">
                <select
                  value={profile.category}
                  onChange={e => {
                    updateProfile('category', e.target.value)
                  }}
                >
                  {categories.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>

              <div>
                <span className="field-label" style={{ display: 'block', marginBottom: '7px' }}>
                  Filter by Macro Environment
                </span>
                <div className="env-filter-bar">
                  {envs.map(env => (
                    <button
                      key={env}
                      type="button"
                      className={`env-chip ${defaultSelectedEnv === env ? 'active' : ''}`}
                      onClick={() => setDefaultSelectedEnv(env)}
                    >
                      {env}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="guidance-banner">
              <ShieldCheck size={18} />
              <div>
                <b>General Suitability Guidance Notice:</b>
                <span>
                  Recommendations in this section reflect general location archetypes and commercial clustering principles.
                  They do not certify specific physical properties, live vacancies, or legal lease terms. Independent on-ground
                  due diligence is required before capital commitment.
                </span>
              </div>
            </div>
          </section>

          {/* Results Shortlist */}
          <section className="panel">
            <PanelTitle
              title={`Ranked Category Shortlist for ${profile.category}`}
              subtitle={`Showing ${filteredDefault.length} category archetypes ranked by explainable suitability.`}
            />

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Category Archetype</th>
                    <th>Environment</th>
                    <th>Suitability</th>
                    <th>Est. Monthly Ask</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDefault.map(r => (
                    <tr key={r.id}>
                      <td>
                        <span className={`rank-dot ${r.rank === 1 ? 'first' : ''}`}>
                          {r.rank}
                        </span>
                      </td>
                      <td>
                        <div className="table-name">{r.name}</div>
                        <div className="table-sub">{r.description.slice(0, 85)}…</div>
                      </td>
                      <td>
                        <span className="col-tag">{r.environment}</span>
                      </td>
                      <td>
                        <div className="score-cell">
                          <b>{r.score.toFixed(1)}</b>
                          <div className="tiny-progress">
                            <span style={{ width: `${r.score}%` }} />
                          </div>
                        </div>
                      </td>
                      <td>₹{r.typical_cost_estimate?.toLocaleString()}/mo</td>
                      <td>
                        <span className={`status-pill ${r.classification.startsWith('High') ? 'good' : r.classification.startsWith('Moderate') ? 'medium' : 'low'}`}>
                          {r.classification}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Detailed Cards for Top Categories */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '14px' }}>
            {filteredDefault.slice(0, 5).map(r => (
              <DefaultCategoryDetailCard key={r.id} r={r} />
            ))}
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SUBSECTION 4.2: Based on Your Data Input                            */}
      {/* =================================================================== */}
      {subSection === 'custom' && (
        <div className="stack">
          {/* Upload Dropzone Panel */}
          <section className="panel">
            <PanelTitle
              title="Upload Your Own Dataset"
              subtitle="Generate recommendations derived strictly from associations and values in your uploaded dataset."
            />

            <div
              className={`upload-dropzone ${dragActive ? 'dragover' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.xlsx,.xls"
                hidden
                onChange={e => handleFileUpload(e.target.files?.[0])}
              />
              <div className="upload-icon-circle"><UploadCloud size={26} /></div>
              <b>Drag &amp; drop your dataset here, or click to browse</b>
              <p>
                Supports <b>CSV (.csv)</b> and <b>Excel (.xlsx)</b>.
                The only mandatory columns are <code>Business Type</code> and <code>Location Name</code>.
                Any additional columns (footfall, rent, ratings, demand, area, etc.) are dynamically ingested.
              </p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={e => { e.stopPropagation(); fileInputRef.current?.click() }}
              >
                <FileUp size={14} /> Select File from Computer
              </button>
            </div>

            {/* Template Download Bar */}
            <div className="template-bar">
              <div>
                <b>Need a starting template?</b> Download sample datasets with the mandatory columns.
              </div>
              <div className="template-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={downloadMinimalTemplate}
                  title="Download minimal 2-column CSV"
                >
                  <Download size={13} /> Minimal 2-Column CSV
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={downloadFullTemplate}
                  title="Download multi-column sample CSV"
                >
                  <Download size={13} /> Sample Multi-Column CSV
                </button>
              </div>
            </div>
          </section>

          {/* Dataset Inspection Summary Card */}
          {uploadedDataset && (
            <section className="panel dataset-summary-box">
              <PanelTitle
                title={`Dataset Summary: ${uploadedDataset.summary.filename}`}
                subtitle="Inspection results, accepted records, and detected schema attributes."
              />

              <div className="dataset-summary-grid">
                <div className="dataset-stat-card">
                  <span>Accepted Records</span>
                  <b>{uploadedDataset.summary.accepted_rows}</b>
                </div>
                <div className="dataset-stat-card">
                  <span>Excluded / Blank Rows</span>
                  <b style={{ color: uploadedDataset.summary.rejected_rows > 0 ? '#b91c1c' : '#0f172a' }}>
                    {uploadedDataset.summary.rejected_rows}
                  </b>
                </div>
                <div className="dataset-stat-card">
                  <span>Business Types Found</span>
                  <b>{uploadedDataset.summary.available_business_types.length}</b>
                </div>
                <div className="dataset-stat-card">
                  <span>Unique Locations</span>
                  <b>{uploadedDataset.summary.unique_locations_count}</b>
                </div>
              </div>

              <div>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155' }}>
                  Detected Columns &amp; Inferred Types:
                </span>
                <div className="col-tags">
                  {uploadedDataset.summary.columns.map(col => (
                    <span
                      key={col.name}
                      className={`col-tag ${['Business Type', 'Location Name'].includes(col.original_name) ? 'mandatory' : col.inferred_type === 'numeric' ? 'numeric' : ''}`}
                    >
                      <b>{col.original_name}</b> ({col.inferred_type})
                    </span>
                  ))}
                </div>
              </div>

              {uploadedDataset.summary.warnings.length > 0 && (
                <div className="warning-list" style={{ marginTop: '14px' }}>
                  {uploadedDataset.summary.warnings.map((w, i) => (
                    <div key={i}><Info size={14} />{w}</div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Query Controls & Data-Driven Shortlist */}
          {uploadedDataset ? (
            <section className="panel">
              <div className="panel-title">
                <div>
                  <h3>Data-Driven Location Recommendations</h3>
                  <p>
                    Rankings reflect association frequency, location clustering, and normalized metrics
                    from your dataset.
                  </p>
                </div>

                <div className="inline-actions">
                  <div className="search-box">
                    <Search size={15} />
                    <input
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Search locations…"
                    />
                  </div>
                  <button className="btn btn-secondary" onClick={exportCustomData}>
                    <Download size={14} /> Export CSV
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={runCustom}
                    disabled={busy}
                  >
                    <Sparkles size={14} />
                    {busy ? 'Analyzing…' : 'Re-calculate'}
                  </button>
                </div>
              </div>

              {/* Business Type Selector for Custom Data */}
              <div style={{ maxWidth: '320px', marginBottom: '16px' }}>
                <Field label="Select Business Type from Dataset" required>
                  <select
                    value={customBusinessType}
                    onChange={e => {
                      setCustomBusinessType(e.target.value)
                      updateProfile('category', e.target.value)
                    }}
                  >
                    {uploadedDataset.summary.available_business_types.map(bt => (
                      <option key={bt} value={bt}>{bt}</option>
                    ))}
                  </select>
                </Field>
              </div>

              {/* Shortlist Table */}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Location Name</th>
                      <th>Occurrences</th>
                      <th>Association %</th>
                      <th>Co-located Businesses</th>
                      <th>Suitability Score</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCustom.map(r => (
                      <tr key={r.id}>
                        <td>
                          <span className={`rank-dot ${r.rank === 1 ? 'first' : ''}`}>
                            {r.rank}
                          </span>
                        </td>
                        <td>
                          <div className="table-name">{r.location_name}</div>
                          {Object.keys(r.numeric_metrics).length > 0 && (
                            <div className="table-sub">
                              {Object.entries(r.numeric_metrics).map(([k, v]) => `${k}: ${v}`).join(' · ')}
                            </div>
                          )}
                        </td>
                        <td><b>{r.occurrence_count}</b></td>
                        <td>{r.association_percentage}%</td>
                        <td>
                          {r.co_located_business_types.length > 0
                            ? r.co_located_business_types.join(', ')
                            : 'None recorded'}
                        </td>
                        <td>
                          <div className="score-cell">
                            <b>{r.score.toFixed(1)}</b>
                            <div className="tiny-progress">
                              <span style={{ width: `${r.score}%` }} />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`status-pill ${r.classification.startsWith('High') ? 'good' : r.classification.startsWith('Moderate') ? 'medium' : 'low'}`}>
                            {r.classification}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Detailed Evidence Cards for Dataset Matches */}
              <div style={{ marginTop: '20px', display: 'grid', gap: '14px' }}>
                {filteredCustom.map(r => (
                  <CustomLocationDetailCard key={r.id} r={r} />
                ))}
              </div>
            </section>
          ) : (
            <div className="empty-state">
              <div className="empty-icon"><Database size={24} /></div>
              <b>No custom dataset uploaded yet</b>
              <p>
                Upload a CSV or Excel file above with <code>Business Type</code> and <code>Location Name</code> columns
                to view data-driven recommendations.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DefaultCategoryDetailCard({ r }) {
  return (
    <section className="panel detail-card">
      <div className="detail-heading">
        <div>
          <div className="detail-overline">RANK #{r.rank} · {r.environment.toUpperCase()}</div>
          <h3>{r.name}</h3>
          <p>{r.description}</p>
        </div>
        <div className="detail-score">
          <strong>{r.score.toFixed(1)}</strong>
          <span>/100</span>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <h4><CheckCircle2 size={15} /> Strengths &amp; Commercial Fit</h4>
          {r.strengths.map((s, i) => (
            <p key={i} className="bullet-line positive">{s}</p>
          ))}
        </div>
        <div>
          <h4><ArrowDownRight size={15} /> Areas to Review / Trade-offs</h4>
          {r.weaknesses.map((w, i) => (
            <p key={i} className="bullet-line caution">{w}</p>
          ))}
        </div>
      </div>

      {/* Factor Breakdown */}
      <div className="factor-breakdown">
        <h4>Factor Utilities (MCDA 0–100 Scale)</h4>
        <div className="factor-bars">
          {r.factors.map(f => (
            <div key={f.key} className="factor-bar-row">
              <span>{f.label}</span>
              <div className="progress"><span style={{ width: `${f.utility_score}%` }} /></div>
              <b>{Math.round(f.utility_score)}</b>
            </div>
          ))}
        </div>
      </div>

      {r.warnings.length > 0 && (
        <div className="warning-list">
          {r.warnings.map((w, i) => (
            <div key={i}><AlertTriangle size={14} />{w}</div>
          ))}
        </div>
      )}

      <div className="next-steps">
        <b>Suggested Due Diligence:</b>
        <ul>
          {r.next_steps.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function CustomLocationDetailCard({ r }) {
  return (
    <section className="panel detail-card">
      <div className="detail-heading">
        <div>
          <div className="detail-overline">RANK #{r.rank} · {r.classification.toUpperCase()}</div>
          <h3>{r.location_name}</h3>
          <p>
            {r.occurrence_count} record(s) in uploaded dataset ({r.association_percentage}% of {r.business_type} entries)
          </p>
        </div>
        <div className="detail-score">
          <strong>{r.score.toFixed(1)}</strong>
          <span>/100</span>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <h4><CheckCircle2 size={15} /> Dataset Strengths</h4>
          {r.strengths.map((s, i) => (
            <p key={i} className="bullet-line positive">{s}</p>
          ))}
        </div>
        <div>
          <h4><ArrowDownRight size={15} /> Limitations &amp; Caveats</h4>
          {r.weaknesses.map((w, i) => (
            <p key={i} className="bullet-line caution">{w}</p>
          ))}
        </div>
      </div>

      {r.warnings.length > 0 && (
        <div className="warning-list">
          {r.warnings.map((w, i) => (
            <div key={i}><AlertTriangle size={14} />{w}</div>
          ))}
        </div>
      )}

      {/* Dataset Evidence Drawer */}
      <details className="evidence-drawer">
        <summary>
          <Eye size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '6px' }} />
          View Supporting Records from Uploaded Dataset ({r.evidence_records.length} row{r.evidence_records.length === 1 ? '' : 's'})
        </summary>
        <table className="evidence-table">
          <thead>
            <tr>
              <th>Row #</th>
              <th>Business Type</th>
              <th>Location Name</th>
              <th>Additional Fields Detected</th>
            </tr>
          </thead>
          <tbody>
            {r.evidence_records.map((rec, i) => (
              <tr key={i}>
                <td>{rec.row_index}</td>
                <td>{rec.business_type}</td>
                <td><b>{rec.location_name}</b></td>
                <td>
                  {Object.entries(rec.additional_data).map(([k, v]) => `${k}: ${v}`).join(' | ') || 'None'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}

// ===========================================================================
// Compare Workspace
// ===========================================================================
function ComparePanel({ recMethod, defaultResults, customResults, selectedIds, setSelectedIds, setTab }) {
  const isDefault = recMethod === 'default'
  const activeRes = isDefault ? defaultResults : customResults

  if (!activeRes || !activeRes.recommendations || activeRes.recommendations.length === 0) {
    return (
      <EmptyPanel
        title="Nothing to compare yet"
        text={`Run an evaluation in the Location section (${isDefault ? 'Default Recommendations' : 'Based on Your Data Input'}) to compare options.`}
      />
    )
  }

  const all = activeRes.recommendations
  const chosenCandidates = selectedIds.length ? all.filter(r => selectedIds.includes(r.id)) : []
  const chosen = chosenCandidates.length > 0 ? chosenCandidates : all.slice(0, Math.min(3, all.length))

  return (
    <div className="stack">
      {/* Source Banner */}
      <div className="guidance-banner">
        <BarChart3 size={18} />
        <div>
          <b>Active Comparison Source: {isDefault ? 'Default Category Recommendations' : 'User Dataset Recommendations'}</b>
          <p style={{ margin: '2px 0 0', fontSize: '11px' }}>
            {isDefault
              ? 'Comparing commercial category archetypes across MCDA factor dimensions.'
              : 'Comparing user-uploaded locations across association frequencies and detected metrics.'}
          </p>
        </div>
      </div>

      {/* Select Candidates Chips */}
      <section className="panel">
        <PanelTitle
          title="Select Options to Compare"
          subtitle="Check 2 to 4 options to view side by side, or leave unselected for top 3."
        />
        <div className="select-chips">
          {all.map(r => (
            <label
              key={r.id}
              className={`select-chip ${selectedIds.includes(r.id) ? 'selected' : ''}`}
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(r.id)}
                onChange={e =>
                  setSelectedIds(ids =>
                    e.target.checked ? [...ids, r.id] : ids.filter(x => x !== r.id)
                  )
                }
              />
              <span>{r.name || r.location_name}</span>
              <b>{r.score.toFixed(0)}</b>
            </label>
          ))}
        </div>
      </section>

      {/* Side-by-Side Comparison Table */}
      <section className="panel">
        <PanelTitle
          title="Side-by-Side Comparison Matrix"
          subtitle="Direct comparison across common and domain-specific indicators."
        />
        <div className="table-wrap">
          <table className="compare-table">
            <thead>
              <tr>
                <th>Indicator</th>
                {chosen.map(r => (
                  <th key={r.id}>{r.name || r.location_name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Overall Suitability / Score</td>
                {chosen.map(r => (
                  <td key={r.id}>
                    <b className="big-table-score">{r.score.toFixed(1)}</b>
                    <span className="table-muted">/100</span>
                  </td>
                ))}
              </tr>
              <tr>
                <td>Rank</td>
                {chosen.map(r => (
                  <td key={r.id}>#{r.rank}</td>
                ))}
              </tr>
              <tr>
                <td>Classification</td>
                {chosen.map(r => (
                  <td key={r.id}>
                    <span className={`status-pill ${r.classification.startsWith('High') ? 'good' : 'medium'}`}>
                      {r.classification}
                    </span>
                  </td>
                ))}
              </tr>

              {isDefault ? (
                <>
                  <tr>
                    <td>Macro Environment</td>
                    {chosen.map(r => (
                      <td key={r.id}>{r.environment}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Benchmark Monthly Cost</td>
                    {chosen.map(r => (
                      <td key={r.id}>₹{r.typical_cost_estimate?.toLocaleString()}</td>
                    ))}
                  </tr>
                  {['affinity', 'footfall', 'accessibility', 'customer_fit', 'competition', 'cost_viability'].map(fk => (
                    <tr key={fk}>
                      <td>{fk.replace('_', ' ').toUpperCase()}</td>
                      {chosen.map(r => {
                        const factor = r.factors?.find(f => f.key === fk)
                        return (
                          <td key={r.id}>
                            {factor ? `${Math.round(factor.utility_score)} / 100` : '—'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </>
              ) : (
                <>
                  <tr>
                    <td>Dataset Occurrence Count</td>
                    {chosen.map(r => (
                      <td key={r.id}><b>{r.occurrence_count}</b></td>
                    ))}
                  </tr>
                  <tr>
                    <td>Association % in Dataset</td>
                    {chosen.map(r => (
                      <td key={r.id}>{r.association_percentage}%</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Co-located Business Types</td>
                    {chosen.map(r => (
                      <td key={r.id}>
                        {r.co_located_business_types?.length > 0
                          ? r.co_located_business_types.join(', ')
                          : 'None'}
                      </td>
                    ))}
                  </tr>
                </>
              )}

              <tr>
                <td>Key Strengths</td>
                {chosen.map(r => (
                  <td key={r.id}>
                    <ul className="table-list">
                      {r.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </td>
                ))}
              </tr>

              <tr>
                <td>Warnings &amp; Constraints</td>
                {chosen.map(r => (
                  <td key={r.id}>
                    <ul className="table-list">
                      {(r.warnings?.length ? r.warnings : ['No warnings returned.']).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Visual Chart Comparison */}
      <section className="panel chart-panel">
        <PanelTitle
          title="Comparative Suitability Chart"
          subtitle="Relative performance across selected options."
        />
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={chosen.map(r => ({ name: r.name || r.location_name, score: r.score }))}
            margin={{ top: 12, right: 12, left: 0, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8edf4" />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6e7b8e' }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6e7b8e' }} axisLine={false} tickLine={false} />
            <Tooltip />
            <Bar dataKey="score" name="Suitability Score" fill="#3867dc" radius={[6, 6, 0, 0]} barSize={44} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </div>
  )
}

// ===========================================================================
// Scenario Lab Workspace
// ===========================================================================
function ScenarioLabPanel({
  recMethod, profile, defaultResults, defaultBaseline, defaultWeights,
  runDefaultScenario, uploadedDataset, customBusinessType, customResults,
  customBaseline, customParams, setCustomParams, runCustomScenario, busy
}) {
  const isDefault = recMethod === 'default'

  // Default scenario local overrides
  const [hypoCategory, setHypoCategory] = useState(profile.category)
  const [hypoBudget, setHypoBudget] = useState(profile.budget)

  const handleRunDefaultScenario = () => {
    runDefaultScenario(true, cleanProfile({ ...profile, category: hypoCategory, budget: Number(hypoBudget) }), defaultWeights)
  }

  const handleRunCustomScenario = () => {
    runCustomScenario(true, customParams)
  }

  const activeRes = isDefault ? defaultResults : customResults
  const activeBase = isDefault ? defaultBaseline : customBaseline

  return (
    <div className="stack">
      {/* Banner */}
      <div className="scenario-banner">
        <div className="scenario-symbol"><SlidersHorizontal size={23} /></div>
        <div>
          <h3>Hypothetical What-If Scenario Lab</h3>
          <p>
            Evaluate alternative capital structures, filtering criteria, and priorities.
            Scenario executions are strictly hypothetical; they do not overwrite your original
            saved business profile or modify user-uploaded datasets.
          </p>
        </div>
      </div>

      {/* Scenario Controls Panel */}
      <section className="panel">
        <PanelTitle
          title={`Scenario Assumptions for ${isDefault ? 'Default Categories' : 'User Dataset'}`}
          subtitle="Modify hypothetical parameters below, then recalculate to observe ranking shifts."
        />

        {isDefault ? (
          <div className="form-grid" style={{ marginBottom: '16px' }}>
            <Field label="Hypothetical Business Category">
              <input
                value={hypoCategory}
                onChange={e => setHypoCategory(e.target.value)}
                placeholder="e.g. Pharmacy, Gym, Cafe"
              />
            </Field>

            <Field label="Hypothetical Monthly Budget (₹)">
              <input
                type="number"
                min="1"
                value={hypoBudget}
                onChange={e => setHypoBudget(e.target.value)}
              />
            </Field>
          </div>
        ) : (
          <div className="form-grid" style={{ marginBottom: '16px' }}>
            <Field label="Minimum Recorded Occurrences Filter" hint="Filter out single-record locations">
              <input
                type="number"
                min="1"
                value={customParams.min_occurrences}
                onChange={e => setCustomParams({ ...customParams, min_occurrences: e.target.value })}
              />
            </Field>

            <Field label="Hypothetical Budget Ceiling (₹)" hint="Penalize locations exceeding this cost">
              <input
                type="number"
                min="0"
                value={customParams.budget_filter}
                onChange={e => setCustomParams({ ...customParams, budget_filter: e.target.value })}
                placeholder="No budget ceiling"
              />
            </Field>

            <Field label="Frequency Weight Ratio (0.0 to 1.0)">
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={customParams.weight_frequency}
                onChange={e => setCustomParams({ ...customParams, weight_frequency: e.target.value })}
              />
            </Field>

            <Field label="Secondary Metrics Weight Ratio (0.0 to 1.0)">
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={customParams.weight_metrics}
                onChange={e => setCustomParams({ ...customParams, weight_metrics: e.target.value })}
              />
            </Field>
          </div>
        )}

        <div className="bottom-actions">
          <span>Assumptions apply only to this what-if simulation run.</span>
          <button
            className="btn btn-primary"
            onClick={isDefault ? handleRunDefaultScenario : handleRunCustomScenario}
            disabled={busy || (!isDefault && !uploadedDataset)}
          >
            <RefreshCw size={15} className={busy ? 'animate-spin' : ''} />
            {busy ? 'Simulating…' : 'Recalculate Scenario'}
          </button>
        </div>
      </section>

      {/* Baseline vs Scenario Results Diff Table */}
      {activeRes && activeBase && (
        <section className="panel">
          <PanelTitle
            title="Scenario Ranking &amp; Score Delta vs Baseline"
            subtitle="Observe how candidate suitability changed compared to your starting baseline."
          />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Option / Location</th>
                  <th>Scenario Score</th>
                  <th>Baseline Score</th>
                  <th>Score Delta</th>
                  <th>Scenario Rank</th>
                </tr>
              </thead>
              <tbody>
                {activeRes.recommendations.map(r => {
                  const rName = r.name || r.location_name
                  const old = activeBase.recommendations.find(
                    x => (x.name || x.location_name) === rName
                  )
                  const diff = old ? r.score - old.score : 0
                  return (
                    <tr key={r.id}>
                      <td><b>{rName}</b></td>
                      <td><b>{r.score.toFixed(1)}</b></td>
                      <td>{old ? old.score.toFixed(1) : '—'}</td>
                      <td className={diff > 0 ? 'diff-up' : diff < 0 ? 'diff-down' : ''}>
                        {diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)}
                      </td>
                      <td>#{r.rank}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

// ===========================================================================
// Methodology Workspace
// ===========================================================================
function MethodologyPanel() {
  return (
    <div className="stack">
      <section className="method-hero">
        <div className="method-icon"><CircleHelp size={24} /></div>
        <div>
          <div className="eyebrow">TRANSPARENT DECISION ARCHITECTURE</div>
          <h2>Documented Recommendation Methodologies</h2>
          <p>
            IntelliOps is built on explainable mathematical models, not black-box predictions.
            Every score traces directly to transparent rules, association statistics, or explicit user inputs.
          </p>
        </div>
      </section>

      <div className="method-grid">
        {/* Method 1: Default Recommendations */}
        <section className="panel">
          <PanelTitle
            title="Method 1: Default Recommendations"
            subtitle="Multi-Criteria Decision Analysis (MCDA) across 31+ location categories."
          />
          <div className="formula">
            Score = Σ [ Normalized Factor Weight × Utility Score(u_i) ]
          </div>
          <p className="body-copy">
            Evaluates 31+ location category archetypes (commercial streets, college roads, transit hubs,
            IT parks, healthcare zones, industrial corridors, etc.) against the user’s selected business type.
          </p>
          <ul className="method-list">
            <li><b>Affinity Index:</b> Compatibility score between business type and location archetype.</li>
            <li><b>Footfall Utility:</b> Visitor density typical of the commercial category.</li>
            <li><b>Accessibility Utility:</b> Transit nodes, parking support, and arterial road connectivity.</li>
            <li><b>Customer Alignment:</b> Demographics fit between target customer and typical visitors.</li>
            <li><b>Cost Viability:</b> Evaluated relative to the user’s monthly rent and operating budget.</li>
          </ul>
        </section>

        {/* Method 2: Based on Your Data Input */}
        <section className="panel">
          <PanelTitle
            title="Method 2: Based on Your Data Input"
            subtitle="Data-driven association and multi-factor ranking from user files."
          />
          <div className="formula">
            Score = w_freq × Normalized Frequency + w_metrics × Normalized Metrics
          </div>
          <p className="body-copy">
            Ingests tabular CSV or Excel (.xlsx) files. Requires only two mandatory columns:
            <code>Business Type</code> and <code>Location Name</code>.
          </p>
          <ul className="method-list">
            <li><b>Association Frequency:</b> Relative occurrence frequency of location for the selected business type.</li>
            <li><b>Co-location Discovery:</b> Tracks other business types co-existing in that location.</li>
            <li><b>Flexible Column Normalization:</b> Automatically detects numeric columns (rent, footfall, ratings) and normalizes to 0–100 scale.</li>
            <li><b>Evidence Tracing:</b> Retains exact row references and values from the user’s source file.</li>
          </ul>
        </section>

        {/* Limitations & Ethics */}
        <section className="panel" style={{ gridColumn: '1 / -1' }}>
          <PanelTitle
            title="Limitations, Due Diligence &amp; Data Ethics"
            subtitle="Understanding what heuristic scores can and cannot guarantee."
          />
          <div className="form-note" style={{ marginTop: 0, marginBottom: '14px' }}>
            <AlertTriangle size={16} />
            <span>
              <b>Important ML Disclosure:</b> Neither recommendation method claims to be a predictive
              supervised machine learning model forecasting revenue, profit, or business survival.
              Scores are comparative utility indices based on supplied inputs and established retail principles.
            </span>
          </div>

          <ul className="method-list">
            <li>Default category recommendations reflect macro-market archetypes, not verified live vacancies.</li>
            <li>User dataset recommendations depend strictly on the sample size, freshness, and accuracy of your uploaded file.</li>
            <li>Always verify real-world lease conditions, municipal permits, competition density, and pedestrian footfall on-ground before committing capital.</li>
          </ul>
        </section>
      </div>
    </div>
  )
}

function EmptyPanel({ title, text }) {
  return (
    <section className="panel empty-large">
      <div className="empty-icon"><Sparkles size={24} /></div>
      <h3>{title}</h3>
      <p>{text}</p>
    </section>
  )
}
