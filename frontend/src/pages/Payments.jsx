import { useEffect, useState } from 'react'
import { api } from '../api.js'

const VOLUNTEER_SERVICE = {
  cleaning_volunteer: 'cleaning',
  security_volunteer: 'security',
}

export default function Payments({ user }) {
  const myService = VOLUNTEER_SERVICE[user?.role]
  const canRecord = !!myService || user?.is_admin_role
  const [tab, setTab] = useState(canRecord ? 'citizens' : 'history')

  return (
    <div>
      <div className="page-head">
        <h1>{myService ? `${myService === 'cleaning' ? 'Cleaning' : 'Security'} Service Payments` : 'Service Payments'}</h1>
      </div>

      <div className="tabs">
        {canRecord && (
          <button className={tab === 'citizens' ? 'tab tab-active' : 'tab'} onClick={() => setTab('citizens')}>
            Citizens & Mark Paid
          </button>
        )}
        <button className={tab === 'history' ? 'tab tab-active' : 'tab'} onClick={() => setTab('history')}>
          Paid Payments
        </button>
      </div>

      {tab === 'citizens' && canRecord ? (
        <CitizensTab user={user} myService={myService} />
      ) : (
        <HistoryTab user={user} myService={myService} />
      )}
    </div>
  )
}

function CitizensTab({ user, myService }) {
  const currentYear = new Date().getFullYear()
  const [service, setService] = useState(myService || 'cleaning')
  const [year, setYear] = useState(currentYear)
  const [amount, setAmount] = useState('1000')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    setError('')
    try {
      setData(await api.listCitizens({ service, year }))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [service, year])

  async function mark(citizen, trimesters) {
    setError('')
    setMessage('')
    if (!amount || Number(amount) <= 0) {
      setError('Enter the amount (RWF) before marking a payment.')
      return
    }
    setBusy(true)
    try {
      const res = await api.recordPayment({ citizen: citizen.id, service, year, amount, trimesters })
      const done = res.created_trimesters.map((t) => `T${t}`).join(', ')
      const skipped = res.already_paid_trimesters.map((t) => `T${t}`).join(', ')
      setMessage(
        `${citizen.name}: ${done ? `marked ${done} paid` : 'nothing new'}${skipped ? ` (already paid: ${skipped})` : ''}.`,
      )
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

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
        <div className="form-group">
          <label>Amount (RWF)</label>
          <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
      </div>

      {!data ? (
        <p className="muted">Loading…</p>
      ) : data.citizens.length === 0 ? (
        <p className="muted">No citizens found in your area.</p>
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
                <th>Whole year</th>
              </tr>
            </thead>
            <tbody>
              {data.citizens.map((c) => {
                const allPaid = [1, 2, 3].every((t) => c.paid[t])
                return (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.isibo || '—'}</td>
                    <td>{c.village_name}</td>
                    {[1, 2, 3].map((t) => (
                      <td key={t}>
                        {c.paid[t] ? (
                          <span className="badge badge-approved">✔ {Number(c.paid[t]).toLocaleString()} RWF</span>
                        ) : (
                          <button className="btn btn-small" disabled={busy} onClick={() => mark(c, [t])}>
                            Mark paid
                          </button>
                        )}
                      </td>
                    ))}
                    <td>
                      {allPaid ? (
                        <span className="badge badge-approved">All paid</span>
                      ) : (
                        <button className="btn btn-small" disabled={busy} onClick={() => mark(c, [1, 2, 3])}>
                          Mark all paid
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function HistoryTab({ user, myService }) {
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
