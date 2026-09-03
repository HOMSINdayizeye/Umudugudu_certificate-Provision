const BASE = '/api'

export function getToken() {
  return localStorage.getItem('certify_token')
}

export function setSession(token, user) {
  localStorage.setItem('certify_token', token)
  localStorage.setItem('certify_user', JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem('certify_token')
  localStorage.removeItem('certify_user')
}

export function getUser() {
  const raw = localStorage.getItem('certify_user')
  return raw ? JSON.parse(raw) : null
}

async function request(path, { method = 'GET', body, blob = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Token ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    clearSession()
    window.location.href = '/login'
    throw new Error('Session expired. Please log in again.')
  }

  if (blob) {
    if (!res.ok) throw new Error('Download failed.')
    return res.blob()
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const message = extractError(data) || `Request failed (${res.status})`
    throw new Error(message)
  }
  return data
}

function extractError(data) {
  if (!data) return null
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (data.non_field_errors) return data.non_field_errors.join(' ')
  // Flatten first field error, e.g. {email: ["taken"]}
  const key = Object.keys(data)[0]
  if (key) {
    const val = data[key]
    const msg = Array.isArray(val) ? val.join(' ') : typeof val === 'object' ? extractError(val) : String(val)
    return `${key}: ${msg}`
  }
  return null
}

export const api = {
  register: (payload) => request('/auth/register/', { method: 'POST', body: payload }),
  login: (payload) => request('/auth/login/', { method: 'POST', body: payload }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
  me: () => request('/auth/me/'),

  listRequests: () => request('/requests/'),
  createRequest: (payload) => request('/requests/', { method: 'POST', body: payload }),
  getRequest: (id) => request(`/requests/${id}/`),
  actOnRequest: (id, action) => request(`/requests/${id}/${action}/`, { method: 'POST' }),
  downloadCertificate: (id) => request(`/requests/${id}/certificate/download/`, { blob: true }),

  listUsers: () => request('/users/'),
  createUser: (payload) => request('/users/', { method: 'POST', body: payload }),
  setEligibility: (id, isEligible) =>
    request(`/users/${id}/eligibility/`, { method: 'POST', body: { is_eligible: isEligible } }),

  listCitizens: (params = {}) => request(`/citizens/?${new URLSearchParams(params)}`),
  listPayments: (params = {}) => request(`/payments/?${new URLSearchParams(params)}`),
  recordPayment: (payload) => request('/payments/', { method: 'POST', body: payload }),

  provinces: () => request('/locations/provinces/'),
  districts: (province) => request(`/locations/districts/?province=${province}`),
  sectors: (district) => request(`/locations/sectors/?district=${district}`),
  cells: (sector) => request(`/locations/cells/?sector=${sector}`),
  villages: (cell) => request(`/locations/villages/?cell=${cell}`),
}
