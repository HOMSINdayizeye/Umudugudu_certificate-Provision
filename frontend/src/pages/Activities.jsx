import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getUser, can } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Pagination from '../components/Pagination.jsx'
import Spinner from '../components/Spinner.jsx'

export const ACTIVITY_KINDS = [
  { value: 'community_work', label: 'Community Work (Umuganda)' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'election', label: 'Election' },
  { value: 'training', label: 'Training / Sensitisation' },
  { value: 'other', label: 'Other' },
]

const today = () => new Date().toISOString().slice(0, 10)
const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')
const PAGE_SIZE = 15

// Leaders: activities of their area with attendance, and who has attended enough to qualify for the
// community engagement letter. The required count is set by the admin on the Eligibility page.
export default function Activities({ user }) {
  const [tab, setTab] = useState('activities')

  return (
    <div>
      <div className="page-head"><h1>Activities &amp; Attendance</h1></div>
      <div className="tabs">
        <button className={tab === 'activities' ? 'tab tab-active' : 'tab'} onClick={() => setTab('activities')}>Activities</button>
        <button className={tab === 'summary' ? 'tab tab-active' : 'tab'} onClick={() => setTab('summary')}>Attendance by citizen</button>
      </div>
      {tab === 'activities' ? <ActivityList user={user} /> : <AttendanceSummary user={user} />}
    </div>
  )
}

function ActivityList({ user }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    setError('')
    try {
      setData(await api.listActivities())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="card">
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="page-head" style={{ marginBottom: '1rem' }}>
        <div className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
          Activities{data ? ` (${data.activities.length})` : ''}
        </div>
        {data?.can_create && <button className="btn btn-small" onClick={() => setCreating(true)}>+ New Activity</button>}
      </div>

      {!data ? (
        <Spinner label="Loading activities…" />
      ) : data.activities.length === 0 ? (
        <p className="muted">
          No activities yet.{data.can_create ? ' Create one, then mark who attended.' : ''}
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <ExportButtons
            title="Activities"
            columns={['Date', 'Activity', 'Type', 'Area', 'Attended', 'Created by']}
            rows={data.activities.map((a) => [fmt(a.date), a.title, a.kind_display, a.location_name, a.attendance_count, a.created_by_name || ''])}
          />
          <table className="table">
            <thead>
              <tr><th>Date</th><th>Activity</th><th>Type</th><th>Area</th><th>Attended</th><th></th></tr>
            </thead>
            <tbody>
              {data.activities.map((a) => (
                <tr key={a.id} className="row-clickable" onClick={() => navigate(`/activities/${a.id}`)}>
                  <td>{fmt(a.date)}</td>
                  <td>
                    <strong>{a.title}</strong>
                    {a.description && <div className="muted small" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description}</div>}
                  </td>
                  <td><span className="badge badge-kind">{a.kind_display}</span></td>
                  <td>{a.location_name}</td>
                  <td>{a.attendance_count}</td>
                  <td className="actions-cell">
                    <Link to={`/activities/${a.id}`} className="btn btn-small" onClick={(e) => e.stopPropagation()}>
                      {data.can_mark ? 'Attendance' : 'View'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <ActivityFormModal
          user={user}
          onClose={() => setCreating(false)}
          onSaved={(a) => {
            setCreating(false)
            setMessage(`Activity "${a.title}" created. Open it to mark attendance.`)
            load()
          }}
        />
      )}
    </div>
  )
}

// Create or edit an activity: name, type, date, description.
export function ActivityFormModal({ user, activity, onClose, onSaved }) {
  const [form, setForm] = useState({
    kind: activity?.kind || 'community_work',
    title: activity?.title || '',
    date: activity?.date || today(),
    description: activity?.description || '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (f) => (e) => setForm({ ...form, [f]: e.target.value })

  // Picking a type fills in a sensible name until the leader types their own
  function pickKind(e) {
    const kind = e.target.value
    const auto = ACTIVITY_KINDS.some((k) => k.label === form.title) || !form.title
    setForm({ ...form, kind, title: auto ? ACTIVITY_KINDS.find((k) => k.value === kind).label : form.title })
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const saved = activity ? await api.updateActivity(activity.id, form) : await api.createActivity(form)
      onSaved(saved)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{activity ? 'Edit activity' : 'New activity'}</h2>
        {!activity && (
          <p className="muted small" style={{ marginTop: 0 }}>
            The activity belongs to {user?.village_name ? `${user.village_name} village` : 'your area'}. After saving, open it to mark attendance.
          </p>
        )}
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-row">
            <div className="form-group">
              <label>Type</label>
              <select value={form.kind} onChange={pickKind}>
                {ACTIVITY_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Date</label>
              <input type="date" value={form.date} onChange={set('date')} required />
            </div>
          </div>
          <div className="form-group">
            <label>Activity name</label>
            <input value={form.title} onChange={set('title')} required maxLength={200} placeholder="e.g. Umuganda – cleaning the drainage" />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea rows={4} value={form.description} onChange={set('description')} placeholder="What will be done, where to gather, what to bring…" />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy}>{busy ? 'Saving…' : activity ? 'Save Changes' : 'Create Activity'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function AttendanceSummary({ user }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('all') // all | eligible | not
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.attendanceSummary().then(setData).catch((err) => setError(err.message))
  }, [])
  useEffect(() => { setPage(1) }, [q, only])

  const needle = q.trim().toLowerCase()
  const rows = (data?.citizens || [])
    .filter((c) => only === 'all' || (only === 'eligible') === c.eligible)
    .filter((c) => !needle || [c.name, c.national_id, c.isibo, c.village_name].join(' ').toLowerCase().includes(needle))
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageRows = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      {error && <div className="alert alert-error">{error}</div>}
      {!data ? (
        <div className="card"><Spinner label="Counting attendance…" /></div>
      ) : (
        <>
          <div className="summary-grid">
            <div className="card summary-card">
              <span className="stat-label">Activities held</span>
              <span className="stat-value">{data.activities_count}</span>
            </div>
            <div className="card summary-card">
              <span className="stat-label">Required to qualify</span>
              <span className="stat-value">{data.min_attendance}</span>
              <span className="muted small">
                attendances for the community engagement letter
                {can(user || getUser(), 'settings:attendance') && <> · <Link to="/eligibility">change</Link></>}
              </span>
            </div>
            <div className="card summary-card">
              <span className="stat-label">Qualifying citizens</span>
              <span className="stat-value">{data.eligible_count}</span>
            </div>
            <div className="card summary-card summary-top">
              <span className="stat-label">Highest attendance</span>
              {data.top ? (
                <>
                  <strong style={{ fontSize: '1.05rem' }}>{data.top.name}</strong>
                  <span className="muted small">{data.top.attended} attendance{data.top.attended === 1 ? '' : 's'} · {data.top.isibo ? `isibo ${data.top.isibo} · ` : ''}{data.top.village_name}</span>
                </>
              ) : <span className="muted small">No attendance marked yet.</span>}
            </div>
          </div>

          <div className="card">
            <div className="filter-row date-filter">
              <div className="form-group" style={{ flex: '2 1 240px', maxWidth: 'none' }}>
                <label>Search</label>
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID number, isibo or village" />
              </div>
              <div className="form-group">
                <label>Show</label>
                <select value={only} onChange={(e) => setOnly(e.target.value)}>
                  <option value="all">All citizens</option>
                  <option value="eligible">Qualifying only</option>
                  <option value="not">Not yet qualifying</option>
                </select>
              </div>
            </div>

            {rows.length === 0 ? (
              <p className="muted">No citizens match.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <ExportButtons
                  title={`Attendance by citizen (minimum ${data.min_attendance})`}
                  columns={['#', 'Citizen', 'ID number', 'Isibo', 'Village', 'Attended', 'Qualifies']}
                  rows={rows.map((c, i) => [i + 1, c.name, c.national_id, c.isibo || '', c.village_name || '', c.attended, c.eligible ? 'Yes' : 'No'])}
                />
                <table className="table">
                  <thead>
                    <tr><th>#</th><th>Citizen</th><th>ID number</th><th>Isibo</th><th>Village</th><th>Attended</th><th>Community letter</th></tr>
                  </thead>
                  <tbody>
                    {pageRows.map((c, idx) => (
                      <tr key={c.id} className={data.top && data.top.id === c.id ? 'row-top' : ''}>
                        <td>{(current - 1) * PAGE_SIZE + idx + 1}</td>
                        <td>{c.name}{data.top && data.top.id === c.id && <span className="badge badge-approved badge-inline">★ Highest</span>}</td>
                        <td>{c.national_id}</td>
                        <td>{c.isibo || '—'}</td>
                        <td>{c.village_name}</td>
                        <td><strong>{c.attended}</strong> <span className="muted small">/ {data.min_attendance}</span></td>
                        <td>
                          {c.eligible
                            ? <span className="badge badge-approved">Eligible</span>
                            : <span className="badge badge-pending">{data.min_attendance - c.attended} more needed</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Pagination page={current} totalPages={totalPages} total={rows.length} label="citizen" onChange={setPage} />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
