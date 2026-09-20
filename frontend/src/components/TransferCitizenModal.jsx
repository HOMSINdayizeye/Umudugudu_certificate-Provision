import { useEffect, useState } from 'react'
import { api } from '../api.js'
import LocationSelect from './LocationSelect.jsx'

// Village/cell leader moves a citizen to the village they now live in.
export function TransferCitizenModal({ citizen, onClose, onDone }) {
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!loc.village) {
      setError('Choose the destination down to the village.')
      return
    }
    if (String(loc.village) === String(citizen.village)) {
      setError('The citizen already lives in this village.')
      return
    }
    setBusy(true)
    try {
      const transfer = await api.transferCitizen(citizen.id, { village: loc.village, note })
      onDone(transfer)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Transfer {citizen.name}</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Currently in <strong>{citizen.village_name}</strong>{citizen.isibo ? `, isibo ${citizen.isibo}` : ''}.
          The receiving village leader is notified and must accept the transfer. Until then the citizen stays in
          your list marked as pending; once accepted they move and can be placed in an isibo there.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="section-title">Where is the citizen moving to?</div>
          <LocationSelect value={loc} onChange={setLoc} progressive />
          <div className="form-group" style={{ marginTop: '1rem' }}>
            <label>Note (optional)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
                   placeholder="Reason or remark for the receiving leader" />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy || !loc.village}>{busy ? 'Sending…' : 'Send Transfer Request'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Destination village leader puts a transferred citizen into one of the village's isibos.
export function PlaceCitizenModal({ citizen, onClose, onDone }) {
  const [isibo, setIsibo] = useState(citizen.isibo || '')
  const [known, setKnown] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.villageIsibos(citizen.village).then(setKnown).catch(() => {})
  }, [citizen.village])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const updated = await api.placeCitizen(citizen.id, isibo.trim())
      onDone(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Place {citizen.name} in an isibo</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Transferred from <strong>{citizen.transferred_from_village_name || 'another village'}</strong>
          {citizen.transferred_from_isibo ? ` (isibo ${citizen.transferred_from_isibo})` : ''}
          {citizen.transferred_at ? ` on ${new Date(citizen.transferred_at).toLocaleDateString()}` : ''}.
          The isibo leader with this isibo name will see the citizen in their list.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Isibo in {citizen.village_name}</label>
            <input list="known-isibos" value={isibo} onChange={(e) => setIsibo(e.target.value)} required
                   placeholder="Type or pick an isibo name" autoFocus />
            <datalist id="known-isibos">
              {known.map((n) => <option key={n} value={n} />)}
            </datalist>
            {known.length > 0 && (
              <div className="field-hint muted">Known isibos here: {known.join(', ')}</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy || !isibo.trim()}>{busy ? 'Saving…' : 'Add to Isibo'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Destination village leader accepts a pending transfer, optionally placing the citizen in an isibo right away.
export function AcceptTransferModal({ transfer, onClose, onDone }) {
  const [isibo, setIsibo] = useState('')
  const [known, setKnown] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.villageIsibos(transfer.to_village).then(setKnown).catch(() => {})
  }, [transfer.to_village])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      onDone(await api.acceptTransfer(transfer.id, isibo.trim()))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Accept {transfer.citizen_name} into {transfer.to_village_name}?</h2>
        <dl className="detail-grid">
          <dt>ID number</dt><dd>{transfer.national_id}</dd>
          <dt>Phone</dt><dd>{transfer.phone || '—'}</dd>
          <dt>Coming from</dt><dd>{transfer.from_village_name}{transfer.from_isibo ? ` · isibo ${transfer.from_isibo}` : ''}</dd>
          <dt>Sent by</dt><dd>{transfer.transferred_by_name || '—'}{transfer.transferred_at ? ` on ${new Date(transfer.transferred_at).toLocaleDateString()}` : ''}</dd>
          {transfer.note && <><dt>Note</dt><dd>{transfer.note}</dd></>}
        </dl>
        <p className="muted small">Once accepted the citizen becomes a citizen of your village and leaves the sender’s list. Where they came from stays on their record.</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Isibo (optional — you can place them later)</label>
            <input list="accept-known-isibos" value={isibo} onChange={(e) => setIsibo(e.target.value)}
                   placeholder="Type or pick an isibo name" autoFocus />
            <datalist id="accept-known-isibos">
              {known.map((n) => <option key={n} value={n} />)}
            </datalist>
            {known.length > 0 && (
              <div className="field-hint muted">Known isibos here: {known.join(', ')}</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn" disabled={busy}>{busy ? 'Accepting…' : 'Accept Transfer'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Destination village leader declines a pending transfer; the citizen stays where they are.
export function DeclineTransferModal({ transfer, onClose, onDone }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      onDone(await api.rejectTransfer(transfer.id, note.trim()))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Decline the transfer of {transfer.citizen_name}?</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          The citizen stays in <strong>{transfer.from_village_name}</strong> and its leader is told the transfer was declined.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Reason (optional)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
                   placeholder="Shown to the sending leader" autoFocus />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn btn-danger" disabled={busy}>{busy ? 'Declining…' : 'Decline Transfer'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={onClose}>Keep pending</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Small marker shown next to a transferred citizen's name.
export function TransferBadge({ citizen }) {
  if (citizen?.pending_transfer) {
    return <span className="badge badge-pending badge-inline" title={`Waiting for ${citizen.pending_transfer.to_village_name} to accept`}>Transfer pending → {citizen.pending_transfer.to_village_name}</span>
  }
  if (!citizen?.transferred_from_village) return null
  if (citizen.awaiting_isibo) {
    return <span className="badge badge-pending badge-inline" title={`From ${citizen.transferred_from_village_name}`}>Transferred in · no isibo yet</span>
  }
  return <span className="badge badge-kind badge-inline">Transferred from {citizen.transferred_from_village_name}</span>
}
