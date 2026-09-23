import { useEffect } from 'react'

// Two-panel dialog: brand panel on the left, content on the right; stacks into a header strip on phones
export default function SplitModal({ title, subtitle, headline, tagline, wide, label, onClose, children }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`split-modal${wide ? ' split-modal-wide' : ''}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={label || title}>
        <aside className="split-brand">
          <div className="split-logo">
            {/* Same coat of arms as the top bar; falls back to the blue CK tile when logo.png is missing */}
            <img src="/logo.png" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextSibling.style.display = 'grid' }} />
            <span className="brand-mark" style={{ display: 'none' }}>CK</span>
          </div>
          <div className="split-brand-text">
            <span className="split-org">Umudugudu Certify</span>
            <h2 className="split-headline">{headline}</h2>
            <p className="split-tagline">{tagline}</p>
          </div>
        </aside>
        <section className="split-body">
          <button type="button" className="split-close" onClick={onClose} aria-label="Close">✕</button>
          <h2 className="split-title">{title}</h2>
          {subtitle && <p className="split-subtitle">{subtitle}</p>}
          {children}
        </section>
      </div>
    </div>
  )
}
