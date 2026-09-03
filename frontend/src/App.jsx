import { Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, getToken, getUser, setSession, clearSession } from './api.js'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SubmitRequest from './pages/SubmitRequest.jsx'
import RequestDetail from './pages/RequestDetail.jsx'
import ManageEligibility from './pages/ManageEligibility.jsx'
import Payments from './pages/Payments.jsx'
import AddUser from './pages/AddUser.jsx'
import Citizens from './pages/Citizens.jsx'

const LEADER_ROLES = ['village_leader', 'cell_leader', 'sector_leader']
const VOLUNTEER_ROLES = ['security_volunteer', 'cleaning_volunteer']

function RequireAuth({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const navigate = useNavigate()
  const [user, setUser] = useState(getUser())

  // Refresh the cached user so new fields (role, location) appear without re-login
  useEffect(() => {
    if (getToken()) {
      api.me().then((u) => {
        setSession(getToken(), u)
        setUser(u)
      }).catch(() => {})
    }
  }, [])

  const isAdmin = user?.is_admin_role || user?.is_superuser
  const seesPayments = isAdmin || LEADER_ROLES.includes(user?.role) || VOLUNTEER_ROLES.includes(user?.role)

  async function handleLogout() {
    try {
      await api.logout()
    } catch {
      // Token may already be invalid; clear locally regardless
    }
    clearSession()
    setUser(null)
    navigate('/login')
  }

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">Certify <span>Kigali City</span></Link>
        <nav>
          {user ? (
            <>
              <Link to="/">Dashboard</Link>
              <Link to="/submit">New Request</Link>
              {seesPayments && <Link to="/payments">Payments</Link>}
              {(isAdmin || user.role === 'isibo_leader') && <Link to="/citizens">Citizens</Link>}
              {isAdmin && <Link to="/add-user">Add User</Link>}
              {isAdmin && <Link to="/eligibility">Eligibility</Link>}
              <span className="user-chip">
                {user.first_name || user.username}
                {user.role_display && user.role !== 'citizen' && <em> · {user.role_display}</em>}
              </span>
              <button className="btn btn-outline" onClick={handleLogout}>Logout</button>
            </>
          ) : (
            <>
              <Link to="/login">Login</Link>
              <Link to="/register">Register</Link>
            </>
          )}
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route path="/login" element={<Login onLogin={setUser} />} />
          <Route path="/register" element={<Register onRegister={setUser} />} />
          <Route path="/" element={<RequireAuth><Dashboard user={user} /></RequireAuth>} />
          <Route path="/submit" element={<RequireAuth><SubmitRequest /></RequireAuth>} />
          <Route path="/requests/:id" element={<RequireAuth><RequestDetail user={user} /></RequireAuth>} />
          <Route path="/payments" element={<RequireAuth><Payments user={user} /></RequireAuth>} />
          <Route path="/citizens" element={<RequireAuth><Citizens user={user} /></RequireAuth>} />
          <Route path="/add-user" element={<RequireAuth><AddUser /></RequireAuth>} />
          <Route path="/eligibility" element={<RequireAuth><ManageEligibility /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
