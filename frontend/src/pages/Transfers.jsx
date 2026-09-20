import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Spinner from '../components/Spinner.jsx'
import { PlaceCitizenModal, AcceptTransferModal, DeclineTransferModal } from '../components/TransferCitizenModal.jsx'

const STATUS_LABEL = {
  pending: 'Awaiting confirmation',
  rejected: 'Declined',
  cancelled: 'Cancelled',
  awaiting_isibo: 'Accepted · awaiting isibo',
  placed: 'Accepted · placed in isibo',
  moved_on: 'Moved again',
}
const STATUS_CLASS = {
  pending: 'badge-pending', rejected: 'badge-denied', cancelled: 'badge-denied',
  awaiting_isibo: 'badge-pending', placed: 'badge-approved', moved_on: 'badge-moved_on',
}

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')

// Leaders' view of citizens moving between villages: requests to confirm, who arrived (to place) and who left.
export default function Transfers({ user }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [placing, setPlacing] = useState(null)
  const [accepting, setAccepting] = useState(null)
  const [declining, setDeclining] = useState(null)
  const [cancelling, setCancelling] = useState(null)
  const [tab, setTab] = useState('incoming')

  async function load() {
    setError('')
    try {
      setData(await api.listTransfers())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  async function cancel(t) {
    setError('')
    setCancelling(t.id)
    try {
      await api.cancelTransfer(t.id)
      setMessage(`Transfer of ${t.citizen_name} to ${t.to_village_name} cancelled. They stay in your list.`)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setCancelling(null)
    }
  }

  const areaLabel = user?.role === 'village_leader' ? 'your village' : user?.role === 'cell_leader' ? 'your cell'
    : user?.role === 'sector_leader' ? 'your sector' : 'the area'
  const pendingIn = data?.pending_in || []
  const awaiting = data?.incoming.filter((c) => c.awaiting_isibo) || []
  const placed = data?.incoming.filter((c) => !c.awaiting_isibo) || []
  const incomingCount = pendingIn.length + awaiting.length

  return (
    <div>
      <div className="page-head">
        <h1>Citizen Transfers</h1>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="tabs">
        <button className={tab === 'incoming' ? 'tab tab-active' : 'tab'} onClick={() => setTab('incoming')}>
          Transferred in{incomingCount > 0 ? ` (${incomingCount} to act on)` : ''}
        </button>
        <button className={tab === 'outgoing' ? 'tab tab-active' : 'tab'} onClick={() => setTab('outgoing')}>
          Transferred out{data ? ` (${data.outgoing.length})` : ''}
        </button>
      </div>

      {!data ? (
        <div className="card"><Spinner label="Loading transfers…" /></div>
      ) : tab === 'incoming' ? (
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Waiting for your confirmation ({pendingIn.length})</div>
          <p className="muted small">
            Another leader wants to move these citizens into {areaLabel}. They stay in their current village until you accept.
          </p>
          {pendingIn.length === 0 ? (
            <p className="muted">No transfer requests are waiting.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Coming from</th>
                    <th>To</th>
                    <th>Sent by</th>
                    <th>Sent on</th>
                    <th>Note</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pendingIn.map((t) => (
                    <tr key={t.id}>
                      <td>{t.citizen_name}</td>
                      <td>{t.national_id}</td>
                      <td>{t.from_village_name}{t.from_isibo ? ` · isibo ${t.from_isibo}` : ''}</td>
                      <td>{t.to_village_name}</td>
                      <td>{t.transferred_by_name || '—'}</td>
                      <td>{fmt(t.transferred_at)}</td>
                      <td>{t.note || '—'}</td>
                      <td className="actions-cell">
                        {data.can_place ? (
                          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <button className="btn btn-small" onClick={() => setAccepting(t)}>Accept</button>
                            <button className="btn btn-small btn-ghost" onClick={() => setDeclining(t)}>Decline</button>
                          </div>
                        ) : (
                          <span className="muted small">Village leader confirms</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="section-title">Accepted, waiting for an isibo ({awaiting.length})</div>
          {awaiting.length === 0 ? (
            <p className="muted">No accepted citizens are waiting to be placed in {areaLabel}.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Came from</th>
                    <th>Now in</th>
                    <th>Accepted on</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {awaiting.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td>{c.national_id}</td>
                      <td>{c.transferred_from_village_name}{c.transferred_from_isibo ? ` · isibo ${c.transferred_from_isibo}` : ''}</td>
                      <td>{c.village_name}</td>
                      <td>{fmt(c.transferred_at)}</td>
                      <td className="actions-cell">
                        {data.can_place && (
                          <button className="btn btn-small" onClick={() => setPlacing(c)}>Add to isibo</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="section-title">Placed in an isibo ({placed.length})</div>
          {placed.length === 0 ? (
            <p className="muted">No transferred citizens have been placed yet.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <ExportButtons
                title="Citizens transferred in"
                columns={['Citizen', 'ID number', 'Came from', 'Village', 'Isibo', 'Accepted on', 'Placed on']}
                rows={placed.map((c) => [c.name, c.national_id, c.transferred_from_village_name, c.village_name, c.isibo,
                  fmt(c.transferred_at), fmt(c.transfer_placed_at)])}
              />
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Came from</th>
                    <th>Village</th>
                    <th>Isibo</th>
                    <th>Accepted on</th>
                    <th>Placed on</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {placed.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td>{c.national_id}</td>
                      <td>{c.transferred_from_village_name}</td>
                      <td>{c.village_name}</td>
                      <td>{c.isibo || '—'}</td>
                      <td>{fmt(c.transferred_at)}</td>
                      <td>{fmt(c.transfer_placed_at)}</td>
                      <td className="actions-cell">
                        {data.can_place && (
                          <button className="btn btn-small btn-ghost" onClick={() => setPlacing(c)}>Change isibo</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Citizens sent out of {areaLabel} ({data.outgoing.length})</div>
          <p className="muted small">
            Pending citizens still appear among your citizens until the receiving leader accepts. Accepted ones no longer do; “Now in” shows where they live today.
          </p>
          {data.outgoing.length === 0 ? (
            <p className="muted">No citizen has been transferred out of {areaLabel}.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <ExportButtons
                title="Citizens transferred out"
                columns={['Citizen', 'ID number', 'Left from', 'Isibo', 'Sent to', 'Now in', 'Isibo now', 'Sent on', 'By', 'Status', 'Decided by', 'Decided on', 'Reason']}
                rows={data.outgoing.map((t) => [t.citizen_name, t.national_id, t.from_village_name, t.from_isibo || '',
                  t.to_village_name, t.current_village_name, t.current_isibo || '', fmt(t.transferred_at), t.transferred_by_name || '',
                  STATUS_LABEL[t.status] || t.status, t.decided_by_name || '', fmt(t.decided_at), t.decision_note || ''])}
              />
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Left from</th>
                    <th>Sent to</th>
                    <th>Now in</th>
                    <th>Sent on</th>
                    <th>By</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.outgoing.map((t) => (
                    <tr key={t.id}>
                      <td>{t.citizen_name}</td>
                      <td>{t.national_id}</td>
                      <td>{t.from_village_name}{t.from_isibo ? ` · isibo ${t.from_isibo}` : ''}</td>
                      <td>{t.to_village_name}</td>
                      <td>{t.current_village_name}{t.current_isibo ? ` · isibo ${t.current_isibo}` : ''}</td>
                      <td>{fmt(t.transferred_at)}</td>
                      <td>{t.transferred_by_name || '—'}</td>
                      <td>
                        <span className={`badge ${STATUS_CLASS[t.status] || ''}`}>{STATUS_LABEL[t.status] || t.status}</span>
                        {t.decided_at && (
                          <div className="muted small">
                            {t.decided_by_name ? `${t.decided_by_name} · ` : ''}{fmt(t.decided_at)}
                            {t.decision_note ? ` — ${t.decision_note}` : ''}
                          </div>
                        )}
                      </td>
                      <td className="actions-cell">
                        {t.status === 'pending' && data.can_transfer && (
                          <button className="btn btn-small btn-ghost" disabled={cancelling === t.id} onClick={() => cancel(t)}>
                            {cancelling === t.id ? 'Cancelling…' : 'Cancel'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {accepting && (
        <AcceptTransferModal
          transfer={accepting}
          onClose={() => setAccepting(null)}
          onDone={async (t) => {
            setAccepting(null)
            setMessage(`${t.citizen_name} is now a citizen of ${t.to_village_name}${t.to_isibo ? `, isibo ${t.to_isibo}` : ' — place them in an isibo below'}.`)
            await load()
          }}
        />
      )}
      {declining && (
        <DeclineTransferModal
          transfer={declining}
          onClose={() => setDeclining(null)}
          onDone={async (t) => {
            setDeclining(null)
            setMessage(`Transfer of ${t.citizen_name} declined. They stay in ${t.from_village_name}.`)
            await load()
          }}
        />
      )}
      {placing && (
        <PlaceCitizenModal
          citizen={placing}
          onClose={() => setPlacing(null)}
          onDone={async (updated) => {
            setPlacing(null)
            setMessage(`${updated.name} placed in isibo ${updated.isibo}.`)
            await load()
          }}
        />
      )}
    </div>
  )
}
