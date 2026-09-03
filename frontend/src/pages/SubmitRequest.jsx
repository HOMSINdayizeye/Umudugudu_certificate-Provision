import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

const CERT_TYPES = [
  { value: 'conduct', label: 'Conduct' },
  { value: 'residence', label: 'Residence Recognition' },
  { value: 'community', label: 'Community Engagement' },
  { value: 'stolen_computer', label: 'Stolen Computer' },
  { value: 'other', label: 'Other' },
]

const emptyDevice = {
  registration_number: '', national_id: '', stolen_datetime: '', location: '',
  device_type: 'Laptop', brand: 'Lenovo', model: '', serial_number: '',
  intel_core: 'i3', ram: '4GB', storage: 'SSD',
  witness_1_name: '', witness_1_phone: '',
  witness_2_name: '', witness_2_phone: '',
  witness_3_name: '', witness_3_phone: '',
  reported_to_police: false, other_description: '',
}

export default function SubmitRequest() {
  const navigate = useNavigate()
  const [certType, setCertType] = useState('conduct')
  const [otherDescription, setOtherDescription] = useState('')
  const [device, setDevice] = useState(emptyDevice)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Hierarchical location state (conduct certificates)
  const [options, setOptions] = useState({ provinces: [], districts: [], sectors: [], cells: [], villages: [] })
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })

  useEffect(() => {
    api.provinces().then((p) => setOptions((o) => ({ ...o, provinces: p }))).catch(() => {})
  }, [])

  async function pick(level, value) {
    const next = { ...loc, [level]: value }
    const chain = ['province', 'district', 'sector', 'cell', 'village']
    // Clear all levels below the one just changed
    for (const l of chain.slice(chain.indexOf(level) + 1)) next[l] = ''
    setLoc(next)

    const loaders = {
      province: () => api.districts(value).then((d) => setOptions((o) => ({ ...o, districts: d, sectors: [], cells: [], villages: [] }))),
      district: () => api.sectors(value).then((d) => setOptions((o) => ({ ...o, sectors: d, cells: [], villages: [] }))),
      sector: () => api.cells(value).then((d) => setOptions((o) => ({ ...o, cells: d, villages: [] }))),
      cell: () => api.villages(value).then((d) => setOptions((o) => ({ ...o, villages: d }))),
    }
    if (value && loaders[level]) await loaders[level]().catch(() => {})
  }

  function setDev(field) {
    return (e) => {
      const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
      setDevice({ ...device, [field]: value })
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = { cert_type: certType }
      if (certType === 'other') payload.other_description = otherDescription
      if (certType === 'conduct') {
        if (!loc.province) throw new Error('Please select a location for the conduct certificate.')
        payload.province = loc.province || null
        payload.district = loc.district || null
        payload.sector = loc.sector || null
        payload.cell = loc.cell || null
        payload.village = loc.village || null
        payload.location_code = loc.village || loc.cell || loc.sector || loc.district || loc.province
      }
      if (certType === 'stolen_computer') {
        payload.stolen_device = device
      }
      await api.createRequest(payload)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const locationLevels = [
    ['province', 'Province', options.provinces],
    ['district', 'District', options.districts],
    ['sector', 'Sector', options.sectors],
    ['cell', 'Cell', options.cells],
    ['village', 'Village', options.villages],
  ]

  return (
    <div>
      <div className="page-head"><h1>Submit Certificate Request</h1></div>
      {error && <div className="alert alert-error">{error}</div>}

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Certificate type</label>
          <select value={certType} onChange={(e) => setCertType(e.target.value)}>
            {CERT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        {certType === 'other' && (
          <div className="form-group">
            <label>Describe the certificate you need</label>
            <textarea rows={3} value={otherDescription} onChange={(e) => setOtherDescription(e.target.value)} required />
          </div>
        )}

        {certType === 'conduct' && (
          <>
            <div className="section-title">Your location</div>
            {locationLevels.map(([level, label, opts]) => (
              <div className="form-group" key={level}>
                <label>{label}</label>
                <select
                  value={loc[level]}
                  onChange={(e) => pick(level, e.target.value)}
                  disabled={level !== 'province' && opts.length === 0}
                >
                  <option value="">— Select {label} —</option>
                  {opts.map((o) => <option key={o.location_id} value={o.location_id}>{o.name}</option>)}
                </select>
              </div>
            ))}
          </>
        )}

        {certType === 'stolen_computer' && (
          <>
            <div className="section-title">Incident details</div>
            <div className="form-row">
              <div className="form-group">
                <label>Registration number</label>
                <input value={device.registration_number} onChange={setDev('registration_number')} required />
              </div>
              <div className="form-group">
                <label>National ID</label>
                <input value={device.national_id} onChange={setDev('national_id')} maxLength={16} required />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Date & time stolen</label>
                <input type="datetime-local" value={device.stolen_datetime} onChange={setDev('stolen_datetime')} required />
              </div>
              <div className="form-group">
                <label>Location of incident</label>
                <input value={device.location} onChange={setDev('location')} required />
              </div>
            </div>

            <div className="section-title">Device description</div>
            <div className="form-row">
              <div className="form-group">
                <label>Device type</label>
                <select value={device.device_type} onChange={setDev('device_type')}>
                  <option>Laptop</option><option>Tablet</option>
                </select>
              </div>
              <div className="form-group">
                <label>Brand</label>
                <select value={device.brand} onChange={setDev('brand')}>
                  <option>Lenovo</option><option>HP</option><option>Dell</option><option>Mac</option>
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Model</label>
                <input value={device.model} onChange={setDev('model')} required />
              </div>
              <div className="form-group">
                <label>Serial number</label>
                <input value={device.serial_number} onChange={setDev('serial_number')} required />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Processor</label>
                <select value={device.intel_core} onChange={setDev('intel_core')}>
                  <option value="i3">Intel Core i3</option>
                  <option value="i5">Intel Core i5</option>
                  <option value="i7">Intel Core i7</option>
                </select>
              </div>
              <div className="form-group">
                <label>RAM</label>
                <select value={device.ram} onChange={setDev('ram')}>
                  <option>4GB</option><option>8GB</option><option>16GB</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Storage</label>
              <select value={device.storage} onChange={setDev('storage')}>
                <option value="SSD">SSD</option>
                <option value="HDD">Hard Disk</option>
              </select>
            </div>

            <div className="section-title">Witnesses</div>
            {[1, 2, 3].map((n) => (
              <div className="form-row" key={n}>
                <div className="form-group">
                  <label>Witness {n} name</label>
                  <input value={device[`witness_${n}_name`]} onChange={setDev(`witness_${n}_name`)} required={n === 1} />
                </div>
                <div className="form-group">
                  <label>Witness {n} phone</label>
                  <input value={device[`witness_${n}_phone`]} onChange={setDev(`witness_${n}_phone`)} maxLength={15} required={n === 1} />
                </div>
              </div>
            ))}

            <div className="form-group checkbox-row">
              <input type="checkbox" id="police" checked={device.reported_to_police} onChange={setDev('reported_to_police')} />
              <label htmlFor="police" style={{ margin: 0 }}>Reported to police</label>
            </div>
            <div className="form-group">
              <label>Additional details (optional)</label>
              <textarea rows={2} value={device.other_description} onChange={setDev('other_description')} />
            </div>
          </>
        )}

        <button className="btn" disabled={loading}>{loading ? 'Submitting…' : 'Submit Request'}</button>
      </form>
    </div>
  )
}
