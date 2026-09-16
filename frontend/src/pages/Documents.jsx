import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, saveBlob } from '../api.js'
import Pagination, { DateFilter, inDateRange } from '../components/Pagination.jsx'

const PAGE_SIZE = 5

// Archive of every generated letter the user may see, with the date it was created
export default function Documents({ user }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [range, setRange] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.listDocuments().then(setItems).catch((err) => setError(err.message))
  }, [])

  // Back to the first page whenever the filters change
  useEffect(() => { setPage(1) }, [filter, range.from, range.to])

  async function download(url) {
    setError('')
    try {
      saveBlob(await api.downloadByUrl(url))
    } catch (err) {
      setError(err.message)
    }
  }

  const isLeader = ['village_leader', 'cell_leader', 'sector_leader'].includes(user?.role) || user?.is_admin_role || user?.is_superuser
  const visible = (items || [])
    .filter((d) => filter === 'all' || d.kind === filter)
    .filter((d) => inDateRange([d.created_at], range.from, range.to))
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageItems = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      <div className="page-head">
        <h1>{isLeader ? 'Issued Documents' : 'My Documents'}</h1>
        <div className="tabs" style={{ marginBottom: 0, borderBottom: 'none' }}>
          {[['all', 'All'], ['request', 'Letters'], ['announcement', 'Announcements']].map(([v, l]) => (
            <button key={v} className={`tab ${filter === v ? 'tab-active' : ''}`} onClick={() => setFilter(v)}>{l}</button>
          ))}
        </div>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <DateFilter from={range.from} to={range.to} onChange={setRange} />
        {items === null ? (
          <p className="muted">Loading…</p>
        ) : visible.length === 0 ? (
          <p className="muted">
            {items.length === 0
              ? 'No documents yet. Approved letters and saved announcements appear here with the date they were created.'
              : 'No documents match this filter.'}
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Created</th><th>Document</th><th>For / Subject</th>
                  {isLeader && <th>Issued by</th>}
                  <th>Download</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((d) => (
                  <tr key={`${d.kind}-${d.id}`}>
                    <td>
                      {new Date(d.created_at).toLocaleDateString()}
                      <div className="muted small">{new Date(d.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    </td>
                    <td>
                      <span className={`badge ${d.kind === 'request' ? 'badge-approved' : 'badge-kind'}`}>{d.kind === 'request' ? 'Letter' : 'Announcement'}</span>
                      <div style={{ marginTop: '0.3rem' }}>{d.title}</div>
                    </td>
                    <td>{d.subject || '—'}{d.kind === 'request' && <div><Link to={d.link} className="small">View request #{d.id}</Link></div>}</td>
                    {isLeader && <td>{d.created_by || '—'}</td>}
                    <td className="actions-cell">
                      <button className="btn btn-small" onClick={() => download(d.pdf_url)}>PDF</button>
                      <button className="btn btn-small btn-outline-dark" onClick={() => download(d.docx_url)}>Word</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="document" onChange={setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
