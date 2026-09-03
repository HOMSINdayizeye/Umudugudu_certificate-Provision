import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Dashboard({ user }) {
  const [requests, setRequests] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setRequests(await api.listRequests())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function act(id, action) {
    setError('')
    try {
      await api.actOnRequest(id, action)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>{user?.is_superuser ? 'All Certificate Requests' : 'My Certificate Requests'}</h1>
        <Link to="/submit" className="btn">New Request</Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        {loading ? (
          <p className="muted">Loading…</p>
        ) : requests.length === 0 ? (
          <p className="muted">No requests yet. Click "New Request" to submit one.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                {user?.is_superuser && <th>Requested by</th>}
                <th>Type</th>
                <th>Date</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  {user?.is_superuser && <td>{r.user.first_name} {r.user.last_name} ({r.user.email})</td>}
                  <td>{r.cert_type_display}</td>
                  <td>{new Date(r.created_at).toLocaleDateString()}</td>
                  <td><span className={`badge badge-${r.status}`}>{r.status_display}</span></td>
                  <td>
                    <Link to={`/requests/${r.id}`} className="btn btn-small">View</Link>{' '}
                    {user?.is_superuser && r.status === 'pending' && (
                      <>
                        <button className="btn btn-small" onClick={() => act(r.id, 'approve')}>Approve</button>{' '}
                        <button className="btn btn-small btn-danger" onClick={() => act(r.id, 'deny')}>Deny</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
