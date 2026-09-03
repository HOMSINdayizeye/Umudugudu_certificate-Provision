import { useEffect, useState } from 'react'
import { api } from '../api.js'

const VOLUNTEER_SERVICE = {
  cleaning_volunteer: 'cleaning',
  security_volunteer: 'security',
}

export default function Payments({ user }) {
  const myService = VOLUNTEER_SERVICE[user?.role]
  const canRecord = !!myService || user?.is_admin_role
  const [tab, setTab] = useState('citizens')

  return (
    <div>
      <div className="page-head">
        <h1>{myService ? `${myService === 'cleaning' ? 'Cleaning' : 'Security'} Service Payments` : 'Service Payments'}</h1>
      </div>

      <div className="tabs">
        <button className={tab === 'citizens' ? 'tab tab-active' : 'tab'} onClick={() => setTab('citizens')}>
          Citizens
        </button>
        <button className={tab === 'history' ? 'tab tab-active' : 'tab'} onClick={() => setTab('history')}>
          Paid Payments
        </button>
      </div>

      {tab === 'citizens' ? (
        <CitizensTab myService={myService} canRecord={canRecord} />
      ) : (
        <HistoryTab myService={myService} />
      )}
    </div>
  )
}

function CitizensTab({ myService, canRecord }) {
  const currentYear = new Date().getFullYear()
  const [service, setService] = useState(myService || 'cleaning')
  const [year, setYear] = useState(currentYear)
  const [data, setData] = useState(null)
  const [selected, setSelected] = useState(null) // citizen opened in the payment panel
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      const res = await api.listCitizens({ service, year })
      setData(res)
      // Keep the open panel in sync after marking/unmarking
      if (selected) {
        const fresh = res.citizens.find((c) => c.id === selected.id)
        if (fresh) setSelected(fresh)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [service, year])

  const canMark = data?.can_mark && canRecord

  return (
    <div className="card">
      {error && <div className="alert alert-error">{error}</div>}

      <div className="filter-row">
        {!myService && (
          <div className="form-group">
            <label>Service</label>
            <select value={service} onChange={(e) => setService(e.target.value)}>
              <option value="cleaning">Cleaning</option>
              <option value="security">Security</option>
            </select>
          </div>
        )}
        <div className="form-group">
          <label>Year</label>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[currentYear + 1, currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {!data ? (
        <p className="muted">Loading…</p>
      ) : data.citizens.length === 0 ? (
        <p className="muted">No citizens registered in your area yet. The isibo leader adds citizens.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Citizen</th>
                <th>Isibo</th>
                <th>Village</th>
                <th>T1</th>
                <th>T2</th>
                <th>T3</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.citizens.map((c) => (
                <tr key={c.id} className="row-clickable" onClick={() => setSelected(c)}>
                  <td>{c.name}</td>
                  <td>{c.isibo || '—'}</td>
                  <td>{c.village_name}</td>
                  {[1, 2, 3].map((t) => (
                    <td key={t}>
                      {c.paid[t] ? (
                        <span className="badge badge-approved">✔ {Number(c.paid[t].amount).toLocaleString()}</span>
                      ) : (
                        <span className="badge badge-pending">Unpaid</span>
                      )}
                    </td>
                  ))}
                  <td>
                    <button className="btn btn-small" onClick={(e) => { e.stopPropagation(); setSelected(c) }}>
                      {canMark ? 'View / Mark' : 'View'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <CitizenPaymentModal
          citizen={selected}
          service={service}
          year={year}
          canMark={canMark}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      )}
    </div>
  )
}

// Read-only citizen info + per-trimester mark/unmark controls.
function CitizenPaymentModal({ citizen, service, year, canMark, onClose, onChanged }) {
  const [amount, setAmount] = useState('1000')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function mark(trimesters) {
    setError('')
    if (!amount || Number(amount) <= 0) {
      setError('Enter the amount (RWF) first.')
      return
    }
    setBusy(true)
    try {
      await api.recordPayment({ citizen: citizen.id, service, year, amount, trimesters })
      await onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function unmark(paymentId) {
    setError('')
    setBusy(true)
    try {
      await api.unmarkPayment(paymentId)
      await onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const unpaid = [1, 2, 3].filter((t) => !citizen.paid[t])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{citizen.name}</h2>
        {error && <div className="alert alert-error">{error}</div>}

        <dl className="detail-grid" style={{ marginBottom: '1rem' }}>
          <dt>Phone</dt><dd>{citizen.phone || '—'}</dd>
          <dt>Email</dt><dd>{citizen.email || '—'}</dd>
          <dt>ID number</dt><dd>{citizen.national_id}</dd>
          <dt>Age</dt><dd>{citizen.age || '—'}</dd>
          <dt>Isibo</dt><dd>{citizen.isibo || '—'}</dd>
          <dt>Village</dt><dd>{citizen.village_name}</dd>
        </dl>
        <p className="muted" style={{ marginTop: 0 }}>
          Citizen information can only be changed by the isibo leader.
        </p>

        <div className="section-title">
          {service === 'cleaning' ? 'Cleaning' : 'Security'} service — {year}
        </div>

        {canMark && (
          <div className="form-group" style={{ maxWidth: 220 }}>
            <label>Amount (RWF)</label>
            <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
        )}

        <table className="table">
          <thead>
            <tr><th>Trimester</th><th>Status</th>{canMark && <th>Action</th>}</tr>
          </thead>
          <tbody>
            {[1, 2, 3].map((t) => (
              <tr key={t}>
                <td>Trimester {t}</td>
                <td>
                  {citizen.paid[t] ? (
                    <span className="badge badge-approved">✔ Paid {Number(citizen.paid[t].amount).toLocaleString()} RWF</span>
                  ) : (
                    <span className="badge badge-pending">Not paid</span>
                  )}
                </td>
                {canMark && (
                  <td>
                    {citizen.paid[t] ? (
                      <button className="btn btn-small btn-danger" disabled={busy}
                              onClick={() => unmark(citizen.paid[t].payment_id)}>
                        Unmark
                      </button>
                    ) : (
                      <button className="btn btn-small" disabled={busy} onClick={() => mark([t])}>
                        Mark paid
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
          {canMark && unpaid.length > 1 && (
            <button className="btn" disabled={busy} onClick={() => mark(unpaid)}>
              Mark all remaining paid
            </button>
          )}
          <button className="btn btn-outline-dark" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

function HistoryTab({ myService }) {
  const currentYear = new Date().getFullYear()
  const [filters, setFilters] = useState({ service: myService || '', trimester: '', year: '', period: 'all' })
  const [payments, setPayments] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setError('')
    setLoading(true)
    try {
      const params = {}
      for (const [k, v] of Object.entries(filters)) if (v && v !== 'all') params[k] = v
      setPayments(await api.listPayments(params))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filters])

  function set(field) {
    return (e) => setFilters({ ...filters, [field]: e.target.value })
  }

  const total = payments.reduce((sum, p) => sum + Number(p.amount), 0)

  return (
    <div className="card">
      {error && <div className="alert alert-error">{error}</div>}

      <div className="filter-row">
        {!myService && (
          <div className="form-group">
            <label>Service</label>
            <select value={filters.service} onChange={set('service')}>
              <option value="">All services</option>
              <option value="cleaning">Cleaning</option>
              <option value="security">Security</option>
            </select>
          </div>
        )}
        <div className="form-group">
          <label>Trimester</label>
          <select value={filters.trimester} onChange={set('trimester')}>
            <option value="">All</option>
            <option value="1">Trimester 1</option>
            <option value="2">Trimester 2</option>
            <option value="3">Trimester 3</option>
          </select>
        </div>
        <div className="form-group">
          <label>Year</label>
          <select value={filters.year} onChange={set('year')}>
            <option value="">All years</option>
            {[currentYear + 1, currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Paid</label>
          <select value={filters.period} onChange={set('period')}>
            <option value="all">All time</option>
            <option value="this_month">This month</option>
            <option value="last_month">Last month</option>
          </select>
        </div>
      </div>

      {loading ? (
        <p className="muted">Loading…</p>
      ) : payments.length === 0 ? (
        <p className="muted">No payments match these filters.</p>
      ) : (
        <>
          <p className="muted">{payments.length} payment(s) — total {total.toLocaleString()} RWF</p>
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Citizen</th>
                  <th>Isibo</th>
                  <th>Service</th>
                  <th>Trimester</th>
                  <th>Year</th>
                  <th>Amount</th>
                  <th>Paid on</th>
                  <th>Recorded by</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td>{p.citizen_name}</td>
                    <td>{p.citizen_isibo || '—'}</td>
                    <td>{p.service_display}</td>
                    <td>T{p.trimester}</td>
                    <td>{p.year}</td>
                    <td>{Number(p.amount).toLocaleString()} RWF</td>
                    <td>{new Date(p.paid_at).toLocaleDateString()}</td>
                    <td>{p.recorded_by_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
