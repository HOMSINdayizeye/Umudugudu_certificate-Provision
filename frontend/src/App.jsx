import { Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { api, getToken, getUser, clearSession } from './api.js'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SubmitRequest from './pages/SubmitRequest.jsx'
import RequestDetail from './pages/RequestDetail.jsx'
import ManageEligibility from './pages/ManageEligibility.jsx'

function RequireAuth({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const navigate = useNavigate()
  const [user, setUser] = useState(getUser())

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
              {user.is_superuser && <Link to="/eligibility">Eligibility</Link>}
              <span className="user-chip">{user.first_name || user.username}</span>
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
          <Route path="/eligibility" element={<RequireAuth><ManageEligibility /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
