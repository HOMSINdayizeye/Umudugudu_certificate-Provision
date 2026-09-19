import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Pagination from '../components/Pagination.jsx'
import Spinner from '../components/Spinner.jsx'
import { TransferCitizenModal, PlaceCitizenModal, TransferBadge } from '../components/TransferCitizenModal.jsx'

const PAGE_SIZE = 10
const AREA = { village_leader: 'village', cell_leader: 'cell', sector_leader: 'sector' }

// Village / cell / sector leader: every registered citizen living in their area, read-only with transfer actions.
export default function AreaCitizens({ user }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [q, setQ] = useState('')
  const [village, setVillage] = useState('all')
  const [isibo, setIsibo] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)

  async function load() {
    setError('')
    try {
      setData(await api.listCitizens())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => { setPage(1) }, [q, village, isibo])

  const citizens = data?.citizens || []
  const area = AREA[user?.role] || 'area'
  const villages = [...new Map(citizens.map((c) => [String(c.village), c.village_name])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]))
  const isibos = [...new Set(citizens.filter((c) => String(c.village) === village || village === 'all').map((c) => c.isibo))]
    .sort((a, b) => (a || '').localeCompare(b || ''))

  const needle = q.trim().toLowerCase()
  const visible = citizens
    .filter((c) => village === 'all' || String(c.village) === village)
    .filter((c) => isibo === 'all' || c.isibo === isibo)
    .filter((c) => !needle || [c.name, c.national_id, c.phone, c.email, c.isibo, c.village_name].join(' ').toLowerCase().includes(needle))
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageRows = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      <div className="page-head">
        <h1>Citizens in your {area}{data ? ` (${citizens.length})` : ''}</h1>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="card">
        <div className="filter-row date-filter">
          <div className="form-group" style={{ flex: '2 1 240px', maxWidth: 'none' }}>
            <label>Search</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID number, phone, isibo…" />
          </div>
          {villages.length > 1 && (
            <div className="form-group">
              <label>Village</label>
              <select value={village} onChange={(e) => { setVillage(e.target.value); setIsibo('all') }}>
                <option value="all">All villages</option>
                {villages.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
              </select>
            </div>
          )}
          <div className="form-group">
            <label>Isibo</label>
            <select value={isibo} onChange={(e) => setIsibo(e.target.value)}>
              <option value="all">All isibos</option>
              {isibos.map((n) => <option key={n || '_none'} value={n}>{n || '(no isibo)'}</option>)}
            </select>
          </div>
        </div>

        {!data ? (
          <Spinner label="Loading citizens…" />
        ) : citizens.length === 0 ? (
          <p className="muted">No citizens are registered in your {area} yet. Isibo leaders add citizens.</p>
        ) : visible.length === 0 ? (
          <p className="muted">No citizens match these filters.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title={`Citizens in your ${area}`}
              columns={['#', 'Name', 'ID number', 'Age', 'Phone', 'Email', 'Village', 'Isibo', 'Registered by', 'Transferred from']}
              rows={visible.map((c, i) => [i + 1, c.name, c.national_id, c.age, c.phone || '', c.email || '', c.village_name || '',
                c.isibo || '', c.added_by_name || '', c.transferred_from_village_name || ''])}
            />
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Name</th>
                  <th>ID number</th>
                  <th>Age</th>
                  <th>Phone</th>
                  {villages.length > 1 && <th>Village</th>}
                  <th>Isibo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((c, idx) => (
                  <tr key={c.id} className="row-clickable" onClick={() => setSelected(c)}>
                    <td>{(current - 1) * PAGE_SIZE + idx + 1}</td>
                    <td>{c.name}<TransferBadge citizen={c} /></td>
                    <td>{c.national_id}</td>
                    <td>{c.age || '—'}</td>
                    <td>{c.phone || '—'}</td>
                    {villages.length > 1 && <td>{c.village_name}</td>}
                    <td>{c.isibo || '—'}</td>
                    <td className="actions-cell">
                      <button className="btn btn-small" onClick={(e) => { e.stopPropagation(); setSelected(c) }}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="citizen" onChange={setPage} />
          </div>
        )}
      </div>

      {selected && (
        <CitizenDetailModal
          citizen={selected}
          canTransfer={!!data?.can_transfer}
          canPlace={!!data?.can_place}
          canDelete={!!data?.can_delete}
          onClose={() => setSelected(null)}
          onMoved={async (text) => { setSelected(null); setMessage(text); await load() }}
        />
      )}
    </div>
  )
}

function CitizenDetailModal({ citizen, canTransfer, canPlace, canDelete, onClose, onMoved }) {
  const [action, setAction] = useState(null) // 'transfer' | 'place' | 'delete' | null
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function remove() {
    setError('')
    setBusy(true)
    try {
      const res = await api.deleteCitizen(citizen.id)
      onMoved(res.detail)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{citizen.name}</h2>
        <dl className="detail-grid">
          <dt>ID number</dt><dd>{citizen.national_id}</dd>
          <dt>Age</dt><dd>{citizen.age || '—'}</dd>
          <dt>Phone</dt><dd>{citizen.phone || '—'}</dd>
          <dt>Email</dt><dd>{citizen.email || '—'}</dd>
          <dt>Village</dt><dd>{citizen.village_name}</dd>
          <dt>Isibo</dt><dd>{citizen.isibo || (citizen.awaiting_isibo ? <em className="muted">not yet placed</em> : '—')}</dd>
          <dt>Registered by</dt><dd>{citizen.added_by_name || '—'}</dd>
          <dt>Registered on</dt><dd>{citizen.created_at ? new Date(citizen.created_at).toLocaleDateString() : '—'}</dd>
          {citizen.transferred_from_village && (
            <>
              <dt>Transferred from</dt>
              <dd>
                {citizen.transferred_from_village_name}{citizen.transferred_from_isibo ? ` · isibo ${citizen.transferred_from_isibo}` : ''}
                {citizen.transferred_at ? ` (${new Date(citizen.transferred_at).toLocaleDateString()})` : ''}
              </dd>
            </>
          )}
        </dl>
        <p className="muted small">Citizen information can only be changed by the isibo leader.</p>
        {error && <div className="alert alert-error">{error}</div>}

        {(canTransfer || (canPlace && citizen.awaiting_isibo)) && (
          <>
            <div className="section-title">Residence</div>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {canPlace && citizen.awaiting_isibo && (
                <button className="btn btn-small" onClick={() => setAction('place')}>Add to an isibo</button>
              )}
              {canTransfer && (
                <button className="btn btn-small btn-outline-dark" onClick={() => setAction('transfer')}>Transfer to another village</button>
              )}
            </div>
          </>
        )}

        {action === 'delete' ? (
          <div className="alert alert-error" style={{ marginTop: '1.25rem' }}>
            <strong>Delete {citizen.name}?</strong> The record and their payment history are removed permanently.
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
              <button className="btn btn-small btn-danger" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Yes, delete'}</button>
              <button className="btn btn-small btn-ghost" disabled={busy} onClick={() => setAction(null)}>Keep</button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
            {canDelete && <button className="btn btn-small btn-danger" onClick={() => setAction('delete')}>Delete citizen</button>}
            <button className="btn btn-small btn-ghost" onClick={onClose}>Close</button>
          </div>
        )}

        {action === 'transfer' && (
          <TransferCitizenModal
            citizen={citizen}
            onClose={() => setAction(null)}
            onDone={(t) => onMoved(`${citizen.name} transferred to ${t.to_village_name}. See Transfers for where they are.`)}
          />
        )}
        {action === 'place' && (
          <PlaceCitizenModal
            citizen={citizen}
            onClose={() => setAction(null)}
            onDone={(c) => onMoved(`${c.name} placed in isibo ${c.isibo}.`)}
          />
        )}
      </div>
    </div>
  )
}
