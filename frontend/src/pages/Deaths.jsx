import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Pagination from '../components/Pagination.jsx'
import Spinner from '../components/Spinner.jsx'

const PAGE_SIZE = 15
const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')
const today = () => new Date().toISOString().slice(0, 10)
const emptyNew = { first_name: '', last_name: '', national_id: '', age: '', phone: '', isibo: '' }

// Deceased register of the leader's area, with the village leader's tools to report a death.
// Reported citizens leave every living-citizen list and count (village, cell and sector).
export default function Deaths({ user, refreshKey }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reporting, setReporting] = useState(false)
  const [undoing, setUndoing] = useState(null)
  const [filters, setFilters] = useState({ q: '', from: '', to: '' })
  const [page, setPage] = useState(1)

  async function load() {
    setError('')
    try {
      setData(await api.listDeaths())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [refreshKey])
  useEffect(() => { setPage(1) }, [filters])

  const set = (f) => (e) => setFilters({ ...filters, [f]: e.target.value })
  const needle = filters.q.trim().toLowerCase()
  const rows = (data?.reports || [])
    .filter((r) => !needle || [r.citizen_name, r.national_id, r.phone, r.isibo, r.village_name, r.place, r.reported_by_name]
      .join(' ').toLowerCase().includes(needle))
    .filter((r) => !filters.from || r.date_of_death >= filters.from)
    .filter((r) => !filters.to || r.date_of_death <= filters.to)
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageRows = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const villages = new Set((data?.reports || []).map((r) => r.village))

  async function undo(r) {
    setError('')
    setMessage('')
    try {
      const res = await api.undoDeath(r.id)
      setMessage(res.detail)
      setUndoing(null)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="card">
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="page-head" style={{ marginBottom: '1rem' }}>
        <div className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
          Deceased register{data ? ` (${data.reports.length})` : ''}
        </div>
        {data?.can_report && <button className="btn btn-small btn-danger" onClick={() => setReporting(true)}>Report a death</button>}
      </div>

      <div className="filter-row date-filter">
        <div className="form-group" style={{ flex: '2 1 220px', maxWidth: 'none' }}>
          <label>Search</label>
          <input value={filters.q} onChange={set('q')} placeholder="Name, ID number, phone, isibo, place…" />
        </div>
        <div className="form-group">
          <label>Died from</label>
          <input type="date" value={filters.from} onChange={set('from')} />
        </div>
        <div className="form-group">
          <label>Died until</label>
          <input type="date" value={filters.to} onChange={set('to')} />
        </div>
        {(filters.q || filters.from || filters.to) && (
          <button type="button" className="btn btn-small btn-ghost" style={{ marginBottom: '0.15rem' }} onClick={() => setFilters({ q: '', from: '', to: '' })}>Clear</button>
        )}
      </div>

      {!data ? (
        <Spinner label="Loading register…" />
      ) : data.reports.length === 0 ? (
        <p className="muted">No death has been reported in your area.</p>
      ) : rows.length === 0 ? (
        <p className="muted">No report matches these filters.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <ExportButtons
            title="Deceased register"
            columns={['#', 'Name', 'ID number', 'Age', 'Phone', 'Isibo', 'Village', 'Date of death', 'Place', 'Note', 'Reported by', 'Reported on']}
            rows={rows.map((r, i) => [i + 1, r.citizen_name, r.national_id, r.age, r.phone || '', r.isibo || '', r.village_name,
              fmt(r.date_of_death), r.place || '', r.note || '', r.reported_by_name || '', fmt(r.reported_at)])}
          />
          <table className="table">
            <thead>
              <tr>
                <th>#</th><th>Name</th><th>ID number</th><th>Age</th><th>Phone</th><th>Isibo</th>
                {villages.size > 1 && <th>Village</th>}
                <th>Date of death</th><th>Place</th><th>Reported</th>
                {data.can_report && <th></th>}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r, idx) => (
                <tr key={r.id}>
                  <td>{(current - 1) * PAGE_SIZE + idx + 1}</td>
                  <td>{r.citizen_name}{r.note && <div className="muted small">{r.note}</div>}</td>
                  <td>{r.national_id}</td>
                  <td>{r.age || '—'}</td>
                  <td>{r.phone || '—'}</td>
                  <td>{r.isibo || '—'}</td>
                  {villages.size > 1 && <td>{r.village_name.split(',')[0]}</td>}
                  <td>{fmt(r.date_of_death)}</td>
                  <td>{r.place || '—'}</td>
                  <td className="small">{fmt(r.reported_at)}{r.reported_by_name ? <span className="muted"> · {r.reported_by_name}</span> : null}</td>
                  {data.can_report && (
                    <td className="actions-cell">
                      {undoing === r.id ? (
                        <>
                          <button className="btn btn-small btn-danger" onClick={() => undo(r)}>Confirm undo</button>
                          <button className="btn btn-small btn-ghost" onClick={() => setUndoing(null)}>Keep</button>
                        </>
                      ) : (
                        <button className="btn btn-small btn-ghost" title="Reported by mistake? Return this citizen to the living register" onClick={() => setUndoing(r.id)}>Undo</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={current} totalPages={totalPages} total={rows.length} label="report" onChange={setPage} />
        </div>
      )}

      {reporting && (
        <ReportDeathModal
          user={user}
          onClose={() => setReporting(false)}
          onDone={(r) => {
            setReporting(false)
            setMessage(`${r.citizen_name} reported deceased on ${fmt(r.date_of_death)}. They no longer count among the citizens of the village, cell or sector.`)
            load()
          }}
        />
      )}
    </div>
  )
}

// Village leader: find the citizen (or register them) and record the death.
export function ReportDeathModal({ user, citizen: preselected, onClose, onDone }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [chosen, setChosen] = useState(preselected || null)
  const [registering, setRegistering] = useState(false)
  const [form, setForm] = useState(emptyNew)
  const [death, setDeath] = useState({ date_of_death: today(), place: '', note: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    clearTimeout(timer.current)
    if (chosen || registering || q.trim().length < 2) { setResults(null); return }
    timer.current = setTimeout(async () => {
      setSearching(true)
      try {
        setResults(await api.searchForDeath(q.trim()))
      } catch (err) {
        setError(err.message)
      } finally {
        setSearching(false)
      }
    }, 300)
    return () => clearTimeout(timer.current)
  }, [q, chosen, registering])

  const setF = (f) => (e) => setForm({ ...form, [f]: e.target.value })
  const setD = (f) => (e) => setDeath({ ...death, [f]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const payload = { ...death }
      if (registering) payload.new = { ...form, age: Number(form.age) }
      else payload.citizen = chosen.id
      onDone(await api.reportDeath(payload))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const ready = registering || !!chosen

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Report a death</h2>
        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={submit}>
        <div className="section-title" style={{ marginTop: 0 }}>Death details</div>
        <div className="form-row">
          <div className="form-group">
            <label>Date of death <span className="req">*</span></label>
            <input type="date" value={death.date_of_death} onChange={setD('date_of_death')} max={today()} required />
          </div>
          <div className="form-group">
            <label>Place (optional)</label>
            <input value={death.place} onChange={setD('place')} maxLength={200} placeholder="Hospital, home, village…" />
          </div>
        </div>
        <div className="form-group">
          <label>Note (optional)</label>
          <textarea rows={2} value={death.note} onChange={setD('note')} placeholder="Cause, circumstances, who informed you…" />
        </div>

        <div className="section-title">Who died?</div>
        {!ready && (
          <>
            <div className="form-group">
              <label>Find the citizen</label>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID number or phone…" autoFocus />
            </div>
            {searching && <Spinner label="Searching…" />}
            {results && !searching && (
              results.length === 0 ? (
                <p className="muted small">No living registered citizen matches “{q}”.</p>
              ) : (
                <ul className="attend-results">
                  {results.map((c) => (
                    <li key={c.id}>
                      <div>
                        <strong>{c.name}</strong>
                        <div className="muted small">ID {c.national_id}{c.isibo ? ` · isibo ${c.isibo}` : ''} · {c.village_name}</div>
                      </div>
                      <button type="button" className="btn btn-small" onClick={() => setChosen(c)}>Select</button>
                    </li>
                  ))}
                </ul>
              )
            )}
            <div className="info-strip" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
              <span>Person not registered?</span>
              <button type="button" className="link-btn" onClick={() => { setRegistering(true); setForm({ ...emptyNew }) }}>
                Add their details and report
              </button>
            </div>
          </>
        )}

        {ready && (
          <>
            {registering ? (
              <>
                <p className="muted small" style={{ marginTop: 0 }}>
                  Added to the registry of {user?.village_name ? `${user.village_name} village` : 'your village'} and marked deceased at once.
                </p>
                <div className="form-row">
                  <div className="form-group"><label>First name</label><input value={form.first_name} onChange={setF('first_name')} required /></div>
                  <div className="form-group"><label>Last name</label><input value={form.last_name} onChange={setF('last_name')} required /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>ID number</label><input value={form.national_id} onChange={setF('national_id')} maxLength={16} required /></div>
                  <div className="form-group"><label>Age</label><input type="number" min="1" max="130" value={form.age} onChange={setF('age')} required /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Isibo (optional)</label><input value={form.isibo} onChange={setF('isibo')} /></div>
                  <div className="form-group"><label>Phone (optional)</label><input value={form.phone} onChange={setF('phone')} maxLength={20} /></div>
                </div>
              </>
            ) : (
              <div className="loc-summary" style={{ marginBottom: '1rem' }}>
                <span><strong>{chosen.name}</strong> · ID {chosen.national_id}{chosen.isibo ? ` · isibo ${chosen.isibo}` : ''} · {chosen.village_name}</span>
                {!preselected && <button type="button" className="link-btn" onClick={() => setChosen(null)}>change</button>}
              </div>
            )}
            <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
              The citizen will be removed from the living citizens of the village, cell and sector and kept in the deceased register.
            </div>
          </>
        )}

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button className="btn btn-danger" disabled={busy || !ready} title={ready ? '' : 'Select or add the person first'}>
            {busy ? 'Saving…' : 'Report Deceased'}
          </button>
          {registering && !preselected && <button type="button" className="btn btn-outline-dark" onClick={() => setRegistering(false)}>Back to search</button>}
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </div>
        </form>
      </div>
    </div>
  )
}
