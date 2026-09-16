import { useEffect, useState } from 'react'
import { api } from '../api.js'

const LEVELS = [
  ['province', 'Province'],
  ['district', 'District'],
  ['sector', 'Sector'],
  ['cell', 'Cell'],
  ['village', 'Village'],
]

// Cascading province → district → sector → cell → village selector.
// value: {province, district, sector, cell, village}; onChange receives the updated object.
// progressive: reveal one level at a time down a vertical chain; chosen levels collapse to a row with "change".
export default function LocationSelect({ value, onChange, upTo = 'village', progressive = false }) {
  const [options, setOptions] = useState({ province: [], district: [], sector: [], cell: [], village: [] })
  const levels = LEVELS.slice(0, LEVELS.findIndex(([l]) => l === upTo) + 1)

  useEffect(() => {
    api.provinces().then((p) => setOptions((o) => ({ ...o, province: p }))).catch(() => {})
  }, [])

  async function pick(level, val) {
    const next = { ...value, [level]: val }
    const chain = LEVELS.map(([l]) => l)
    for (const l of chain.slice(chain.indexOf(level) + 1)) next[l] = ''
    onChange(next)

    const loaders = {
      province: () => api.districts(val).then((d) => setOptions((o) => ({ ...o, district: d, sector: [], cell: [], village: [] }))),
      district: () => api.sectors(val).then((d) => setOptions((o) => ({ ...o, sector: d, cell: [], village: [] }))),
      sector: () => api.cells(val).then((d) => setOptions((o) => ({ ...o, cell: d, village: [] }))),
      cell: () => api.villages(val).then((d) => setOptions((o) => ({ ...o, village: d }))),
    }
    if (val && loaders[level]) await loaders[level]().catch(() => {})
  }

  if (!progressive) {
    return (
      <>
        {levels.map(([level, label]) => (
          <div className="form-group" key={level}>
            <label>{label}</label>
            <select
              value={value[level] || ''}
              onChange={(e) => pick(level, e.target.value)}
              disabled={level !== 'province' && options[level].length === 0 && !value[level]}
            >
              <option value="">— Select {label} —</option>
              {options[level].map((o) => (
                <option key={o.location_id} value={o.location_id}>{o.name}</option>
              ))}
            </select>
          </div>
        ))}
      </>
    )
  }

  // Index of the first level still to choose; everything above it is done, nothing below it is shown yet
  const nextIndex = levels.findIndex(([level]) => !value[level])
  const nameOf = (level) => options[level].find((o) => String(o.location_id) === String(value[level]))?.name || value[level]

  return (
    <div className="loc-chain">
      {levels.map(([level, label], i) => {
        if (nextIndex !== -1 && i > nextIndex) return null
        const done = !!value[level]
        return (
          <div className={`loc-row ${done ? 'loc-row-done' : 'loc-row-active'}`} key={level}>
            <span className="loc-dot">{done ? '✓' : i + 1}</span>
            {done ? (
              <>
                <span className="loc-label">{label}</span>
                <span className="loc-value">{nameOf(level)}</span>
                <button type="button" className="link-btn" onClick={() => pick(level, '')}>change</button>
              </>
            ) : (
              <select autoFocus={i > 0} value="" onChange={(e) => pick(level, e.target.value)}>
                <option value="">Choose {label.toLowerCase()}…</option>
                {options[level].map((o) => (
                  <option key={o.location_id} value={o.location_id}>{o.name}</option>
                ))}
              </select>
            )}
          </div>
        )
      })}
    </div>
  )
}
