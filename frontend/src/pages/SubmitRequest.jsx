import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, getUser } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'

// ---------- document types shown as option cards ----------
const Icon = {
  doc: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></svg>,
  home: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 11 12 4l9 7" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></svg>,
  laptop: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="5" width="16" height="11" /><path d="M2 19h20" /></svg>,
  people: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="9" cy="8" r="3.2" /><circle cx="17" cy="9" r="2.5" /><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" /><path d="M15.5 14.5c2.8 0 5.5 2 5.5 5.5" /></svg>,
  pen: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h4l10-10-4-4L4 16z" /><path d="M13 7l4 4" /></svg>,
}

const TYPES = [
  {
    value: 'conduct', title: 'Certificate of Conduct', rw: "Icyangombwa cy'imico n'imyifatire", icon: Icon.doc, tile: '',
    desc: 'Confirms you are a known resident of good conduct, needed by the cell for jobs, school or travel.',
    needs: ['National ID copy', 'Student card if you are a student'],
  },
  {
    value: 'residence', title: 'Residence Recognition', rw: 'Icyangombwa kigaragaza ko umuturage azwi', icon: Icon.home, tile: 'green',
    desc: 'Certifies that you live in this village and since when. Valid for 30 days.',
    needs: ['National ID or passport copy', 'Proof of residence (tenancy, hostel allocation)'],
  },
  {
    value: 'stolen_computer', title: 'Stolen Device Report', rw: 'Raporo ya mudasobwa yibwe', icon: Icon.laptop, tile: 'amber',
    desc: 'Official report of a stolen laptop, phone or other device for the police, insurer or your school.',
    needs: ['National ID or passport copy', 'Proof of ownership (receipt, photo of serial)'],
  },
  {
    value: 'community', title: 'Community Engagement Referral', rw: 'Ibaruwa igaragaza uruhare mu bikorwa rusange', icon: Icon.people, tile: 'purple',
    desc: 'A referral letter confirming your participation in Umuganda and community activities.',
    needs: ['National ID copy', 'Photos or lists showing participation (optional)'],
  },
  {
    value: 'other', title: 'Other Document', rw: 'Ikindi cyangombwa', icon: Icon.pen, tile: '',
    desc: 'Any other attestation from the village office. Describe what you need and why.',
    needs: ['Any document that supports your request'],
  },
]

const ATTACHMENT_KINDS = [
  ['national_id', 'National ID / Passport'],
  ['student_card', 'Student Card'],
  ['proof', 'Proof / Supporting Document'],
  ['photo', 'Photo'],
  ['other', 'Other'],
]

const STEPS = ['Applicant', 'Details', 'Documents', 'Review']

// Only these detail fields are sent for each document type, so defaults for other types never leak into the letter
const BIRTH = ['birth_country', 'birth_province', 'birth_district', 'birth_sector', 'birth_cell', 'birth_village']
const RELEVANT_FIELDS = {
  conduct: ['full_name', 'gender', 'national_id', 'dob', 'id_issue_district', 'id_issue_sector', 'father_name', 'mother_name',
    ...BIRTH, 'occupation_type', 'school', 'department', 'year_of_study', 'occupation', 'purpose'],
  residence: ['full_name', 'national_id', 'id_issue_district', 'id_issue_sector', 'dob', 'resident_since', 'father_name',
    'mother_name', ...BIRTH, 'purpose'],
  stolen_computer: ['full_name', 'gender', 'id_type', 'id_number', 'nationality', 'registration_number', 'institution',
    'incident_date', 'incident_time', 'incident_location', 'device_type', 'brand', 'model', 'serial_number', 'processor',
    'ram', 'storage', 'color', 'other_description', 'witnesses', 'reported_to', 'reported_to_police'],
  community: ['full_name', 'gender', 'national_id', 'activities', 'purpose'],
  other: ['full_name', 'subject'],
}

const LABELS = {
  full_name: 'Full name', gender: 'Gender', national_id: 'National ID', id_number: 'ID / Passport number', id_type: 'ID type',
  dob: 'Date of birth', father_name: "Father's name", mother_name: "Mother's name", id_issue_district: 'ID issued in district',
  id_issue_sector: 'ID issued in sector', birth_country: 'Country of birth', birth_province: 'Province of birth',
  birth_district: 'District of birth', birth_sector: 'Sector of birth', birth_cell: 'Cell of birth', birth_village: 'Village of birth',
  occupation_type: 'Applicant is', school: 'School', department: 'Department', year_of_study: 'Year of study', occupation: 'Occupation',
  purpose: 'Purpose', resident_since: 'Resident since', nationality: 'Nationality', registration_number: 'Registration number',
  institution: 'Institution', incident_date: 'Incident date', incident_time: 'Incident time', incident_location: 'Incident location',
  device_type: 'Device type', brand: 'Brand', model: 'Model', serial_number: 'Serial number', processor: 'Processor', ram: 'RAM',
  storage: 'Storage', color: 'Colour', other_description: 'Other details', reported_to: 'Reported to', reported_to_police: 'Reported to police',
  activities: 'Community activities', subject: 'Subject',
}

// Field components live at module level so React keeps the same input mounted while the user types
function F({ label, name, type = 'text', required, placeholder, hint, children, details, set }) {
  return (
    <div className="form-group">
      <label>{label}{required && <span className="req"> *</span>}</label>
      {children || (
        <input type={type} value={details[name] || ''} onChange={set(name)} required={required} placeholder={placeholder} />
      )}
      {hint && <div className="field-hint muted">{hint}</div>}
    </div>
  )
}

function GenderSelect(fp) {
  return (
    <F {...fp} label="Gender" name="gender">
      <select value={fp.details.gender || 'male'} onChange={fp.set('gender')}>
        <option value="male">Male</option>
        <option value="female">Female</option>
      </select>
    </F>
  )
}

function BirthPlace(fp) {
  return (
    <>
      <div className="section-title">Place of birth (Aho yavukiye)</div>
      <div className="form-row">
        <F {...fp} label="Country" name="birth_country" placeholder="Rwanda" />
        <F {...fp} label="Province (Intara)" name="birth_province" placeholder="e.g. Amajyaruguru" />
      </div>
      <div className="form-row">
        <F {...fp} label="District (Akarere)" name="birth_district" />
        <F {...fp} label="Sector (Umurenge)" name="birth_sector" />
      </div>
      <div className="form-row">
        <F {...fp} label="Cell (Akagari)" name="birth_cell" />
        <F {...fp} label="Village (Umudugudu)" name="birth_village" />
      </div>
    </>
  )
}

function IdIssue(fp) {
  return (
    <div className="form-row">
      <F {...fp} label="ID issued in district" name="id_issue_district" placeholder="e.g. Gicumbi" />
      <F {...fp} label="ID issued in sector" name="id_issue_sector" placeholder="e.g. Muko" />
    </div>
  )
}

function Parents(fp) {
  return (
    <div className="form-row">
      <F {...fp} label="Father's name" name="father_name" required />
      <F {...fp} label="Mother's name" name="mother_name" required />
    </div>
  )
}

export default function SubmitRequest() {
  const navigate = useNavigate()
  const user = getUser()
  const formRef = useRef(null)
  const [certType, setCertType] = useState(null)
  const [step, setStep] = useState(0) // 0 = choose type, 1..4 = STEPS
  const [otherDescription, setOtherDescription] = useState('')
  const [details, setDetails] = useState({ occupation_type: 'student', gender: 'male', id_type: 'national_id', device_type: 'Laptop', witnesses: [{ name: '', phone: '' }] })
  const [files, setFiles] = useState([]) // [{kind, file}]
  const [pendingKind, setPendingKind] = useState('national_id')
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })
  const [error, setError] = useState('')
  const [progress, setProgress] = useState('')
  const [loading, setLoading] = useState(false)

  const needsLocation = !user?.village
  const type = TYPES.find((t) => t.value === certType)

  function set(field) {
    return (e) => {
      const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
      setDetails((d) => ({ ...d, [field]: value }))
    }
  }

  function setWitness(i, field, value) {
    setDetails((d) => {
      const witnesses = [...(d.witnesses || [])]
      witnesses[i] = { ...witnesses[i], [field]: value }
      return { ...d, witnesses }
    })
  }

  function addFiles(e) {
    const chosen = Array.from(e.target.files || [])
    setFiles((f) => [...f, ...chosen.map((file) => ({ kind: pendingKind, file }))])
    e.target.value = ''
  }

  function choose(value) {
    setCertType(value)
    setStep(1)
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Only the current step's fields are mounted, so native validation checks exactly what is on screen
  function next() {
    const form = formRef.current
    if (form && !form.checkValidity()) {
      form.reportValidity()
      return
    }
    if (step === 1 && needsLocation && !loc.village) {
      setError('Please select your location down to the village.')
      return
    }
    setError('')
    setStep((s) => Math.min(s + 1, STEPS.length))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function back() {
    setError('')
    setStep((s) => Math.max(s - 1, 0))
  }

  function relevantDetails() {
    const relevant = Object.fromEntries(Object.entries(details).filter(([k]) => RELEVANT_FIELDS[certType].includes(k)))
    if (certType === 'conduct' && relevant.occupation_type !== 'student') {
      delete relevant.school; delete relevant.department; delete relevant.year_of_study
    }
    if (certType === 'conduct' && relevant.occupation_type === 'student') delete relevant.occupation
    if (certType === 'stolen_computer') relevant.witnesses = (relevant.witnesses || []).filter((w) => (w.name || '').trim())
    return relevant
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (step < STEPS.length) { next(); return }
    setError('')
    setLoading(true)
    try {
      const payload = { cert_type: certType, details: relevantDetails() }
      if (certType === 'other') payload.other_description = otherDescription
      if (needsLocation) Object.assign(payload, loc, { location_code: loc.village })
      setProgress('Submitting…')
      const created = await api.createRequest(payload)

      // Upload files grouped by kind so each keeps its label
      const byKind = {}
      for (const { kind, file } of files) (byKind[kind] ||= []).push(file)
      let n = 0
      for (const [kind, list] of Object.entries(byKind)) {
        n += list.length
        setProgress(`Uploading documents (${n}/${files.length})…`)
        await api.uploadAttachments(created.id, kind, list)
      }
      navigate(`/requests/${created.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setProgress('')
    }
  }

  const fp = { details, set }

  // ---------- Step 0: choose the document ----------
  if (step === 0) {
    return (
      <div>
        <div className="page-title">
          <h1>What Would You Like To Apply For?</h1>
          <p>Select a document to get started. The letter is issued by the leader of {user?.village_name || 'your village'}.</p>
        </div>
        <div className="option-grid">
          {TYPES.map((t) => (
            <button type="button" className="option-card" key={t.value} onClick={() => choose(t.value)}>
              <span className={`icon-tile ${t.tile}`}>{t.icon}</span>
              <h2>{t.title}</h2>
              <div className="rw">{t.rw}</div>
              <p>{t.desc}</p>
              <ul className="option-list">
                {t.needs.map((n) => <li key={n}>{n}</li>)}
              </ul>
              <span className="arrow-link">Apply →</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  const relevant = step === STEPS.length ? relevantDetails() : {}

  return (
    <div>
      <div className="page-title">
        <h1>{type.title}</h1>
        <p>{type.rw}</p>
      </div>

      <ol className="steps">
        {STEPS.map((label, i) => {
          const n = i + 1
          const cls = n === step ? 'step step-active' : n < step ? 'step step-done' : 'step'
          return (
            <li key={label}>
              <button type="button" className={cls} onClick={() => n < step && setStep(n)} disabled={n > step}>
                <span className="step-num">{n < step ? '✓' : n}</span>{label}
              </button>
            </li>
          )
        })}
      </ol>

      {error && <div className="alert alert-error">{error}</div>}

      <form className="card" onSubmit={handleSubmit} ref={formRef} noValidate={false}>
        {/* ---------- Step 1: Applicant ---------- */}
        {step === 1 && (
          <>
            <div className="info-strip">
              <span>ℹ️</span>
              <span>Fill in the details exactly as they appear on your identity document. They are printed on the letter.</span>
            </div>
            <div className="section-title">Applicant</div>
            <div className="form-row">
              <F {...fp} label="Full name (as on ID)" name="full_name" required={certType !== 'other'} placeholder="SURNAME Firstname" />
              {certType !== 'residence' && certType !== 'other' && <GenderSelect {...fp} />}
              {certType === 'residence' && <F {...fp} label="Date of birth" name="dob" type="date" required />}
            </div>

            {certType === 'conduct' && (
              <div className="form-row">
                <F {...fp} label="National ID number" name="national_id" required />
                <F {...fp} label="Date of birth" name="dob" type="date" required />
              </div>
            )}
            {certType === 'residence' && (
              <F {...fp} label="National ID / Passport number" name="national_id" required />
            )}
            {(certType === 'conduct' || certType === 'residence') && <IdIssue {...fp} />}

            {certType === 'stolen_computer' && (
              <>
                <div className="form-row">
                  <F {...fp} label="Identity document" name="id_type">
                    <select value={details.id_type || 'national_id'} onChange={set('id_type')}>
                      <option value="national_id">National ID</option>
                      <option value="passport">Passport</option>
                    </select>
                  </F>
                  <F {...fp} label="ID / Passport number" name="id_number" required />
                </div>
                <div className="form-row">
                  <F {...fp} label="Nationality (if not Rwandan)" name="nationality" />
                  <F {...fp} label="Student registration number" name="registration_number" placeholder="e.g. 222005089" />
                </div>
                <F {...fp} label="Institution" name="institution" placeholder="University of Rwanda" />
              </>
            )}
            {certType === 'community' && <F {...fp} label="National ID number" name="national_id" required />}

            {needsLocation && (
              <>
                <div className="section-title">Your residence</div>
                <p className="muted small">Your account has no village yet. Select where you live so the right leader receives the request.</p>
                <LocationSelect value={loc} onChange={setLoc} progressive />
              </>
            )}
          </>
        )}

        {/* ---------- Step 2: Details ---------- */}
        {step === 2 && certType === 'conduct' && (
          <>
            <div className="section-title">Parents</div>
            <Parents {...fp} />
            <BirthPlace {...fp} />
            <div className="section-title">Occupation</div>
            <F {...fp} label="You are a" name="occupation_type">
              <select value={details.occupation_type || 'student'} onChange={set('occupation_type')}>
                <option value="student">Student</option>
                <option value="worker">Worker / other</option>
              </select>
            </F>
            {details.occupation_type === 'student' ? (
              <>
                <div className="form-row">
                  <F {...fp} label="School / Campus" name="school" placeholder="UR-CST Nyarugenge Campus" />
                  <F {...fp} label="Department / Programme" name="department" placeholder="e.g. Information Systems" />
                </div>
                <F {...fp} label="Year of study" name="year_of_study" placeholder="e.g. 3" />
              </>
            ) : (
              <F {...fp} label="Occupation" name="occupation" placeholder="e.g. umukozi muri resitora (Restaurant)" />
            )}
            <F {...fp} label="Purpose (optional)" name="purpose" placeholder="Why do you need this certificate?" />
          </>
        )}

        {step === 2 && certType === 'residence' && (
          <>
            <div className="section-title">Residence</div>
            <F {...fp} label="Resident here since" name="resident_since" type="month" required hint="Month and year you moved to this village" />
            <div className="section-title">Parents</div>
            <Parents {...fp} />
            <BirthPlace {...fp} />
            <F {...fp} label="Purpose (optional)" name="purpose" />
          </>
        )}

        {step === 2 && certType === 'stolen_computer' && (
          <>
            <div className="section-title">Incident</div>
            <div className="form-row">
              <F {...fp} label="Date" name="incident_date" type="date" required />
              <F {...fp} label="Approximate time" name="incident_time" placeholder="e.g. 11:20 AM" />
            </div>
            <F {...fp} label="Location" name="incident_location" required placeholder="e.g. MUHABURA Building (UR-CST), room 0R01" />

            <div className="section-title">Device</div>
            <div className="form-row">
              <F {...fp} label="Device type" name="device_type" required>
                <select value={details.device_type || 'Laptop'} onChange={set('device_type')}>
                  {['Laptop', 'Desktop Computer', 'Tablet', 'Mobile Phone', 'Other Electronic Device'].map((o) => <option key={o}>{o}</option>)}
                </select>
              </F>
              <F {...fp} label="Brand" name="brand" required placeholder="e.g. HP, Lenovo, Dell" />
            </div>
            <div className="form-row">
              <F {...fp} label="Model" name="model" placeholder="e.g. ProBook 450 G8" />
              <F {...fp} label="Serial number" name="serial_number" required />
            </div>
            <div className="form-row">
              <F {...fp} label="Processor" name="processor" placeholder="e.g. Intel Core i5" />
              <F {...fp} label="RAM" name="ram" placeholder="e.g. 8GB" />
            </div>
            <div className="form-row">
              <F {...fp} label="Storage" name="storage" placeholder="e.g. 512GB SSD" />
              <F {...fp} label="Colour" name="color" />
            </div>
            <F {...fp} label="Other identifying details (optional)" name="other_description">
              <textarea rows={2} value={details.other_description || ''} onChange={set('other_description')} placeholder="Stickers, cracks, bag it was in, what else was taken…" />
            </F>

            <div className="section-title">People informed / witnesses</div>
            {(details.witnesses || []).map((w, i) => (
              <div className="form-row" key={i}>
                <div className="form-group">
                  <label>Name {i + 1}</label>
                  <input value={w.name || ''} onChange={(e) => setWitness(i, 'name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Phone</label>
                  <input value={w.phone || ''} onChange={(e) => setWitness(i, 'phone', e.target.value)} />
                </div>
              </div>
            ))}
            {(details.witnesses || []).length < 5 && (
              <button type="button" className="btn btn-small btn-ghost" onClick={() => setDetails((d) => ({ ...d, witnesses: [...(d.witnesses || []), { name: '', phone: '' }] }))}>
                + Add another person
              </button>
            )}
            <div style={{ marginTop: '1.25rem' }}>
              <F {...fp} label="Also reported to" name="reported_to" placeholder="e.g. Security officers, UR-SU" />
            </div>
            <div className="form-group checkbox-row">
              <input type="checkbox" id="police" checked={!!details.reported_to_police} onChange={set('reported_to_police')} />
              <label htmlFor="police" style={{ margin: 0 }}>Reported to Rwanda National Police</label>
            </div>
          </>
        )}

        {step === 2 && certType === 'community' && (
          <>
            <div className="section-title">Community engagement</div>
            <F {...fp} label="Community activities you took part in" name="activities" required>
              <textarea rows={4} value={details.activities || ''} onChange={set('activities')} required placeholder="Umuganda, youth programs, public talks, local development initiatives…" />
            </F>
            <F {...fp} label="Purpose of the letter (optional)" name="purpose" placeholder="e.g. scholarship application" />
          </>
        )}

        {step === 2 && certType === 'other' && (
          <>
            <div className="section-title">Your request</div>
            <F {...fp} label="Subject of the letter" name="subject" placeholder="e.g. Attestation of good standing" />
            <div className="form-group">
              <label>Describe the document you need<span className="req"> *</span></label>
              <textarea rows={5} value={otherDescription} onChange={(e) => setOtherDescription(e.target.value)} required />
            </div>
          </>
        )}

        {/* ---------- Step 3: Documents ---------- */}
        {step === 3 && (
          <>
            <div className="section-title">Supporting documents</div>
            <p className="muted small" style={{ marginTop: 0 }}>
              Please attach: {type.needs.join(' · ')}. PDF, JPG, PNG or Word, up to 10 MB each.
            </p>
            <div className="form-row">
              <div className="form-group">
                <label>Document type</label>
                <select value={pendingKind} onChange={(e) => setPendingKind(e.target.value)}>
                  {ATTACHMENT_KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Choose file(s)</label>
                <div className="dropzone">
                  <span className="muted small">Select one or more files for the type chosen on the left</span>
                  <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" onChange={addFiles} />
                </div>
              </div>
            </div>
            {files.length > 0 ? (
              <ul className="file-list">
                {files.map(({ kind, file }, i) => (
                  <li key={i}>
                    <span className="badge badge-kind">{ATTACHMENT_KINDS.find(([v]) => v === kind)?.[1]}</span>
                    <span className="file-name">{file.name}</span>
                    <span className="muted small">{(file.size / 1024).toFixed(0)} KB</span>
                    <button type="button" className="link-btn danger" onClick={() => setFiles((f) => f.filter((_, j) => j !== i))}>remove</button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No files added yet. You can also add documents later, while the request is pending.</p>
            )}
          </>
        )}

        {/* ---------- Step 4: Review ---------- */}
        {step === STEPS.length && (
          <>
            <div className="section-title">Review your application</div>
            <div className="review-grid">
              <div className="review-item"><small>Document</small><span>{type.title}</span></div>
              <div className="review-item"><small>Village</small><span>{user?.village_name || (loc.village ? 'Selected location' : '—')}</span></div>
              {Object.entries(relevant).map(([k, v]) => {
                if (k === 'witnesses') return null
                const pretty = { male: 'Male', female: 'Female', national_id: 'National ID', passport: 'Passport', student: 'Student', worker: 'Worker / other' }
                const text = v === true ? 'Yes' : v === false ? 'No' : (['gender', 'id_type', 'occupation_type'].includes(k) ? pretty[v] : null) ?? String(v ?? '').trim()
                if (!text) return null
                return <div className="review-item" key={k}><small>{LABELS[k] || k}</small><span>{text}</span></div>
              })}
              {certType === 'other' && <div className="review-item" style={{ gridColumn: '1 / -1' }}><small>Description</small><span>{otherDescription}</span></div>}
              {(relevant.witnesses || []).length > 0 && (
                <div className="review-item" style={{ gridColumn: '1 / -1' }}>
                  <small>People informed</small>
                  <span>{relevant.witnesses.map((w) => w.name + (w.phone ? ` (${w.phone})` : '')).join(', ')}</span>
                </div>
              )}
              <div className="review-item" style={{ gridColumn: '1 / -1' }}>
                <small>Documents</small>
                <span>{files.length ? files.map((f) => f.file.name).join(', ') : 'None attached'}</span>
              </div>
            </div>
            <div className="info-strip" style={{ marginTop: '1.5rem', marginBottom: 0 }}>
              <span>✔</span>
              <span>By submitting, you confirm the information above is true. The village leader will review it and you will be notified here.</span>
            </div>
          </>
        )}

        <div className="form-actions">
          <button type="button" className="btn btn-ghost" onClick={back} disabled={loading}>
            ← {step === 1 ? 'Change document' : 'Back'}
          </button>
          {step < STEPS.length ? (
            <button type="button" className="btn" onClick={next}>Continue →</button>
          ) : (
            <button className="btn" disabled={loading}>{loading ? (progress || 'Submitting…') : 'Submit Application'}</button>
          )}
        </div>
      </form>
    </div>
  )
}
