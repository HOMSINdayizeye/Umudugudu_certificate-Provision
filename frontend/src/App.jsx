import { Routes, Route, Navigate, Link, NavLink, useNavigate } from 'react-router-dom'
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
import Announcements from './pages/Announcements.jsx'
import Documents from './pages/Documents.jsx'
import Codes from './pages/Codes.jsx'
import Profile from './pages/Profile.jsx'
import NotificationBell from './components/NotificationBell.jsx'

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
        <Link to="/" className="brand">
          {/* Drop the coat of arms at frontend/public/logo.png and it replaces the blue tile */}
          <img src="/logo.png" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextSibling.style.display = 'grid' }} />
          <span className="brand-mark" style={{ display: 'none' }}>CK</span>
          Kigali City <span>Certify</span>
        </Link>
        <nav>
          {user ? (
            <>
              <NavLink to="/" end>Dashboard</NavLink>
              {!isAdmin && !LEADER_ROLES.includes(user.role) && <NavLink to="/submit">Apply</NavLink>}
              <NavLink to="/announcements">Announcements</NavLink>
              <NavLink to="/documents">Documents</NavLink>
              {(isAdmin || LEADER_ROLES.includes(user.role)) && <NavLink to="/codes">Codes</NavLink>}
              {seesPayments && <NavLink to="/payments">Payments</NavLink>}
              {(isAdmin || user.role === 'isibo_leader') && <NavLink to="/citizens">Citizens</NavLink>}
              {isAdmin && <NavLink to="/add-user">Add User</NavLink>}
              {isAdmin && <NavLink to="/eligibility">Eligibility</NavLink>}
              <NotificationBell />
              <NavLink to="/profile" className="user-chip" title="My profile">
                {user.first_name || user.username}
                {user.role_display && user.role !== 'citizen' && <em> · {user.role_display}</em>}
              </NavLink>
              <button className="btn btn-outline" onClick={handleLogout}>Logout</button>
            </>
          ) : (
            <>
              <Link to="/login">Login</Link>
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
          <Route path="/requests/:id/edit" element={<RequireAuth><SubmitRequest /></RequireAuth>} />
          <Route path="/payments" element={<RequireAuth><Payments user={user} /></RequireAuth>} />
          <Route path="/citizens" element={<RequireAuth><Citizens user={user} /></RequireAuth>} />
          <Route path="/announcements" element={<RequireAuth><Announcements user={user} /></RequireAuth>} />
          <Route path="/documents" element={<RequireAuth><Documents user={user} /></RequireAuth>} />
          <Route path="/codes" element={<RequireAuth><Codes /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile user={user} onUpdate={setUser} /></RequireAuth>} />
          <Route path="/add-user" element={<RequireAuth><AddUser /></RequireAuth>} />
          <Route path="/eligibility" element={<RequireAuth><ManageEligibility /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="site-footer">© {new Date().getFullYear()} <strong>City of Kigali</strong>. All Rights Reserved.</footer>
    </div>
  )
}
