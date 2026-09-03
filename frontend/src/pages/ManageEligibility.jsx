import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function ManageEligibility() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.listUsers().then(setUsers).catch((err) => setError(err.message))
  }, [])

  async function toggle(user) {
    setError('')
    setMessage('')
    try {
      const updated = await api.setEligibility(user.id, !user.is_eligible)
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)))
      setMessage(`${updated.username} is now ${updated.is_eligible ? 'eligible' : 'not eligible'}.`)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="page-head"><h1>Manage Eligibility</h1></div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="card">
        <table className="table">
          <thead>
            <tr><th>Username</th><th>Name</th><th>Email</th><th>Eligible</th><th></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.first_name} {u.last_name}</td>
                <td>{u.email}</td>
                <td>{u.is_eligible ? '✔ Yes' : '— No'}</td>
                <td>
                  <button className="btn btn-small" onClick={() => toggle(u)}>
                    {u.is_eligible ? 'Revoke' : 'Mark eligible'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
