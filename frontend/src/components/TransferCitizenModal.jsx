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
          After the transfer the citizen leaves your list; the new village leader places them in an isibo.
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
            <button className="btn" disabled={busy || !loc.village}>{busy ? 'Transferring…' : 'Confirm Transfer'}</button>
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

// Small marker shown next to a transferred citizen's name.
export function TransferBadge({ citizen }) {
  if (!citizen?.transferred_from_village) return null
  if (citizen.awaiting_isibo) {
    return <span className="badge badge-pending badge-inline" title={`From ${citizen.transferred_from_village_name}`}>Transferred in · no isibo yet</span>
  }
  return <span className="badge badge-kind badge-inline">Transferred from {citizen.transferred_from_village_name}</span>
}
