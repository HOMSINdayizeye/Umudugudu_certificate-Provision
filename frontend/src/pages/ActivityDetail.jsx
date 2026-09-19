import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Spinner from '../components/Spinner.jsx'
import { ActivityFormModal } from './Activities.jsx'

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')
const fmtTime = (d) => (d ? new Date(d).toLocaleString() : '—')
const emptyNew = { first_name: '', last_name: '', national_id: '', age: '', phone: '', isibo: '' }

// One activity: its details, who attended, and the attendance-marking tools.
export default function ActivityDetail({ user }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  async function load() {
    setError('')
    try {
      setData(await api.getActivity(id))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [id])

  async function remove() {
    setBusy(true)
    try {
      const res = await api.deleteActivity(id)
      navigate('/activities', { state: { message: res.detail } })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  async function unmark(citizenId, name) {
    setError('')
    setMessage('')
    try {
      await api.unmarkAttendance(id, citizenId)
      setMessage(`${name} removed from the attendance list.`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (!data && !error) return <Spinner label="Loading activity…" />
  if (!data) return <div className="alert alert-error">{error}</div>
  const a = data.activity

  return (
    <div>
      <div className="page-head">
        <div>
          <Link to="/activities" className="arrow-link">← Activities</Link>
          <h1 style={{ marginTop: '0.35rem' }}>{a.title}</h1>
        </div>
        {data.can_edit && (
          <div className="btn-row" style={{ marginTop: 0 }}>
            <button className="btn btn-small btn-outline-dark" onClick={() => setEditing(true)}>Edit</button>
            <button className="btn btn-small btn-danger" onClick={() => setConfirmDelete(true)}>Delete</button>
          </div>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {confirmDelete && (
        <div className="alert alert-error">
          <strong>Delete this activity?</strong> Its {data.attendances.length} attendance record{data.attendances.length === 1 ? '' : 's'} will be removed too.
          <div className="btn-row">
            <button className="btn btn-small btn-danger" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Yes, delete'}</button>
            <button className="btn btn-small btn-ghost" onClick={() => setConfirmDelete(false)}>Keep</button>
          </div>
        </div>
      )}

      <div className="two-col">
        <div className="card">
          <dl className="detail-grid">
            <dt>Type</dt><dd><span className="badge badge-kind">{a.kind_display}</span></dd>
            <dt>Date</dt><dd>{fmt(a.date)}</dd>
            <dt>Area</dt><dd>{a.location_name}</dd>
            <dt>Created by</dt><dd>{a.created_by_name || '—'}</dd>
            <dt>Attended</dt><dd><strong>{data.attendances.length}</strong> citizen{data.attendances.length === 1 ? '' : 's'}</dd>
          </dl>
          {a.description && (
            <>
              <div className="section-title">Description</div>
              <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{a.description}</p>
            </>
          )}
        </div>

        {data.can_mark && (
          <MarkAttendance
            activityId={id}
            user={user}
            onMarked={(res) => {
              setMessage(res.created
                ? `${res.citizen_name} marked as attended (${res.total_attendance} of ${res.min_attendance} needed for the community letter).`
                : `${res.citizen_name} was already marked for this activity.`)
              load()
            }}
          />
        )}
      </div>

      <div className="card" style={{ marginTop: '1.25rem' }}>
        <div className="section-title" style={{ marginTop: 0 }}>Attendance list ({data.attendances.length})</div>
        {data.attendances.length === 0 ? (
          <p className="muted">Nobody has been marked yet.{data.can_mark ? ' Search a citizen above to mark them.' : ''}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title={`Attendance — ${a.title} (${fmt(a.date)})`}
              columns={['#', 'Citizen', 'ID number', 'Isibo', 'Village', 'Marked at', 'Marked by']}
              rows={data.attendances.map((t, i) => [i + 1, t.citizen_name, t.national_id, t.isibo || '', t.village_name || '', fmtTime(t.marked_at), t.marked_by_name || ''])}
            />
            <table className="table">
              <thead>
                <tr><th>#</th><th>Citizen</th><th>ID number</th><th>Isibo</th><th>Village</th><th>Marked</th>{data.can_mark && <th></th>}</tr>
              </thead>
              <tbody>
                {data.attendances.map((t, i) => (
                  <tr key={t.id}>
                    <td>{i + 1}</td>
                    <td>{t.citizen_name}</td>
                    <td>{t.national_id}</td>
                    <td>{t.isibo || '—'}</td>
                    <td>{t.village_name}</td>
                    <td className="small">{fmtTime(t.marked_at)}{t.marked_by_name ? <span className="muted"> · {t.marked_by_name}</span> : null}</td>
                    {data.can_mark && (
                      <td className="actions-cell">
                        <button className="btn btn-small btn-ghost" onClick={() => unmark(t.citizen, t.citizen_name)}>Remove</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <ActivityFormModal
          user={user}
          activity={a}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); setMessage('Activity updated.'); load() }}
        />
      )}
    </div>
  )
}

// Search registered citizens and mark them; register on the spot when someone is missing.
function MarkAttendance({ activityId, user, onMarked }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [form, setForm] = useState(emptyNew)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  // Search as the leader types, after a short pause
  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults(null); return }
    timer.current = setTimeout(async () => {
      setSearching(true)
      try {
        setResults(await api.searchAttendees(activityId, q.trim()))
      } catch (err) {
        setError(err.message)
      } finally {
        setSearching(false)
      }
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, activityId])

  async function mark(citizen) {
    setError('')
    setBusy(true)
    try {
      const res = await api.markAttendance(activityId, { citizen: citizen.id })
      onMarked(res)
      setResults((r) => r && r.map((c) => (c.id === citizen.id ? { ...c, already_marked: true } : c)))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function registerAndMark(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api.markAttendance(activityId, { new: { ...form, age: Number(form.age) } })
      onMarked(res)
      setForm(emptyNew)
      setRegistering(false)
      setQ('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const set = (f) => (e) => setForm({ ...form, [f]: e.target.value })

  return (
    <div className="card">
      <div className="section-title" style={{ marginTop: 0 }}>Mark attendance</div>
      {error && <div className="alert alert-error">{error}</div>}

      {!registering ? (
        <>
          <div className="form-group">
            <label>Find a citizen</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID number or phone…" autoFocus />
          </div>
          {searching && <Spinner label="Searching…" />}
          {results && !searching && (
            results.length === 0 ? (
              <p className="muted small">No registered citizen matches “{q}”.</p>
            ) : (
              <ul className="attend-results">
                {results.map((c) => (
                  <li key={c.id}>
                    <div>
                      <strong>{c.name}</strong>
                      <div className="muted small">ID {c.national_id}{c.isibo ? ` · isibo ${c.isibo}` : ''} · {c.village_name}</div>
                    </div>
                    {c.already_marked
                      ? <span className="badge badge-approved">✔ Attended</span>
                      : <button className="btn btn-small" disabled={busy} onClick={() => mark(c)}>Mark attended</button>}
                  </li>
                ))}
              </ul>
            )
          )}
          <div className="info-strip" style={{ marginTop: '1rem', marginBottom: 0 }}>
            <span>Citizen not registered yet?</span>
            <button type="button" className="link-btn" onClick={() => { setRegistering(true); setForm({ ...emptyNew, isibo: user?.isibo || '' }) }}>
              Register them and mark attendance
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={registerAndMark}>
          <p className="muted small" style={{ marginTop: 0 }}>
            The citizen is added to the registry in {user?.village_name ? `${user.village_name} village` : 'the activity’s village'} and marked as attended.
          </p>
          <div className="form-row">
            <div className="form-group"><label>First name</label><input value={form.first_name} onChange={set('first_name')} required /></div>
            <div className="form-group"><label>Last name</label><input value={form.last_name} onChange={set('last_name')} required /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>ID number</label><input value={form.national_id} onChange={set('national_id')} maxLength={16} required /></div>
            <div className="form-group"><label>Age</label><input type="number" min="1" max="130" value={form.age} onChange={set('age')} required /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Isibo (optional)</label><input value={form.isibo} onChange={set('isibo')} /></div>
            <div className="form-group"><label>Phone (optional)</label><input value={form.phone} onChange={set('phone')} maxLength={20} /></div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Register & Mark Attended'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={() => setRegistering(false)}>Back to search</button>
          </div>
        </form>
      )}
    </div>
  )
}
