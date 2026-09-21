import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CodeCard } from './CodeCards.jsx'
import Pagination from './Pagination.jsx'

const PAGE_SIZE = 9
const TYPE_TILE = { conduct: '', residence: 'green', stolen_computer: 'amber', community: 'purple', other: '' }

// Codes bucketed by the document type they were issued for, biggest group first
export function groupByType(codes) {
  const map = new Map()
  for (const c of codes) {
    const g = map.get(c.cert_type) || { type: c.cert_type, label: c.cert_type_display, items: [] }
    g.items.push(c)
    map.set(c.cert_type, g)
  }
  return [...map.values()].sort((a, b) => b.items.length - a.items.length)
}

// Single dashboard card: total issued codes plus a count per document type; click to browse them
export function CodesSummaryCard({ codes, onOpen }) {
  const groups = useMemo(() => groupByType(codes), [codes])
  return (
    <div className="card codes-summary" style={{ marginBottom: '1.25rem' }}>
      <div className="page-head" style={{ marginBottom: '0.75rem' }}>
        <h2 className="card-title" style={{ margin: 0 }}>Verification codes</h2>
        <Link to="/codes" className="arrow-link">Verify a code →</Link>
      </div>
      {codes.length === 0 ? (
        <p className="muted small">No codes yet. A code is issued every time a letter is approved.</p>
      ) : (
        <button type="button" className="codes-summary-btn" onClick={onOpen} aria-label="Browse all verification codes">
          <div className="codes-summary-total">
            <span className="stat-value">{codes.length}</span>
            <span className="stat-label">code{codes.length === 1 ? '' : 's'} issued</span>
          </div>
          <div className="codes-summary-types">
            {groups.map((g) => (
              <span key={g.type} className="codes-summary-type">
                <span className={`code-chip ${TYPE_TILE[g.type] || ''}`}>{g.label}</span>
                <strong>{g.items.length}</strong>
              </span>
            ))}
          </div>
          <span className="arrow-link">Browse by request type →</span>
        </button>
      )}
    </div>
  )
}

// Modal listing every code, one tab per document type; clicking a code opens its details
export function CodesBrowser({ codes, onClose, onOpenCode }) {
  const groups = useMemo(() => groupByType(codes), [codes])
  const [tab, setTab] = useState('all')
  const [page, setPage] = useState(1)

  const visible = tab === 'all' ? codes : (groups.find((g) => g.type === tab)?.items || [])
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageItems = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  function pick(next) { setTab(next); setPage(1) }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal codes-browser" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="All verification codes">
        <div className="viewer-head" style={{ padding: 0, border: 'none', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Verification codes</h2>
          <button className="btn btn-small btn-ghost" onClick={onClose}>Close ✕</button>
        </div>
        <div className="tabs codes-tabs">
          <button type="button" className={tab === 'all' ? 'tab tab-active' : 'tab'} onClick={() => pick('all')}>All <span className="tab-count">{codes.length}</span></button>
          {groups.map((g) => (
            <button key={g.type} type="button" className={tab === g.type ? 'tab tab-active' : 'tab'} onClick={() => pick(g.type)}>
              {g.label} <span className="tab-count">{g.items.length}</span>
            </button>
          ))}
        </div>
        {visible.length === 0 ? (
          <p className="muted">No codes for this request type.</p>
        ) : (
          <>
            <div className="code-grid">
              {pageItems.map((c) => <CodeCard key={c.code} item={c} onOpen={onOpenCode} />)}
            </div>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="code" onChange={setPage} />
          </>
        )}
        <div className="btn-row" style={{ marginTop: '1.25rem', justifyContent: 'space-between' }}>
          <p className="muted small" style={{ margin: 0 }}>Codes are shared with cell and village leaders only. Do not give them to applicants.</p>
          <Link to="/codes" className="arrow-link" onClick={onClose}>Search & verify →</Link>
        </div>
      </div>
    </div>
  )
}
