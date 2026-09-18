import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Pagination from '../components/Pagination.jsx'
import { CodeCard, CodeModal } from '../components/CodeCards.jsx'
import ExportButtons from '../components/ExportButtons.jsx'

const PAGE_SIZE = 12

// All verification codes the leader may see, plus a box to verify a code someone presents
export default function Codes() {
  const [items, setItems] = useState(null)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [verify, setVerify] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listCodes().then(setItems).catch((err) => setError(err.message))
  }, [])

  useEffect(() => { setPage(1) }, [q])

  async function check(e) {
    e.preventDefault()
    if (!verify.trim()) return
    setError(''); setChecking(true)
    try {
      setSelected(await api.lookupCode(verify))
    } catch (err) {
      // 404 means the code is not one of ours; show that clearly in the same modal
      setSelected({ code: verify.trim(), valid: false, detail: err.message })
    } finally {
      setChecking(false)
    }
  }

  const needle = q.trim().toLowerCase()
  const visible = (items || []).filter((i) => !needle || i.code.toLowerCase().includes(needle) || (i.applicant || '').toLowerCase().includes(needle))
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageItems = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      <div className="page-head"><h1>Verification Codes</h1></div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="two-col" style={{ marginBottom: '1.25rem' }}>
        <form className="card" onSubmit={check}>
          <h2 className="card-title">Verify a document</h2>
          <p className="muted small" style={{ marginTop: 0 }}>Type the code printed in the footer of a letter to confirm it was issued by this system.</p>
          <div className="form-group">
            <label>Verification code</label>
            <input value={verify} onChange={(e) => setVerify(e.target.value)} placeholder="e.g. 1109030905" />
          </div>
          <button className="btn" disabled={checking || !verify.trim()}>{checking ? 'Checking…' : 'Verify'}</button>
        </form>
        <div className="card">
          <h2 className="card-title">Search issued codes</h2>
          <div className="form-group">
            <label>Code or applicant name</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" />
          </div>
          <p className="muted small">{items ? `${visible.length} code${visible.length === 1 ? '' : 's'}` : 'Loading…'}</p>
        </div>
      </div>

      <div className="card">
        {items === null ? (
          <p className="muted">Loading…</p>
        ) : visible.length === 0 ? (
          <p className="muted">No codes yet. A code is issued every time a letter is approved.</p>
        ) : (
          <>
            <ExportButtons
              title="Verification codes"
              columns={['Code', 'Document', 'Issued to', 'Village', 'Stage', 'Approved', 'Approved by']}
              rows={visible.map((i) => [i.code, i.cert_type_display, i.applicant || '', i.village_name || '', i.status_display || '',
                i.approved_at ? new Date(i.approved_at).toLocaleDateString() : '', i.approved_by || ''])}
            />
            <div className="code-grid">
              {pageItems.map((i) => <CodeCard key={i.code} item={i} onOpen={setSelected} />)}
            </div>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="code" onChange={setPage} />
          </>
        )}
      </div>
      <CodeModal item={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
