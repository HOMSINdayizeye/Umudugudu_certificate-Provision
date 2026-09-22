import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { CodeModal } from '../components/CodeCards.jsx'
import { CodesSummaryCard, CodesBrowser } from '../components/CodesByType.jsx'
import CountUp from '../components/CountUp.jsx'
import ExportButtons from '../components/ExportButtons.jsx'
import LeaderWorkCard from '../components/LeaderWorkCard.jsx'
import Spinner from '../components/Spinner.jsx'

// Each summary number counts up in turn: Pending, then Approved, then Rejected, then Total
const COUNT_MS = 550

// Which request status each leader role can act on
const ACTIONABLE_STATUS = {
  village_leader: 'pending',
  cell_leader: 'village_approved',
  sector_leader: 'cell_approved',
}

export function canActOn(user, request) {
  if (!user) return false
  if (user.is_admin_role || user.is_superuser) {
    return !['approved', 'denied'].includes(request.status)
  }
  return ACTIONABLE_STATUS[user.role] === request.status && request.user.id !== user.id
}

const LEADER_ROLES = Object.keys(ACTIONABLE_STATUS)

const PAGE_SIZE = 5

export default function Dashboard({ user }) {
  const [requests, setRequests] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  const isLeader = LEADER_ROLES.includes(user?.role)
  const isAdmin = user?.is_admin_role || user?.is_superuser
  const [codes, setCodes] = useState([])
  const [selectedCode, setSelectedCode] = useState(null)
  const [browsingCodes, setBrowsingCodes] = useState(false)

  // All verification codes for leaders and admins, shown as one summary card
  useEffect(() => {
    if (isLeader || isAdmin) api.listCodes().then(setCodes).catch(() => {})
  }, [isLeader, isAdmin])

  async function load() {
    try {
      setRequests(await api.listRequests())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function act(id, action) {
    setError('')
    try {
      await api.actOnRequest(id, action)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const title = isAdmin
    ? 'All Document Requests'
    : isLeader
      ? `Document requests in your ${user.role.replace('_leader', '')}`
      : 'My Document Requests'

  const totalPages = Math.max(1, Math.ceil(requests.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const pageRequests = requests.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  return (
    <div>
      <div className="page-head dashboard-head">
        <div>
          <h1>{title}</h1>
          {!isAdmin && !isLeader && <Link to="/submit" className="btn" style={{ marginTop: '0.75rem' }}>Apply for a Document</Link>}
        </div>
        {!loading && (
          <div className="stat-card" aria-label="Request summary">
            {[
              ['Pending', requests.filter((r) => r.status === 'pending').length],
              ['Approved', requests.filter((r) => ['village_approved', 'cell_approved', 'approved'].includes(r.status)).length],
              ['Rejected', requests.filter((r) => r.status === 'denied').length],
              ['Total', requests.length],
            ].map(([label, value], i) => (
              <div className="stat" key={label}>
                <span className="stat-value"><CountUp value={value} duration={COUNT_MS} delay={i * COUNT_MS} /></span>
                <span className="stat-label">{label}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {isLeader && <LeaderWorkCard user={user} />}

      {(isLeader || isAdmin) && <CodesSummaryCard codes={codes} onOpen={() => setBrowsingCodes(true)} />}

      <div className="card">
        {loading ? (
          <Spinner label="Loading requests…" />
        ) : requests.length === 0 ? (
          <p className="muted">{isAdmin || isLeader ? 'No document requests yet.' : 'No requests yet. Click "Apply for a Document" to submit one.'}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title={title}
              columns={['#', 'Requested by', 'Email', 'Document', 'Applicant', 'Submitted', 'Status', 'Approved by']}
              rows={requests.map((r, i) => [i + 1, `${r.user.first_name} ${r.user.last_name}`.trim() || r.user.username, r.user.email, r.cert_type_display,
                r.details?.full_name || '', new Date(r.created_at).toLocaleDateString(), r.status_display, r.approved_by_name || ''])}
            />
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  {(isAdmin || isLeader) && <th>Requested by</th>}
                  <th>Type</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pageRequests.map((r, idx) => (
                  <tr key={r.id}>
                    <td>{(currentPage - 1) * PAGE_SIZE + idx + 1}</td>
                    {(isAdmin || isLeader) && (
                      <td>{r.user.first_name} {r.user.last_name} ({r.user.email})</td>
                    )}
                    <td>{r.cert_type_display}</td>
                    <td>{new Date(r.created_at).toLocaleDateString()}</td>
                    <td><span className={`badge badge-${r.status}`}>{r.status_display}</span></td>
                    <td>
                      <Link to={`/requests/${r.id}`} className="btn btn-small">{canActOn(user, r) ? 'Review' : 'View'}</Link>
                      {r.attachments?.length > 0 && <span className="muted small" title="Attached documents"> 📎{r.attachments.length}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="page-btn"
                  disabled={currentPage === 1}
                  onClick={() => setPage(currentPage - 1)}
                >
                  ‹ Prev
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    className={n === currentPage ? 'page-btn page-btn-active' : 'page-btn'}
                    onClick={() => setPage(n)}
                  >
                    {n}
                  </button>
                ))}
                <button
                  className="page-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Next ›
                </button>
                <span className="muted page-info">
                  Page {currentPage} of {totalPages} — {requests.length} request(s)
                </span>
              </div>
            )}
          </div>
        )}
      </div>
      {browsingCodes && <CodesBrowser codes={codes} onClose={() => setBrowsingCodes(false)} onOpenCode={setSelectedCode} />}
      <CodeModal item={selectedCode} onClose={() => setSelectedCode(null)} />
    </div>
  )
}
