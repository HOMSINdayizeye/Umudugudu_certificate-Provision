import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, can } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'
import CensusCoverage, { LEVEL_LABEL, fmt } from '../components/CensusCoverage.jsx'
import Spinner from '../components/Spinner.jsx'

const LEVELS = ['province', 'district', 'sector', 'cell', 'village']

function fmtValue(ind) {
  if (ind.value === null || ind.value === undefined) return '—'
  if (ind.unit === 'percent') return `${Number(ind.value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
  if (ind.unit === 'index') return Number(ind.value).toLocaleString(undefined, { maximumFractionDigits: 3 })
  if (ind.unit === 'years') return `${Number(ind.value).toLocaleString(undefined, { maximumFractionDigits: 1 })} yrs`
  return fmt(Math.round(ind.value))
}

// Groups an area's indicators by topic for display
function IndicatorGroups({ indicators }) {
  const groups = indicators.reduce((m, i) => { (m[i.group] = m[i.group] || []).push(i); return m }, {})
  const names = Object.keys(groups).filter((g) => g !== 'Projections')
  if (!names.length) return <p className="muted">No indicators published for this level.</p>
  return (
    <div className="indicator-grid">
      {names.map((g) => (
        <div key={g} className="indicator-group">
          <div className="section-title" style={{ marginTop: 0 }}>{g}</div>
          <table className="table table-compact">
            <tbody>
              {groups[g].filter((i) => !i.key.startsWith('age_')).map((i) => (
                <tr key={i.key}><td>{i.label}</td><td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}><strong>{fmtValue(i)}</strong></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

// Browse NISR census figures for any area and compare them with the registry
export default function Census({ user }) {
  const [params, setParams] = useSearchParams()
  const isAdmin = user?.is_admin_role || user?.is_superuser
  const own = { province: user?.province || '', district: user?.district || '', sector: user?.sector || '', cell: user?.cell || '', village: user?.village || '' }
  const [loc, setLoc] = useState(own)
  const [area, setArea] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('sector')
  const [datasets, setDatasets] = useState(null)

  // Deepest chosen level is the area shown; ?location= from a link selects it
  const chosen = LEVELS.map((l) => loc[l]).filter(Boolean).pop() || ''

  useEffect(() => {
    const fromUrl = params.get('location')
    if (!fromUrl) return
    const s = String(fromUrl)
    setLoc({ province: s.slice(0, 1), district: s.length >= 2 ? s.slice(0, 2) : '', sector: s.length >= 4 ? s.slice(0, 4) : '',
             cell: s.length >= 6 ? s.slice(0, 6) : '', village: s.length >= 8 ? s : '' })
  }, [])

  function loadArea() {
    if (!chosen) { setArea(null); return }
    setError('')
    api.censusArea(chosen).then((a) => { setArea(a); setParams({ location: chosen }, { replace: true }) }).catch((e) => setError(e.message))
  }

  useEffect(() => { loadArea() }, [chosen])

  useEffect(() => { api.censusDatasets().then(setDatasets).catch(() => {}) }, [])

  const areas = area?.areas || []
  const current = areas.find((a) => a.level === tab) || areas[0]
  const est = area?.estimate

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Census &amp; population</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            Figures of the National Institute of Statistics of Rwanda (NISR): 2022 census and 2023–2032 projections, compared with the citizen registry.
          </p>
        </div>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div className="section-title" style={{ marginTop: 0 }}>Choose an area</div>
        <div className="loc-inline">
          <LocationSelect value={loc} onChange={setLoc} />
        </div>
        {!isAdmin && <p className="muted small" style={{ margin: 0 }}>Registration coverage is shown for your own area and the areas around it; published census figures are open for the whole country.</p>}
      </div>

      {!chosen ? (
        <p className="muted">Pick a province, district, sector, cell or village above.</p>
      ) : !area ? (
        <div className="card"><Spinner label="Loading census figures…" /></div>
      ) : (
        <>
          {est && (
            <div className="stat-card census-stats" aria-label="Population summary">
              <div className="stat"><span className="stat-value stat-value-sm">{fmt(est.census)}</span><span className="stat-label">Census {area.census_year}</span></div>
              <div className="stat"><span className="stat-value stat-value-sm">{fmt(est.estimate)}</span><span className="stat-label">Estimated {est.year}</span></div>
              <div className="stat"><span className="stat-value stat-value-sm">{fmt(est.male)}</span><span className="stat-label">Male</span></div>
              <div className="stat"><span className="stat-value stat-value-sm">{fmt(est.female)}</span><span className="stat-label">Female</span></div>
              <div className="stat"><span className="stat-value stat-value-sm">{fmt(est.households)}</span><span className="stat-label">Households</span></div>
            </div>
          )}
          {est?.basis && <div className="info-strip"><span>{area.name} ({LEVEL_LABEL[area.level]}): {est.basis}</span></div>}

          {['village', 'cell', 'sector', 'district'].includes(area.level) && (
            <CensusCoverage location={chosen} compact title={`Registered citizens in ${area.name}`} onChanged={loadArea} />
          )}

          {areas.length > 0 && (
            <div className="card" style={{ marginTop: '1.25rem' }}>
              <div className="page-head" style={{ marginBottom: '0.5rem' }}>
                <h2 className="card-title" style={{ margin: 0 }}>Published indicators (census 2022)</h2>
              </div>
              <div className="tabs">
                {areas.map((a) => (
                  <button key={a.level} className={current?.level === a.level ? 'tab tab-active' : 'tab'} onClick={() => setTab(a.level)}>
                    {a.name} · {LEVEL_LABEL[a.level]}
                  </button>
                ))}
              </div>
              {current?.population && (
                <p className="muted small">
                  Resident population {fmt(current.population.total)} ({fmt(current.population.male)} male, {fmt(current.population.female)} female
                  {current.population.urban !== null ? `; ${fmt(current.population.urban)} urban, ${fmt(current.population.rural)} rural` : ''}
                  {current.population.households ? `; ${fmt(current.population.households)} households` : ''}).
                </p>
              )}
              {current && <IndicatorGroups indicators={current.indicators} />}
            </div>
          )}

          {area.projections?.length > 0 && (
            <div className="card" style={{ marginTop: '1.25rem' }}>
              <h2 className="card-title">Projected population of {areas.find((a) => a.level === 'district')?.name} district, 2023–2032</h2>
              <div style={{ overflowX: 'auto' }}>
                <table className="table table-compact">
                  <thead>
                    <tr><th>Year</th><th>Total</th><th>Male</th><th>Female</th><th>Under 5</th><th>Children 0–17</th><th>School age 6–17</th><th>Youth 16–30</th><th>Working age 16–64</th><th>Elderly 60+</th></tr>
                  </thead>
                  <tbody>
                    {area.projections.map((p) => (
                      <tr key={p.year} className={p.year === new Date().getFullYear() ? 'row-current' : ''}>
                        <td><strong>{p.year}</strong></td><td>{fmt(p.total)}</td><td>{fmt(p.male)}</td><td>{fmt(p.female)}</td>
                        <td>{fmt(p.under_5)}</td><td>{fmt(p.children_0_17)}</td><td>{fmt(p.school_6_17)}</td><td>{fmt(p.youth_16_30)}</td><td>{fmt(p.working_16_64)}</td><td>{fmt(p.elderly_60plus)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {datasets && (
        <div className="card" style={{ marginTop: '1.25rem' }}>
          <h2 className="card-title">Datasets loaded</h2>
          <table className="table table-compact">
            <thead><tr><th>Dataset</th><th>Rows</th><th>Years</th><th>Levels</th><th>Source</th></tr></thead>
            <tbody>
              {datasets.datasets.map((d, i) => (
                <tr key={i}><td>{d.dataset}</td><td>{fmt(d.rows)}</td><td>{d.years}</td><td>{d.levels.map((l) => LEVEL_LABEL[l]).join(', ')}</td><td className="muted small">{d.source}</td></tr>
              ))}
            </tbody>
          </table>
          {can(user, 'manage:census') && <p className="muted small" style={{ marginBottom: 0 }}>Cells and villages have no NISR count: open an area above and use “Local count” to enter the number your office counted.</p>}
        </div>
      )}
    </div>
  )
}
