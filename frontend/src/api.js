// Backend address for the deployed site. Change this line if the Render URL changes.
const PRODUCTION_API = 'https://umudugudu-certificate-provision.onrender.com'

// On localhost the Vite proxy forwards /api to the local Django server; anywhere else the deployed backend is used.
// VITE_API_URL, when set, overrides both.
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname)
const API_ORIGIN = (import.meta.env.VITE_API_URL || (isLocal ? '' : PRODUCTION_API)).replace(/\/$/, '')
const BASE = `${API_ORIGIN}/api`

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

// True when the signed-in user holds a permission key such as "delete:users" (admins hold all)
export function can(user, key) {
  return !!user && (user.is_superuser || user.is_admin_role || (user.permissions || []).includes(key))
}

// formData: send multipart (browser sets the boundary header itself)
// blob: resolve to {blob, filename} using the server's Content-Disposition
async function request(path, { method = 'GET', body, formData, blob = false } = {}) {
  const headers = {}
  if (!formData) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers['Authorization'] = `Token ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: formData ? formData : body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    clearSession()
    window.location.href = '/login'
    throw new Error('Session expired. Please log in again.')
  }

  if (blob) {
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      throw new Error(extractError(data) || 'Download failed.')
    }
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)
    const filename = match ? decodeURIComponent(match[1]) : 'download'
    return { blob: await res.blob(), filename }
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

// Trigger a browser download for a blob returned by the API
export function saveBlob({ blob, filename }) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  register: (payload) => request('/auth/register/', { method: 'POST', body: payload }),
  login: (payload) => request('/auth/login/', { method: 'POST', body: payload }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
  me: () => request('/auth/me/'),
  updateMe: (payload) => request('/auth/me/', { method: 'PATCH', body: payload }),
  changePassword: (payload) => request('/auth/change-password/', { method: 'POST', body: payload }),

  listRequests: () => request('/requests/'),
  createRequest: (payload) => request('/requests/', { method: 'POST', body: payload }),
  getRequest: (id) => request(`/requests/${id}/`),
  updateRequest: (id, payload) => request(`/requests/${id}/`, { method: 'PATCH', body: payload }),
  actOnRequest: (id, action, message = '') =>
    request(`/requests/${id}/${action}/`, { method: 'POST', body: { message } }),
  downloadCertificate: (id, { regenerate = false, format = 'docx' } = {}) =>
    request(`/requests/${id}/certificate/download/?${new URLSearchParams({ ...(regenerate ? { regenerate: 1 } : {}), as: format })}`, { blob: true }),
  listDocuments: () => request('/documents/'),
  exportTable: (payload) => request('/export/', { method: 'POST', body: payload, blob: true }),

  notifications: () => request('/notifications/'),
  markNotificationRead: (id) => request(`/notifications/${id}/read/`, { method: 'POST' }),
  markAllNotificationsRead: () => request('/notifications/read-all/', { method: 'POST' }),
  listCodes: (q = '') => request(`/codes/?q=${encodeURIComponent(q)}`),
  lookupCode: (code) => request(`/codes/${encodeURIComponent(code.trim())}/`),
  downloadByUrl: (url) => request(url.replace(/^\/api/, ''), { blob: true }),

  uploadAttachments: (id, kind, files) => {
    const fd = new FormData()
    fd.append('kind', kind)
    for (const f of files) fd.append('files', f)
    return request(`/requests/${id}/attachments/`, { method: 'POST', formData: fd })
  },
  downloadAttachment: (id) => request(`/attachments/${id}/download/`, { blob: true }),
  deleteAttachment: (id) => request(`/attachments/${id}/`, { method: 'DELETE' }),

  listAnnouncements: () => request('/announcements/'),
  createAnnouncement: (payload) => request('/announcements/', { method: 'POST', body: payload }),
  updateAnnouncement: (id, payload) => request(`/announcements/${id}/`, { method: 'PATCH', body: payload }),
  deleteAnnouncement: (id) => request(`/announcements/${id}/`, { method: 'DELETE' }),
  previewAnnouncement: (payload) => request('/announcements/preview/', { method: 'POST', body: payload }),
  downloadAnnouncement: (id, format = 'docx') => request(`/announcements/${id}/download/?as=${format}`, { blob: true }),

  listUsers: () => request('/users/'),
  createUser: (payload) => request('/users/', { method: 'POST', body: payload }),
  deleteUser: (id) => request(`/users/${id}/`, { method: 'DELETE' }),
  updateUser: (id, payload) => request(`/users/${id}/`, { method: 'PATCH', body: payload }),
  setUserPermissions: (id, grants, denies) =>
    request(`/users/${id}/permissions/`, { method: 'PUT', body: { grants, denies } }),
  permissionCatalog: () => request('/permissions/'),
  setRolePermissions: (role, permissions) =>
    request(`/permissions/roles/${role}/`, { method: 'PUT', body: { permissions } }),
  resetRolePermissions: (role) => request(`/permissions/roles/${role}/`, { method: 'DELETE' }),
  deleteCitizen: (id) => request(`/citizens/${id}/`, { method: 'DELETE' }),

  listDeaths: () => request('/citizens/deaths/'),
  searchForDeath: (q) => request(`/citizens/deaths/search/?q=${encodeURIComponent(q)}`),
  reportDeath: (payload) => request('/citizens/deaths/', { method: 'POST', body: payload }),
  undoDeath: (id) => request(`/citizens/deaths/${id}/`, { method: 'DELETE' }),

  listActivities: () => request('/activities/'),
  createActivity: (payload) => request('/activities/', { method: 'POST', body: payload }),
  getActivity: (id) => request(`/activities/${id}/`),
  updateActivity: (id, payload) => request(`/activities/${id}/`, { method: 'PATCH', body: payload }),
  deleteActivity: (id) => request(`/activities/${id}/`, { method: 'DELETE' }),
  searchAttendees: (id, q) => request(`/activities/${id}/attendance/?q=${encodeURIComponent(q)}`),
  markAttendance: (id, payload) => request(`/activities/${id}/attendance/`, { method: 'POST', body: payload }),
  unmarkAttendance: (id, citizenId) => request(`/activities/${id}/attendance/${citizenId}/`, { method: 'DELETE' }),
  attendanceSummary: () => request('/activities/summary/'),
  communityEligibility: (nationalId = '') => request(`/community/eligibility/?national_id=${encodeURIComponent(nationalId)}`),
  attendanceSetting: () => request('/settings/attendance/'),
  setAttendanceSetting: (minAttendance) =>
    request('/settings/attendance/', { method: 'PUT', body: { min_attendance: minAttendance } }),
  setEligibility: (id, isEligible) =>
    request(`/users/${id}/eligibility/`, { method: 'POST', body: { is_eligible: isEligible } }),

  listCitizens: (params = {}) => request(`/citizens/?${new URLSearchParams(params)}`),
  addCitizen: (payload) => request('/citizens/', { method: 'POST', body: payload }),
  updateCitizen: (id, payload) => request(`/citizens/${id}/`, { method: 'PATCH', body: payload }),
  transferCitizen: (id, payload) => request(`/citizens/${id}/transfer/`, { method: 'POST', body: payload }),
  placeCitizen: (id, isibo) => request(`/citizens/${id}/place/`, { method: 'POST', body: { isibo } }),
  listTransfers: () => request('/citizens/transfers/'),
  acceptTransfer: (id, isibo = '') => request(`/citizens/transfers/${id}/accept/`, { method: 'POST', body: { isibo } }),
  rejectTransfer: (id, note = '') => request(`/citizens/transfers/${id}/reject/`, { method: 'POST', body: { note } }),
  cancelTransfer: (id) => request(`/citizens/transfers/${id}/cancel/`, { method: 'POST', body: {} }),
  villageIsibos: (village) => request(`/citizens/isibos/?village=${village || ''}`),
  listPayments: (params = {}) => request(`/payments/?${new URLSearchParams(params)}`),
  recordPayment: (payload) => request('/payments/', { method: 'POST', body: payload }),
  unmarkPayment: (id) => request(`/payments/${id}/`, { method: 'DELETE' }),

  provinces: () => request('/locations/provinces/'),
  districts: (province) => request(`/locations/districts/?province=${province}`),
  sectors: (district) => request(`/locations/sectors/?district=${district}`),
  cells: (sector) => request(`/locations/cells/?sector=${sector}`),
  villages: (cell) => request(`/locations/villages/?cell=${cell}`),
}
