import { useState } from 'react'
import { Link } from 'react-router-dom'
import SplitModal from './SplitModal.jsx'

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

// The code split into one box per character, coloured by outcome, with a copy button
export function CodeDigits({ code, tone }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked; the code is still readable on screen */ }
  }
  return (
    <div className={`code-digits-wrap ${tone || ''}`}>
      <div className="code-digits" aria-label={`Code ${code}`}>
        {[...code].map((ch, i) => <span key={i} className="code-digit">{ch}</span>)}
      </div>
      <button type="button" className="code-copy" onClick={copy}>{copied ? 'Copied ✓' : 'Copy code'}</button>
    </div>
  )
}

// Outcome banner: genuine, replaced by a newer code, or not one of ours
function CodeStatus({ item }) {
  if (item.valid === false) {
    return (
      <div className="code-status code-status-bad" role="alert">
        <span className="code-status-icon">✕</span>
        <div><strong>Not a valid code</strong><span>{item.detail || 'No letter issued by this system carries this code.'}</span></div>
      </div>
    )
  }
  if (item.superseded) {
    const latest = item.history?.[item.history.length - 1]?.code
    return (
      <div className="code-status code-status-warn" role="alert">
        <span className="code-status-icon">!</span>
        <div><strong>Replaced by a newer code</strong><span>This code was valid but a later endorsement issued <span className="code-inline">{latest}</span>. Ask for the latest copy of the letter.</span></div>
      </div>
    )
  }
  return (
    <div className="code-status code-status-ok" role="status">
      <span className="code-status-icon">✓</span>
      <div><strong>Genuine document</strong><span>This code was issued by Umudugudu Certify when the letter was approved.</span></div>
    </div>
  )
}

// Details of the letter linked to a code, or the failed lookup for a code that is not ours
export function CodeModal({ item, onClose }) {
  if (!item) return null
  const invalid = item.valid === false
  const tone = invalid ? 'bad' : item.superseded ? 'warn' : 'ok'
  return (
    <SplitModal
      title="Verification code"
      subtitle={invalid ? 'We checked this code against every letter issued by this system.' : 'Compare it with the code printed in the footer of the letter.'}
      headline="Every letter carries a code."
      tagline="A code is issued the moment a letter is approved, so anyone presented with it can confirm it came from this office."
      onClose={onClose}
    >
      <CodeDigits code={item.code} tone={tone} />
      <CodeStatus item={item} />
      {!invalid && (
        <>
          <dl className="detail-grid split-details">
            <dt>Document</dt><dd>{item.cert_type_display}</dd>
            <dt>Issued to</dt><dd>{item.applicant || '—'}</dd>
            {item.village_name && (<><dt>Village</dt><dd>{item.village_name}</dd></>)}
            {item.status_display && (<><dt>Stage</dt><dd><span className={`badge badge-${item.status}`}>{item.status_display}</span></dd></>)}
            <dt>Approved</dt><dd>{item.approved_at ? new Date(item.approved_at).toLocaleString() : '—'}</dd>
            <dt>Approved by</dt><dd>{item.approved_by || '—'}</dd>
            {(item.history || []).length > 0 && (
              <>
                <dt>Code history</dt>
                <dd>{item.history.map((h, i) => <div key={i}><span className="code-inline">{h.code}</span> <span className="muted small">{h.level} · {h.by} · {new Date(h.at).toLocaleDateString()}</span></div>)}</dd>
              </>
            )}
            {item.in_scope === false && (<><dt>Note</dt><dd>This letter was issued outside your area, so only the summary is shown.</dd></>)}
          </dl>
          {item.in_scope !== false && (
            <Link to={`/requests/${item.request_id}`} className="btn btn-block" style={{ marginTop: '1.25rem' }} onClick={onClose}>Open request #{item.request_id}</Link>
          )}
        </>
      )}
      <p className="split-note">Codes are shared with cell and village leaders only. Do not give them to applicants.</p>
    </SplitModal>
  )
}
