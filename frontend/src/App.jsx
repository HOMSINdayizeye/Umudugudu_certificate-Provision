import { Routes, Route, Navigate, Link, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, getToken, getUser, setSession, clearSession, can } from './api.js'
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
import Transfers from './pages/Transfers.jsx'
import Users from './pages/Users.jsx'
import Roles from './pages/Roles.jsx'
import DataManagement from './pages/DataManagement.jsx'
import Activities from './pages/Activities.jsx'
import ActivityDetail from './pages/ActivityDetail.jsx'
import Census from './pages/Census.jsx'
import ResetPassword from './pages/ResetPassword.jsx'
import MessagingSettings from './pages/MessagingSettings.jsx'
import NotificationBell from './components/NotificationBell.jsx'
import { YOUTH_ROLES } from './citizen.js'

const LEADER_ROLES = ['village_leader', 'cell_leader', 'sector_leader']

function RequireAuth({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [user, setUser] = useState(getUser())
  const [menuOpen, setMenuOpen] = useState(false)

  // Close the phone menu whenever the page changes
  useEffect(() => { setMenuOpen(false) }, [location.pathname])

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
  // Menu entries follow the permissions the admin granted (role defaults unless changed on the Roles page)
  const seesPayments = can(user, 'view:payments')

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
          UMUDUGUDU: INZEGO Y'IMITEGEKERE Y'IGIHUGU <span>Certify</span>
        </Link>

        {/* Always visible, even on phones: bell and the menu button */}
        {user && (
          <div className="topbar-tools">
            <NotificationBell />
            <button
              type="button"
              className="nav-toggle"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
            >
              {menuOpen ? '✕' : '☰'}
            </button>
          </div>
        )}

        <nav className={menuOpen ? 'open' : ''}>
          {user ? (
            <>
              <NavLink to="/" end>Dashboard</NavLink>
              {!isAdmin && !LEADER_ROLES.includes(user.role) && !YOUTH_ROLES.includes(user.role) && <NavLink to="/submit">Apply</NavLink>}
              <NavLink to="/announcements">Announcements</NavLink>
              <NavLink to="/documents">Documents</NavLink>
              {(isAdmin || LEADER_ROLES.includes(user.role)) && <NavLink to="/codes">Codes</NavLink>}
              {seesPayments && <NavLink to="/payments">Payments</NavLink>}
              {can(user, 'view:citizens') && <NavLink to="/citizens">Citizens</NavLink>}
              {can(user, 'view:transfers') && <NavLink to="/transfers">Transfers</NavLink>}
              {can(user, 'view:activities') && <NavLink to="/activities">Activities</NavLink>}
              {can(user, 'view:census') && <NavLink to="/census">Census</NavLink>}
              {can(user, 'view:users') && <NavLink to="/users">Users</NavLink>}
              {can(user, 'permissions:users') && <NavLink to="/roles">Roles</NavLink>}
              {can(user, 'eligibility:users') && <NavLink to="/eligibility">Eligibility</NavLink>}
              {isAdmin && <NavLink to="/data">Data</NavLink>}
              {can(user, 'settings:sms') && <NavLink to="/messaging">Messaging</NavLink>}
              <NavLink to="/profile" className="user-chip" title="My profile">
                {user.first_name || user.username}
                {user.role_display && user.role !== 'citizen' && <em> · {user.role_display}</em>}
              </NavLink>
              <button className="btn btn-outline" onClick={handleLogout}>Logout</button>
            </>
          ) : (
            <Link to="/login">Login</Link>
          )}
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route path="/login" element={<Login onLogin={setUser} />} />
          <Route path="/register" element={<Register onRegister={setUser} />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/messaging" element={<RequireAuth><MessagingSettings user={user} /></RequireAuth>} />
          <Route path="/" element={<RequireAuth><Dashboard user={user} /></RequireAuth>} />
          <Route path="/submit" element={<RequireAuth><SubmitRequest /></RequireAuth>} />
          <Route path="/requests/:id" element={<RequireAuth><RequestDetail user={user} /></RequireAuth>} />
          <Route path="/requests/:id/edit" element={<RequireAuth><SubmitRequest /></RequireAuth>} />
          <Route path="/payments" element={<RequireAuth><Payments user={user} /></RequireAuth>} />
          <Route path="/citizens" element={<RequireAuth><Citizens user={user} /></RequireAuth>} />
          <Route path="/transfers" element={<RequireAuth><Transfers user={user} /></RequireAuth>} />
          <Route path="/announcements" element={<RequireAuth><Announcements user={user} /></RequireAuth>} />
          <Route path="/documents" element={<RequireAuth><Documents user={user} /></RequireAuth>} />
          <Route path="/codes" element={<RequireAuth><Codes /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile user={user} onUpdate={setUser} /></RequireAuth>} />
          <Route path="/add-user" element={<RequireAuth><AddUser /></RequireAuth>} />
          <Route path="/users" element={<RequireAuth><Users /></RequireAuth>} />
          <Route path="/roles" element={<RequireAuth><Roles /></RequireAuth>} />
          <Route path="/activities" element={<RequireAuth><Activities user={user} /></RequireAuth>} />
          <Route path="/activities/:id" element={<RequireAuth><ActivityDetail user={user} /></RequireAuth>} />
          <Route path="/census" element={<RequireAuth><Census user={user} /></RequireAuth>} />
          <Route path="/eligibility" element={<RequireAuth><ManageEligibility /></RequireAuth>} />
          <Route path="/data" element={<RequireAuth><DataManagement user={user} /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="site-footer">© {new Date().getFullYear()} <strong>ISIBO Initiative</strong>. All Rights Reserved.</footer>
    </div>
  )
}
