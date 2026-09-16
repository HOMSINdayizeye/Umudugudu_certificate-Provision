import { Link } from 'react-router-dom'

const TYPE_TILE = { conduct: '', residence: 'green', stolen_computer: 'amber', community: 'purple', other: '' }

// One verification code as a card; click to open its details
export function CodeCard({ item, onOpen }) {
  return (
    <button type="button" className="code-card" onClick={() => onOpen(item)}>
      <span className={`code-chip ${TYPE_TILE[item.cert_type] || ''}`}>{item.cert_type_display}</span>
      <span className="code-value">{item.code}</span>
      <span className="code-applicant">{item.applicant || '—'}</span>
      <span className="muted small">
        {item.village_name ? `${item.village_name} · ` : ''}
        {item.approved_at ? new Date(item.approved_at).toLocaleDateString() : ''}
      </span>
    </button>
  )
}

// Details of the letter linked to a code
export function CodeModal({ item, onClose }) {
  if (!item) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Verification code">
        <div className="viewer-head" style={{ padding: 0, border: 'none', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Verification code</h2>
          <button className="btn btn-small btn-ghost" onClick={onClose}>Close ✕</button>
        </div>
        <div className="code-big">{item.code}</div>
        {item.valid === false ? (
          <div className="alert alert-error" style={{ marginTop: '1rem' }}>{item.detail}</div>
        ) : (
          <>
            <dl className="detail-grid" style={{ marginTop: '1.25rem' }}>
              <dt>Document</dt><dd>{item.cert_type_display}</dd>
              <dt>Issued to</dt><dd>{item.applicant || '—'}</dd>
              {item.village_name && (<><dt>Village</dt><dd>{item.village_name}</dd></>)}
              <dt>Approved</dt><dd>{item.approved_at ? new Date(item.approved_at).toLocaleString() : '—'}</dd>
              <dt>Approved by</dt><dd>{item.approved_by || '—'}</dd>
              {item.in_scope === false && (<><dt>Note</dt><dd>This letter was issued outside your area, so only the summary is shown.</dd></>)}
            </dl>
            {item.in_scope !== false && (
              <div className="btn-row" style={{ marginTop: '1.25rem' }}>
                <Link to={`/requests/${item.request_id}`} className="btn" onClick={onClose}>Open request #{item.request_id}</Link>
              </div>
            )}
          </>
        )}
        <p className="muted small" style={{ marginTop: '1rem' }}>Codes are shared with cell and village leaders only. Do not give them to applicants.</p>
      </div>
    </div>
  )
}
