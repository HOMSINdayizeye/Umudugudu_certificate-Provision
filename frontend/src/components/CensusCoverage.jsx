import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import Spinner from './Spinner.jsx'

export const LEVEL_LABEL = { country: 'Country', province: 'Province', district: 'District', sector: 'Sector', cell: 'Cell', village: 'Village' }
export const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toLocaleString())

export function CoverageBar({ pct }) {
  if (pct === null || pct === undefined) return <span className="muted small">no estimate</span>
  const width = Math.min(100, pct)
  const tone = pct >= 90 ? 'high' : pct >= 50 ? 'mid' : 'low'
  return (
    <div className="coverage-bar" title={`${pct}% of the estimated population is registered`}>
      <div className={`coverage-fill coverage-${tone}`} style={{ width: `${width}%` }} />
      <span className="coverage-pct">{pct}%</span>
    </div>
  )
}

// Rows of registered citizens vs estimated population. `rows` come from /census/coverage/ (chain or children).
export function CoverageTable({ rows, year, censusYear, showLevel = true, onPick, onEdit }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table coverage-table">
        <thead>
          <tr>
            {showLevel && <th>Level</th>}
            <th>Area</th>
            <th>Registered</th>
            <th>Census {censusYear}</th>
            <th>Estimated {year}</th>
            <th>Still to register</th>
            <th>Coverage</th>
            {onEdit && <th></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.location} className={onPick ? 'row-clickable' : ''} onClick={onPick ? () => onPick(r) : undefined}>
              {showLevel && <td className="muted small">{LEVEL_LABEL[r.level] || r.level}</td>}
              <td>
                <strong>{r.name}</strong>
                {r.method === 'local' && <span className="badge badge-kind badge-inline">local count</span>}
                {r.method === 'derived' && <span className="badge badge-citizen badge-inline">estimate</span>}
              </td>
              <td><strong>{fmt(r.registered)}</strong></td>
              <td>{fmt(r.census)}</td>
              <td>{fmt(r.estimate)}</td>
              <td>{r.gap === null || r.gap === undefined ? '—' : r.gap > 0 ? fmt(r.gap) : <span className="muted">complete</span>}</td>
              <td style={{ minWidth: 140 }}><CoverageBar pct={r.coverage_pct} /></td>
              {onEdit && (
                <td className="actions-cell">
                  {['cell', 'village'].includes(r.level) && (
                    <button type="button" className="btn btn-small btn-ghost" onClick={(e) => { e.stopPropagation(); onEdit(r) }}>
                      {r.method === 'local' ? 'Edit count' : 'Local count'}
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Modal: a leader enters the real population of a cell or village to replace the derived estimate
export function LocalCountModal({ row, onClose, onSaved }) {
  const local = row.local_count || {}
  const [form, setForm] = useState({
    total: local.total ?? row.estimate ?? '', households: local.households ?? row.households ?? '',
    year: local.year ?? new Date().getFullYear(), note: local.note || '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function save(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api.setLocalCount({ location: row.location, ...form, households: form.households || null })
      onSaved(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm(`Remove the local count of ${row.name}? The NISR-based estimate will be used again.`)) return
    setBusy(true)
    try {
      onSaved(await api.deleteLocalCount(row.location))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Population of {row.name} {LEVEL_LABEL[row.level]?.toLowerCase()}</h2>
        <p className="muted small">
          NISR publishes census counts down to sector level only. The current figure for this {row.level} is an estimate
          ({fmt(row.estimate)}). If your office has counted the people living here, enter that count and it will be used instead.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={save}>
          <div className="form-row">
            <div className="form-group">
              <label>People living here</label>
              <input type="number" min="0" value={form.total} onChange={set('total')} required />
            </div>
            <div className="form-group">
              <label>Households (optional)</label>
              <input type="number" min="0" value={form.households} onChange={set('households')} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Year counted</label>
              <input type="number" min="2022" max={new Date().getFullYear() + 1} value={form.year} onChange={set('year')} required />
            </div>
            <div className="form-group">
              <label>Note (optional)</label>
              <input value={form.note} onChange={set('note')} placeholder="e.g. Isibo leaders' headcount, March" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save count'}</button>
            {row.local_count && <button type="button" className="btn btn-danger" disabled={busy} onClick={remove}>Remove local count</button>}
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Card showing registered citizens against the NISR census for an area, the areas above it and its sub-areas.
// location: a village/cell/sector/district id (defaults to the user's own area); refreshKey reloads after changes.
export default function CensusCoverage({ location, refreshKey, title = 'Registered citizens vs population', showChildren = true, compact = false, onChanged }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')

  async function load() {
    setError('')
    try {
      setData(await api.censusCoverage(location))
    } catch (err) {
      setError(err.message)
      setData(null)
    }
  }

  useEffect(() => { load() }, [location, refreshKey])

  if (error) return <div className="alert alert-error">{error}</div>
  if (!data) return <div className="card"><Spinner label="Comparing with the census…" /></div>

  const chain = [...data.chain]
  const here = chain[0]
  const children = data.children || []
  const childLabel = { village: 'villages', cell: 'cells', sector: 'sectors', district: 'districts' }[data.child_level]

  return (
    <div className="card census-card">
      <div className="page-head" style={{ marginBottom: '0.5rem' }}>
        <div>
          <h2 className="card-title" style={{ margin: 0 }}>{title}</h2>
          <span className="muted small">
            NISR 2022 census, grown to {data.year} with the district projection. {here?.registered !== undefined && here?.estimate
              ? <>About <strong>{fmt(here.estimate)}</strong> people live in {here.name}; <strong>{fmt(here.registered)}</strong> are registered{here.gap > 0 ? <>, <strong>{fmt(here.gap)}</strong> still to register</> : ''}.</>
              : ''}
          </span>
        </div>
        {!compact && <Link to={`/census?location=${data.location}`} className="btn btn-small btn-ghost">Census details</Link>}
      </div>
      {message && <div className="alert alert-success">{message}</div>}

      <CoverageTable rows={chain} year={data.year} censusYear={data.census_year} onEdit={data.can_manage ? setEditing : undefined} />

      {showChildren && children.length > 0 && (
        <>
          <div className="section-title">By {childLabel} of {data.name}</div>
          <CoverageTable rows={children} year={data.year} censusYear={data.census_year} showLevel={false}
                         onEdit={data.can_manage ? setEditing : undefined} />
        </>
      )}

      <p className="muted small" style={{ marginBottom: 0 }}>
        <em>estimate</em>: the sector's census population shared equally among its villages, because NISR publishes no
        cell or village counts. <em>local count</em>: a figure a leader entered for this area.
      </p>

      {editing && (
        <LocalCountModal
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={async (res) => { setEditing(null); setMessage(res.detail); await load(); onChanged?.() }}
        />
      )}
    </div>
  )
}
