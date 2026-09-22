import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, can } from '../api.js'
import CountUp from './CountUp.jsx'

const COUNT_MS = 450

// Dashboard card totalling what the signed-in leader has done: letters, communications, activities, registry work
export default function LeaderWorkCard({ user }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.leaderStats().then(setStats).catch(() => setStats(null))
  }, [user?.id])

  if (!stats) return null

  const tiles = [
    { key: 'approved', label: 'Letters approved', hint: `${stats.fully_approved} fully approved`, to: '/documents' },
    { key: 'announcements', label: 'Communications', hint: `${stats.announcements_published} published`, to: '/announcements' },
    { key: 'activities', label: 'Activities', hint: `${stats.attendance_marked} attendance marks`, to: '/activities', perm: 'view:activities' },
    { key: 'citizens', label: 'Citizens in area', to: '/citizens', perm: 'view:citizens' },
    { key: 'transfers', label: 'Transfers handled', to: '/transfers', perm: 'view:transfers' },
    { key: 'deaths', label: 'Deaths reported', to: '/citizens', perm: 'view:citizens' },
    { key: 'payments', label: 'Payments recorded', to: '/payments', perm: 'view:payments' },
  ].filter((t) => !t.perm || can(user, t.perm))

  return (
    <div className="card work-summary" style={{ marginBottom: '1.25rem' }}>
      <div className="page-head" style={{ marginBottom: '0.75rem' }}>
        <h2 className="card-title" style={{ margin: 0 }}>Your work</h2>
        <span className="muted small">Totals of everything you have approved, published or recorded</span>
      </div>
      <div className="work-grid">
        {tiles.map((t, i) => (
          <Link key={t.key} to={t.to} className="work-tile">
            <span className="stat-value stat-value-sm"><CountUp value={stats[t.key]} duration={COUNT_MS} delay={i * 120} /></span>
            <span className="stat-label">{t.label}</span>
            {t.hint && <span className="work-hint">{t.hint}</span>}
          </Link>
        ))}
      </div>
    </div>
  )
}
