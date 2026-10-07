const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (res.status === 401) {
    window.location.href = '/auth/login'
    throw new Error('Not logged in')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),

  listRuns: () => request('/api/validations'),
  startRun: (payload) => request('/api/validations', { method: 'POST', body: JSON.stringify(payload) }),
  getRun: (id) => request(`/api/validations/${id}`),
  updateRun: (id, payload) => request(`/api/validations/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  refreshChecks: (id) => request(`/api/validations/${id}/refresh-checks`, { method: 'POST' }),
  submitRun: (id) => request(`/api/validations/${id}/submit`, { method: 'POST' }),

  exportDocxUrl: (id) => `/api/validations/${id}/export.docx`,
  exportPdfUrl: (id) => `/api/validations/${id}/export.pdf`,
}
