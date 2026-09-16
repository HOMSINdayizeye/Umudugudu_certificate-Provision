import { useEffect, useState } from 'react'
import { saveBlob } from '../api.js'

// Opens a fetched file on screen: PDFs in a frame, images inline, anything else with a download fallback.
// doc: {title, blob, filename}
export default function DocViewer({ doc, onClose }) {
  const [url, setUrl] = useState(null)

  useEffect(() => {
    if (!doc) return undefined
    const u = URL.createObjectURL(doc.blob)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [doc])

  useEffect(() => {
    if (!doc) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doc, onClose])

  if (!doc || !url) return null
  const type = doc.blob.type || ''
  const isPdf = type === 'application/pdf' || /\.pdf$/i.test(doc.filename)
  const isImage = type.startsWith('image/') || /\.(png|jpe?g|gif|webp)$/i.test(doc.filename)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal viewer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={doc.title}>
        <div className="viewer-head">
          <div>
            <strong>{doc.title}</strong>
            <div className="muted small">{doc.filename}</div>
          </div>
          <div className="btn-row" style={{ marginTop: 0 }}>
            <button className="btn btn-small btn-outline-dark" onClick={() => saveBlob(doc)}>Download</button>
            <button className="btn btn-small btn-ghost" onClick={onClose}>Close ✕</button>
          </div>
        </div>
        <div className="viewer-body">
          {isPdf ? (
            <iframe src={`${url}#toolbar=1&view=FitH`} title={doc.title} />
          ) : isImage ? (
            <img src={url} alt={doc.title} />
          ) : (
            <div className="viewer-fallback">
              <p>This file type cannot be shown in the browser.</p>
              <button className="btn" onClick={() => saveBlob(doc)}>Download {doc.filename}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
