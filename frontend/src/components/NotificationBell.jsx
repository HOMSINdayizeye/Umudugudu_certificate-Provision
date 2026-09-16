import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

const POLL_MS = 60000

// Bell in the navbar: unread count, dropdown list, click marks read and follows the link
export default function NotificationBell() {
  const [data, setData] = useState({ unread: 0, items: [] })
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const box = useRef(null)

  async function load() {
    try {
      setData(await api.notifications())
    } catch {
      // Ignore network hiccups; the next poll will retry
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (!open) return undefined
    const onClick = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  async function openItem(n) {
    setOpen(false)
    if (!n.read_at) {
      api.markNotificationRead(n.id).then(load).catch(() => {})
    }
    if (n.link) navigate(n.link)
  }

  async function readAll() {
    try {
      await api.markAllNotificationsRead()
      await load()
    } catch {
      // nothing to do
    }
  }

  return (
    <div className="bell-wrap" ref={box}>
      <button type="button" className="bell" onClick={() => setOpen((o) => !o)} aria-label={`Notifications, ${data.unread} unread`} title="Notifications">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M6 8a6 6 0 0 1 12 0v5l2 3H4l2-3z" /><path d="M10 19a2 2 0 0 0 4 0" /></svg>
        {data.unread > 0 && <span className="bell-count">{data.unread > 9 ? '9+' : data.unread}</span>}
      </button>
      {open && (
        <div className="notif-dropdown">
          <div className="notif-head">
            <strong>Notifications</strong>
            {data.unread > 0 && <button type="button" className="link-btn" onClick={readAll}>Mark all read</button>}
          </div>
          {data.items.length === 0 ? (
            <p className="muted small" style={{ padding: '0.75rem 1rem' }}>Nothing yet.</p>
          ) : (
            <ul className="notif-list">
              {data.items.map((n) => (
                <li key={n.id} className={n.read_at ? '' : 'notif-unread'}>
                  <button type="button" onClick={() => openItem(n)}>
                    <span className="notif-title">{n.title}</span>
                    <span className="notif-msg">{n.message}</span>
                    <span className="muted small">{new Date(n.created_at).toLocaleString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
