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
export default function LocationSelect({ value, onChange, upTo = 'village' }) {
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
