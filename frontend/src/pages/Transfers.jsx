import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Spinner from '../components/Spinner.jsx'
import { PlaceCitizenModal } from '../components/TransferCitizenModal.jsx'

const STATUS_LABEL = {
  awaiting_isibo: 'Awaiting isibo',
  placed: 'Placed in isibo',
  moved_on: 'Moved again',
}
const STATUS_CLASS = { awaiting_isibo: 'badge-pending', placed: 'badge-approved', moved_on: 'badge-moved_on' }

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')

// Leaders' view of citizens moving between villages: who arrived here (to place) and who left (and where they are).
export default function Transfers({ user }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [placing, setPlacing] = useState(null)
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

  const areaLabel = user?.role === 'village_leader' ? 'your village' : user?.role === 'cell_leader' ? 'your cell'
    : user?.role === 'sector_leader' ? 'your sector' : 'the area'
  const awaiting = data?.incoming.filter((c) => c.awaiting_isibo) || []
  const placed = data?.incoming.filter((c) => !c.awaiting_isibo) || []

  return (
    <div>
      <div className="page-head">
        <h1>Citizen Transfers</h1>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="tabs">
        <button className={tab === 'incoming' ? 'tab tab-active' : 'tab'} onClick={() => setTab('incoming')}>
          Transferred in{awaiting.length > 0 ? ` (${awaiting.length} to place)` : ''}
        </button>
        <button className={tab === 'outgoing' ? 'tab tab-active' : 'tab'} onClick={() => setTab('outgoing')}>
          Transferred out{data ? ` (${data.outgoing.length})` : ''}
        </button>
      </div>

      {!data ? (
        <div className="card"><Spinner label="Loading transfers…" /></div>
      ) : tab === 'incoming' ? (
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Waiting for an isibo ({awaiting.length})</div>
          {awaiting.length === 0 ? (
            <p className="muted">No transferred citizens are waiting to be placed in {areaLabel}.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Came from</th>
                    <th>Now in</th>
                    <th>Transferred on</th>
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
                columns={['Citizen', 'ID number', 'Came from', 'Village', 'Isibo', 'Transferred on', 'Placed on']}
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
                    <th>Transferred on</th>
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
          <div className="section-title" style={{ marginTop: 0 }}>Citizens who left {areaLabel} ({data.outgoing.length})</div>
          <p className="muted small">These citizens no longer appear among your area’s citizens. “Now in” shows where they live today.</p>
          {data.outgoing.length === 0 ? (
            <p className="muted">No citizen has been transferred out of {areaLabel}.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <ExportButtons
                title="Citizens transferred out"
                columns={['Citizen', 'ID number', 'Left from', 'Isibo', 'Now in', 'Isibo now', 'Transferred on', 'By', 'Status']}
                rows={data.outgoing.map((t) => [t.citizen_name, t.national_id, t.from_village_name, t.from_isibo || '',
                  t.current_village_name, t.current_isibo || '', fmt(t.transferred_at), t.transferred_by_name || '',
                  STATUS_LABEL[t.status] || t.status])}
              />
              <table className="table">
                <thead>
                  <tr>
                    <th>Citizen</th>
                    <th>ID number</th>
                    <th>Left from</th>
                    <th>Now in</th>
                    <th>Transferred on</th>
                    <th>By</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.outgoing.map((t) => (
                    <tr key={t.id}>
                      <td>{t.citizen_name}</td>
                      <td>{t.national_id}</td>
                      <td>{t.from_village_name}{t.from_isibo ? ` · isibo ${t.from_isibo}` : ''}</td>
                      <td>{t.current_village_name}{t.current_isibo ? ` · isibo ${t.current_isibo}` : ''}</td>
                      <td>{fmt(t.transferred_at)}</td>
                      <td>{t.transferred_by_name || '—'}</td>
                      <td><span className={`badge ${STATUS_CLASS[t.status] || ''}`}>{STATUS_LABEL[t.status] || t.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
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
