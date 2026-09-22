import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Spinner from '../components/Spinner.jsx'

// System admin: see how much each part of the system stores and delete it in bulk — a few datasets,
// only records older than a date, or everything at once. Locations, settings and admin accounts are never touched.
export function formatBytes(n) {
  if (n === null || n === undefined) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

const fmtNum = (n) => Number(n || 0).toLocaleString()

export default function DataManagement({ user }) {
  const [data, setData] = useState(null)
  const [before, setBefore] = useState('') // only records older than this date (blank = all)
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null) // last purge summary
  const [confirming, setConfirming] = useState(null) // datasets awaiting the confirmation phrase

  const isAdmin = user?.is_admin_role || user?.is_superuser

  async function load(cutoff = before) {
    setLoading(true)
    setError('')
    try {
      setData(await api.dataOverview(cutoff))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (isAdmin) load() }, [isAdmin])

  // Re-count when the cutoff date changes so the admin sees exactly what would go
  useEffect(() => {
    if (!isAdmin || data === null) return
    const t = setTimeout(() => load(before), 300)
    return () => clearTimeout(t)
  }, [before])

  if (!isAdmin) {
    return <div className="alert alert-error">Only a system administrator can manage data.</div>
  }

  const datasets = data?.datasets || []
  const groups = [...new Set(datasets.map((d) => d.group))]
  const byKey = Object.fromEntries(datasets.map((d) => [d.key, d]))
  const totalRows = datasets.filter((d) => !['letters', 'attendances', 'orphan_files'].includes(d.key)).reduce((s, d) => s + d.rows, 0)
  const selectedRows = selected.reduce((s, k) => s + (byKey[k]?.rows || 0), 0)
  const selectedFiles = selected.reduce((s, k) => s + (byKey[k]?.files || 0), 0)
  const nothingSelected = selected.length === 0 || (selectedRows === 0 && selectedFiles === 0)

  function toggle(key) {
    setSelected((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]))
  }

  function toggleAll(on) {
    setSelected(on ? datasets.map((d) => d.key) : [])
  }

  return (
    <div>
      <div className="page-head dashboard-head">
        <div>
          <h1>Data Management</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            Free up the database and file storage by deleting records the system no longer needs.
          </p>
        </div>
        {data && (
          <div className="stat-card">
            <div className="stat"><span className="stat-label">Database</span><span className="stat-value stat-value-sm">{formatBytes(data.database_bytes)}</span></div>
            <div className="stat"><span className="stat-label">Files</span><span className="stat-value stat-value-sm">{formatBytes(data.storage.bytes)}</span></div>
            <div className="stat"><span className="stat-label">Records</span><span className="stat-value stat-value-sm">{fmtNum(totalRows)}</span></div>
          </div>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {result && (
        <div className="alert alert-success">
          <strong>Done.</strong> {fmtNum(result.rows)} record{result.rows === 1 ? '' : 's'} and {fmtNum(result.files)} file{result.files === 1 ? '' : 's'} deleted
          {result.bytes ? `, freeing ${formatBytes(result.bytes)} of storage` : ''}.
          <ul className="purge-summary">
            {result.results.map((r) => (
              <li key={r.key}>{r.label}: {fmtNum(r.rows)} records{r.files ? `, ${fmtNum(r.files)} files (${formatBytes(r.bytes)})` : ''}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="info-strip">
        <span>
          Deleting is permanent and cannot be undone. Location data, role permissions, system settings and administrator
          accounts are never deleted here. The database reuses the space freed by deleted rows for new records.
        </span>
      </div>

      <div className="card">
        <div className="filter-row date-filter">
          <div className="form-group" style={{ maxWidth: 260 }}>
            <label>Only records older than</label>
            <input type="date" value={before} onChange={(e) => setBefore(e.target.value)} max={new Date().toISOString().slice(0, 10)} />
          </div>
          <div className="form-group" style={{ alignSelf: 'flex-end', maxWidth: 'none', flex: '2 1 240px' }}>
            <span className="muted small">
              {before ? `Counts and deletions below apply to records created before ${new Date(before).toLocaleDateString()}.` : 'Leave blank to count and delete records of any date.'}
            </span>
          </div>
          {before && (
            <button type="button" className="btn btn-ghost btn-small" style={{ alignSelf: 'flex-end' }} onClick={() => setBefore('')}>Clear date</button>
          )}
        </div>

        {data === null ? (
          <Spinner label="Counting records…" />
        ) : (
          <>
            <div className="perm-group-head" style={{ marginTop: '0.5rem' }}>
              <label className="checkbox-row" style={{ cursor: 'pointer' }}>
                <input type="checkbox" checked={selected.length === datasets.length && datasets.length > 0}
                       onChange={(e) => toggleAll(e.target.checked)} />
                <span className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Select everything</span>
              </label>
              {loading && <Spinner inline size={18} label="Recounting…" />}
            </div>

            {groups.map((group) => (
              <div key={group} className="perm-group">
                <div className="perm-group-head">
                  <span className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>{group}</span>
                </div>
                {datasets.filter((d) => d.group === group).map((d) => {
                  const on = selected.includes(d.key)
                  const empty = d.rows === 0 && d.files === 0
                  return (
                    <label key={d.key} className={`perm-row data-row ${on ? 'perm-on' : ''} ${empty ? 'data-row-empty' : ''}`}>
                      <input type="checkbox" checked={on} onChange={() => toggle(d.key)} />
                      <span className="perm-text">
                        <span className="perm-desc">{d.label}</span>
                        <span className="muted small">{d.description}{!d.dated && before ? ' Not limited by the date.' : ''}</span>
                      </span>
                      <span className="data-counts">
                        {d.key !== 'letters' && d.key !== 'orphan_files' && <span className="data-count">{fmtNum(d.rows)} <em>records</em></span>}
                        {(d.files > 0 || d.key === 'letters' || d.key === 'orphan_files' || d.key === 'attachments') && (
                          <span className="data-count">{fmtNum(d.files)} <em>files</em></span>
                        )}
                      </span>
                    </label>
                  )
                })}
              </div>
            ))}

            <div className="btn-row" style={{ marginTop: '1.5rem', justifyContent: 'space-between' }}>
              <span className="muted small" style={{ alignSelf: 'center' }}>
                {selected.length === 0 ? 'Tick the data you want to remove.' :
                  `Selected: ${fmtNum(selectedRows)} record${selectedRows === 1 ? '' : 's'} and ${fmtNum(selectedFiles)} file${selectedFiles === 1 ? '' : 's'} in ${selected.length} dataset${selected.length === 1 ? '' : 's'}.`}
              </span>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-outline-dark" disabled={loading} onClick={() => load()}>Recount</button>
                <button type="button" className="btn btn-danger" disabled={nothingSelected || loading} onClick={() => setConfirming(selected)}>
                  Delete selected
                </button>
                <button type="button" className="btn btn-danger" disabled={loading || datasets.length === 0} onClick={() => setConfirming(datasets.map((d) => d.key))}>
                  Clear everything
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {confirming && data && (
        <ConfirmPurgeModal
          datasets={datasets.filter((d) => confirming.includes(d.key))}
          before={before}
          phrase={data.confirm_phrase}
          onClose={() => setConfirming(null)}
          onDone={(res) => {
            setConfirming(null)
            setResult(res)
            setSelected([])
            setData(res.overview)
            window.scrollTo({ top: 0, behavior: 'smooth' })
          }}
        />
      )}
    </div>
  )
}

function ConfirmPurgeModal({ datasets, before, phrase, onClose, onDone }) {
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const rows = datasets.reduce((s, d) => s + d.rows, 0)
  const files = datasets.reduce((s, d) => s + d.files, 0)
  const everything = datasets.length > 0 && !before && datasets.some((d) => d.key === 'accounts') && datasets.some((d) => d.key === 'citizens')

  async function run(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      onDone(await api.purgeData(datasets.map((d) => d.key), before, typed.trim()))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={busy ? undefined : onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ color: 'var(--danger)' }}>{everything ? 'Clear everything?' : 'Delete this data?'}</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          {before ? `Records created before ${new Date(before).toLocaleDateString()} in the datasets below` : 'All records in the datasets below'} will be
          permanently deleted, together with their stored files. This cannot be undone.
        </p>
        <ul className="purge-list">
          {datasets.map((d) => (
            <li key={d.key}>
              <span>{d.label}</span>
              <span className="muted small">
                {d.key !== 'letters' && d.key !== 'orphan_files' ? `${fmtNum(d.rows)} records` : ''}
                {d.files ? `${d.key !== 'letters' && d.key !== 'orphan_files' ? ' · ' : ''}${fmtNum(d.files)} files` : ''}
                {!d.rows && !d.files ? 'nothing to delete' : ''}
              </span>
            </li>
          ))}
        </ul>
        <p className="small"><strong>{fmtNum(rows)}</strong> records and <strong>{fmtNum(files)}</strong> files in total.</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={run}>
          <div className="form-group" style={{ maxWidth: 300 }}>
            <label>Type <code>{phrase}</code> to confirm</label>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={phrase} autoFocus autoComplete="off" />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn btn-danger" disabled={busy || typed.trim() !== phrase}>
              {busy ? 'Deleting…' : everything ? 'Yes, clear everything' : 'Yes, delete'}
            </button>
            <button type="button" className="btn btn-outline-dark" disabled={busy} onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}
