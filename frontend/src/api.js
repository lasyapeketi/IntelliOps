const API_BASE = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) }
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = body.detail || message
      if (Array.isArray(message)) {
        message = message.map(err => {
          const loc = Array.isArray(err.loc) ? err.loc.filter(p => p !== 'body').join(' -> ') : ''
          return loc ? `[${loc}]: ${err.msg}` : (err.msg || JSON.stringify(err))
        }).join('; ')
      }
    } catch {}
    throw new Error(message)
  }
  const type = response.headers.get('content-type') || ''
  return type.includes('text/csv') ? response.blob() : response.json()
}

export const api = {
  health: () => request('/api/health'),
  options: () => request('/api/location/options'),
  
  // Section 4.1: Default Recommendations
  defaultCategories: () => request('/api/location/default/categories'),
  recommendDefault: payload => request('/api/location/default/recommend', { method: 'POST', body: JSON.stringify(payload) }),
  compareDefault: payload => request('/api/location/default/compare', { method: 'POST', body: JSON.stringify(payload) }),
  scenarioDefault: payload => request('/api/location/default/scenario', { method: 'POST', body: JSON.stringify(payload) }),

  // Section 4.2: Based on Your Data Input
  uploadCustom: file => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/location/custom/upload', { method: 'POST', body: form })
  },
  recommendCustom: payload => request('/api/location/custom/recommend', { method: 'POST', body: JSON.stringify(payload) }),
  compareCustom: payload => request('/api/location/custom/compare', { method: 'POST', body: JSON.stringify(payload) }),
  scenarioCustom: payload => request('/api/location/custom/scenario', { method: 'POST', body: JSON.stringify(payload) }),
  exportCustom: payload => request('/api/location/custom/export', { method: 'POST', body: JSON.stringify(payload) }),
  getTemplateUrl: type => `${API_BASE}/api/location/custom/template?type=${type}`,

  // Existing Baseline Multi-Factor Endpoints (preserved)
  recommend: payload => request('/api/location/recommend', { method: 'POST', body: JSON.stringify(payload) }),
  scenario: payload => request('/api/location/scenario', { method: 'POST', body: JSON.stringify(payload) }),
  upload: file => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/location/upload', { method: 'POST', body: form })
  },
  export: payload => request('/api/location/export', { method: 'POST', body: JSON.stringify(payload) })
}
