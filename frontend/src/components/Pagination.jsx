// Page buttons shared by the document and announcement lists
export default function Pagination({ page, totalPages, total, label = 'item', onChange }) {
  if (totalPages <= 1) return null
  return (
    <div className="pagination">
      <button className="page-btn" disabled={page === 1} onClick={() => onChange(page - 1)}>‹ Prev</button>
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
        <button key={n} className={n === page ? 'page-btn page-btn-active' : 'page-btn'} onClick={() => onChange(n)}>{n}</button>
      ))}
      <button className="page-btn" disabled={page === totalPages} onClick={() => onChange(page + 1)}>Next ›</button>
      <span className="muted page-info">Page {page} of {totalPages} — {total} {label}{total === 1 ? '' : 's'}</span>
    </div>
  )
}

// From/To date inputs; onChange receives {from, to} as YYYY-MM-DD strings
export function DateFilter({ from, to, onChange }) {
  return (
    <div className="filter-row date-filter">
      <div className="form-group">
        <label>From date</label>
        <input type="date" value={from} onChange={(e) => onChange({ from: e.target.value, to })} />
      </div>
      <div className="form-group">
        <label>To date</label>
        <input type="date" value={to} onChange={(e) => onChange({ from, to: e.target.value })} />
      </div>
      {(from || to) && (
        <button type="button" className="btn btn-small btn-ghost" onClick={() => onChange({ from: '', to: '' })}>Clear</button>
      )}
    </div>
  )
}

// True when any of the given dates (Date objects or ISO strings) falls inside the range
export function inDateRange(dates, from, to) {
  if (!from && !to) return true
  return dates.filter(Boolean).some((d) => {
    const day = new Date(d)
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    return (!from || key >= from) && (!to || key <= to)
  })
}
