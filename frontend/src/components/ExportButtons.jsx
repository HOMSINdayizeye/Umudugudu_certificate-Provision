import { useState } from 'react'
import { api, saveBlob } from '../api.js'

// "Export PDF / Word" for any list: pass the title, column headings and the rows as arrays of cell values
export default function ExportButtons({ title, columns, rows, disabled = false }) {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  async function run(format) {
    setError(''); setBusy(format)
    try {
      saveBlob(await api.exportTable({ title, columns, rows, format }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const none = disabled || !rows || rows.length === 0
  return (
    <div className="export-bar">
      <span className="muted small">Export {rows?.length ? `${rows.length} row${rows.length === 1 ? '' : 's'}` : ''}</span>
      <button type="button" className="btn btn-small btn-outline-dark" disabled={none || !!busy} onClick={() => run('pdf')} title="Download this list as PDF">
        {busy === 'pdf' ? '…' : 'PDF'}
      </button>
      <button type="button" className="btn btn-small btn-outline-dark" disabled={none || !!busy} onClick={() => run('docx')} title="Download this list as Word">
        {busy === 'docx' ? '…' : 'Word'}
      </button>
      {error && <span className="small" style={{ color: 'var(--danger)' }}>{error}</span>}
    </div>
  )
}
