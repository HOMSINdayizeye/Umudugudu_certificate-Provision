// Circular progress indicator shown while data is being fetched
export default function Spinner({ label = 'Loading…', inline = false, size = 36 }) {
  return (
    <div className={`spinner-wrap ${inline ? 'spinner-inline' : ''}`} role="status" aria-live="polite">
      <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />
      {label && <span className="spinner-label">{label}</span>}
    </div>
  )
}
