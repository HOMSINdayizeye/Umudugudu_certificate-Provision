import { useEffect, useState } from 'react'
import { api, saveBlob } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'

// Split an 8-digit village id into the ids the cascading selector expects
function locFromVillage(village) {
  const s = village ? String(village) : ''
  return {
    province: s.slice(0, 1), district: s.slice(0, 2), sector: s.slice(0, 4), cell: s.slice(0, 6), village: s,
  }
}

const KINDS = [
  ['umuganda', 'Community Work (Umuganda)'],
  ['meeting', 'Meeting / Gathering'],
  ['general', 'General Announcement'],
]

const today = () => new Date().toISOString().slice(0, 10)

// Default wording per language for the parts that rarely change
const DEFAULTS = {
  en: {
    partner: 'the University of Rwanda Student Union (UR-SU)',
    reminder: 'As responsible citizens, we are expected to adhere to this schedule properly and on time ("Whoever neglects their duty knowingly commits an offense.")',
    note: 'All Campus activities will resume after the community work.',
  },
  rw: {
    partner: "Ihuriro ry'Abanyeshuri ba Kaminuza y'u Rwanda (UR-SU)",
    reminder: "Nk'abaturage b'inyangamugayo, twese dusabwa kubahiriza iyi gahunda no kugera ku gihe (\"Uwirengagiza inshingano ze abigambiriye aba akoze icyaha.\")",
    note: "Ibikorwa byose bya Kaminuza bizasubukurwa umuganda urangiye.",
  },
}

const EMPTY = {
  kind: 'umuganda', language: 'en', title: '', letter_date: today(), event_date: '', start_time: '',
  venue: '', gathering_point: '', partner: DEFAULTS.en.partner, audience: '', meeting_points: [{ audience: '', place: '', time: '' }],
  location_details: '', activities: '', reminder: DEFAULTS.en.reminder, body: '', note: DEFAULTS.en.note, published: false,
}

export default function Announcements({ user }) {
  const [items, setItems] = useState([])
  const [canCreate, setCanCreate] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [preview, setPreview] = useState(null)
  // Letterhead location: the leader's own village unless changed
  const [loc, setLoc] = useState(locFromVillage(user?.village))
  const [changingLoc, setChangingLoc] = useState(!user?.village)
  const [prevLoc, setPrevLoc] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')

  async function load() {
    try {
      const data = await api.listAnnouncements()
      setItems(data.announcements)
      setCanCreate(data.can_create)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  // Pick up the village once the user profile has refreshed
  useEffect(() => {
    if (user?.village && !loc.village && !editingId) {
      setLoc(locFromVillage(user.village))
      setChangingLoc(false)
    }
  }, [user?.village])

  // Live preview: refresh the letter text shortly after the leader stops typing
  useEffect(() => {
    if (!canCreate || !loc.village) return
    const t = setTimeout(() => {
      api.previewAnnouncement({ ...form, village: loc.village }).then(setPreview).catch(() => {})
    }, 350)
    return () => clearTimeout(t)
  }, [form, loc.village, canCreate])

  function set(field) {
    return (e) => {
      const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
      setForm((f) => {
        const next = { ...f, [field]: value }
        // Switching language swaps the default sentences, but never overwrites text the leader edited
        if (field === 'language') {
          for (const k of ['partner', 'reminder', 'note']) {
            if (!f[k] || f[k] === DEFAULTS[f.language][k]) next[k] = DEFAULTS[value][k]
          }
        }
        return next
      })
    }
  }

  function setPoint(i, field, value) {
    setForm((f) => {
      const meeting_points = [...(f.meeting_points || [])]
      meeting_points[i] = { ...meeting_points[i], [field]: value }
      return { ...f, meeting_points }
    })
  }
  function addPoint() {
    setForm((f) => ({ ...f, meeting_points: [...(f.meeting_points || []), { audience: '', place: '', time: '' }] }))
  }
  function removePoint(i) {
    setForm((f) => ({ ...f, meeting_points: (f.meeting_points || []).filter((_, j) => j !== i) }))
  }

  function startEdit(a) {
    setEditingId(a.id)
    setLoc(locFromVillage(a.village))
    setChangingLoc(false)
    setForm({
      kind: a.kind, language: a.language, title: a.title, letter_date: a.letter_date, event_date: a.event_date || '',
      start_time: a.start_time, venue: a.venue, gathering_point: a.gathering_point, partner: a.partner,
      audience: a.audience, body: a.body, note: a.note, published: a.published,
      location_details: a.location_details || '', activities: a.activities || '', reminder: a.reminder || '',
      // Older announcements stored a single pair; show it as the first point
      meeting_points: a.meeting_points?.length ? a.meeting_points : a.gathering_point ? [{ audience: a.audience, place: a.gathering_point, time: '' }] : [],
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function reset() {
    setEditingId(null)
    setForm(EMPTY)
    setLoc(locFromVillage(user?.village))
    setChangingLoc(!user?.village)
  }

  // andDownload: hand the leader the .docx right after saving
  async function save(e, andDownload = false) {
    e?.preventDefault()
    setError(''); setNotice(''); setBusy(andDownload ? 'save-download' : 'save')
    try {
      if (!loc.village) throw new Error('Choose the village for the letterhead first.')
      const payload = {
        ...form, event_date: form.event_date || null, village: Number(loc.village),
        meeting_points: (form.meeting_points || []).filter((p) => (p.place || '').trim()),
        gathering_point: '', audience: '',
      }
      let saved
      if (editingId) {
        saved = await api.updateAnnouncement(editingId, payload)
        setNotice('Announcement updated.')
      } else {
        saved = await api.createAnnouncement(payload)
        setNotice('Announcement saved. Use Download in the list below whenever you need the letter again.')
      }
      if (andDownload) saveBlob(await api.downloadAnnouncement(saved.id))
      reset()
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function download(a) {
    setError('')
    try {
      saveBlob(await api.downloadAnnouncement(a.id))
    } catch (err) {
      setError(err.message)
    }
  }

  async function togglePublish(a) {
    setError('')
    try {
      await api.updateAnnouncement(a.id, { published: !a.published })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(a) {
    if (!window.confirm('Delete this announcement?')) return
    setError('')
    try {
      await api.deleteAnnouncement(a.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const isUmuganda = form.kind === 'umuganda'
  const rw = form.language === 'rw'

  return (
    <div>
      <div className="page-head"><h1>Announcements</h1></div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {canCreate && (
        <div className="two-col" style={{ marginBottom: '1.5rem' }}>
          <form className="card" onSubmit={save}>
            <h2 className="card-title">{editingId ? `Edit announcement #${editingId}` : 'New announcement'}</h2>

            <div className="form-group">
              <label>Letterhead (City / District / Sector / Cell / Village)</label>
              {!changingLoc ? (
                <div className="loc-summary">
                  <span>
                    {preview?.letterhead
                      ? [preview.letterhead.province, preview.letterhead.district, preview.letterhead.sector, preview.letterhead.cell, preview.letterhead.village].filter(Boolean).join(' › ')
                      : user?.village_name || 'Your village'}
                  </span>
                  <button type="button" className="link-btn" onClick={() => { setPrevLoc(loc); setLoc(locFromVillage(null)); setChangingLoc(true) }}>Change</button>
                </div>
              ) : (
                <div className="loc-picker">
                  <LocationSelect value={loc} onChange={setLoc} progressive />
                  <div className="btn-row" style={{ marginTop: '0.75rem' }}>
                    {loc.village && <button type="button" className="btn btn-small" onClick={() => setChangingLoc(false)}>Use this village</button>}
                    {prevLoc?.village && <button type="button" className="link-btn" onClick={() => { setLoc(prevLoc); setChangingLoc(false) }}>Keep current</button>}
                  </div>
                </div>
              )}
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Type</label>
                <select value={form.kind} onChange={set('kind')}>
                  {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Language</label>
                <select value={form.language} onChange={set('language')}>
                  <option value="en">English</option>
                  <option value="rw">Kinyarwanda</option>
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Letter date</label>
                <input type="date" value={form.letter_date} onChange={set('letter_date')} required />
              </div>
              <div className="form-group">
                <label>{isUmuganda ? 'Umuganda date' : 'Event date'}</label>
                <input type="date" value={form.event_date} onChange={set('event_date')} />
              </div>
            </div>
            <div className="form-group">
              <label>Heading {isUmuganda && <span className="muted small">(leave empty for {rw ? 'ITANGAZO' : 'ANNOUNCEMENT'})</span>}</label>
              <input value={form.title} onChange={set('title')} placeholder={isUmuganda ? '' : rw ? 'e.g. Inama y\'abaturage' : 'e.g. Village General Meeting'} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Start time</label>
                <input value={form.start_time} onChange={set('start_time')} placeholder={rw ? 'e.g. 8h00' : 'e.g. 8:00 AM'} />
              </div>
              <div className="form-group">
                <label>Venue</label>
                <input value={form.venue} onChange={set('venue')} placeholder="e.g. GANZA village" />
              </div>
            </div>
            {isUmuganda && (
              <>
                <div className="form-group">
                  <label>Gathering points <span className="muted small" style={{ textTransform: 'none', letterSpacing: 0 }}>(optional)</span></label>
                  {(form.meeting_points || []).map((p, i) => (
                    <div className="point-row" key={i}>
                      <div className="form-group">
                        <label>Who</label>
                        <input value={p.audience || ''} onChange={(e) => setPoint(i, 'audience', e.target.value)} placeholder={rw ? 'e.g. Abanyeshuri ba MUHABURA (ubusa = Twese)' : 'e.g. Students from MUHABURA Hostel (empty = We will all)'} />
                      </div>
                      <div className="form-group">
                        <label>Gather at</label>
                        <input value={p.place || ''} onChange={(e) => setPoint(i, 'place', e.target.value)} placeholder="e.g. DUSAIDI Hall" />
                      </div>
                      <div className="form-group">
                        <label>Time</label>
                        <input value={p.time || ''} onChange={(e) => setPoint(i, 'time', e.target.value)} placeholder={rw ? '8h00' : '8:00 AM'} />
                      </div>
                      <button type="button" className="link-btn danger" onClick={() => removePoint(i)}>remove</button>
                    </div>
                  ))}
                  <button type="button" className="btn btn-small btn-ghost" onClick={addPoint}>
                    + {form.meeting_points?.length ? 'Add another gathering point' : 'Add a gathering point'}
                  </button>
                </div>
                <div className="form-group">
                  <label>What will be done <span className="muted small" style={{ textTransform: 'none', letterSpacing: 0 }}>(optional; if empty the letter says details will be shared at the gathering point)</span></label>
                  <textarea rows={2} value={form.activities} onChange={set('activities')} placeholder={rw ? 'e.g. gusukura imihanda no gutema ibihuru' : 'e.g. cleaning the roadside and clearing bushes'} />
                </div>
                <div className="form-group">
                  <label>Location details <span className="muted small" style={{ textTransform: 'none', letterSpacing: 0 }}>(shown in brackets after that sentence)</span></label>
                  <input value={form.location_details} onChange={set('location_details')} placeholder="e.g. Outside Campus with NYARUGENGE SECTOR Citizens, APE Rugunga" />
                </div>
                <div className="form-group">
                  <label>In collaboration with</label>
                  <input value={form.partner} onChange={set('partner')} />
                </div>
                <div className="form-group">
                  <label>Reminder sentence</label>
                  <textarea rows={2} value={form.reminder} onChange={set('reminder')} />
                </div>
              </>
            )}
            {!isUmuganda && (
              <div className="form-group">
                <label>Invited / audience</label>
                <input value={form.audience} onChange={set('audience')} placeholder="e.g. All isibo leaders and hostel representatives" />
              </div>
            )}
            <div className="form-group">
              <label>Note (optional)</label>
              <input value={form.note} onChange={set('note')} />
            </div>
            <div className="form-group">
              <label>Custom body <span className="muted small">(optional; replaces the generated paragraph. One paragraph per line.)</span></label>
              <textarea rows={4} value={form.body} onChange={set('body')} />
            </div>
            <div className="form-group checkbox-row">
              <input type="checkbox" id="published" checked={form.published} onChange={set('published')} />
              <label htmlFor="published" style={{ margin: 0 }}>Publish to citizens of the village</label>
            </div>
            <div className="btn-row">
              <button className="btn" disabled={!!busy}>{busy === 'save' ? 'Saving…' : editingId ? 'Save changes' : 'Save'}</button>
              <button type="button" className="btn btn-outline-dark" disabled={!!busy} onClick={(e) => save(e, true)}>
                {busy === 'save-download' ? 'Preparing…' : 'Save & Download (.docx)'}
              </button>
              {editingId && <button type="button" className="btn btn-outline-dark" onClick={reset}>Cancel</button>}
            </div>
          </form>

          <div className="card preview-letter">
            <h2 className="card-title">Preview</h2>
            {preview ? (
              <div className="letter">
                <div className="letterhead">
                  <div>
                    {rw ? (
                      <>
                        <div>{/kigali/i.test(preview.letterhead.province) ? 'UMUJYI WA KIGALI' : `INTARA Y'${preview.letterhead.province.toUpperCase()}`}</div>
                        <div>AKARERE KA {preview.letterhead.district.toUpperCase()}</div>
                        <div>UMURENGE WA {preview.letterhead.sector.toUpperCase()}</div>
                        <div>AKAGARI KA {preview.letterhead.cell.toUpperCase()}</div>
                        <div>UMUDUGUDU W{/^[aeiou]/i.test(preview.letterhead.village) ? "'" : 'A '}{preview.letterhead.village.toUpperCase()}</div>
                      </>
                    ) : (
                      <>
                        <div>{/kigali/i.test(preview.letterhead.province) ? 'CITY OF KIGALI' : `${preview.letterhead.province.toUpperCase()} PROVINCE`}</div>
                        <div>{preview.letterhead.district.toUpperCase()} DISTRICT</div>
                        <div>{preview.letterhead.sector.toUpperCase()} SECTOR</div>
                        <div>{preview.letterhead.cell.toUpperCase()} CELL</div>
                        <div>{preview.letterhead.village.toUpperCase()} VILLAGE</div>
                      </>
                    )}
                  </div>
                  <div>{form.letter_date}</div>
                </div>
                {preview.paragraphs.map((p, i) => (
                  <p key={i} className={`letter-${p.style}`}>{p.text}</p>
                ))}
              </div>
            ) : <p className="muted small">Fill in the form to see the letter text.</p>}
          </div>
        </div>
      )}

      <div className="card">
        <h2 className="card-title">{canCreate ? 'Saved announcements' : 'Announcements from your village'}</h2>
        {items.length === 0 ? (
          <p className="muted">No announcements yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th><th>Type</th><th>Event</th><th>Venue</th><th>Village</th>
                  {canCreate && <th>Status</th>}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id}>
                    <td>{a.letter_date}</td>
                    <td>{a.kind_display}<div className="muted small">{a.language_display}{a.title ? ` · ${a.title}` : ''}</div></td>
                    <td>{a.event_date || '—'}{a.start_time ? ` · ${a.start_time}` : ''}</td>
                    <td>{a.venue || '—'}</td>
                    <td>{a.village_name || '—'}</td>
                    {canCreate && <td><span className={`badge ${a.published ? 'badge-approved' : 'badge-pending'}`}>{a.published ? 'Published' : 'Draft'}</span></td>}
                    <td className="actions-cell">
                      <button className="btn btn-small" onClick={() => download(a)}>Download (.docx)</button>
                      {canCreate && (a.created_by === user?.id || user?.is_admin_role || user?.is_superuser) && (
                        <>
                          <button className="btn btn-small btn-outline-dark" onClick={() => startEdit(a)}>Edit</button>
                          <button className="btn btn-small btn-outline-dark" onClick={() => togglePublish(a)}>{a.published ? 'Unpublish' : 'Publish'}</button>
                          <button className="btn btn-small btn-danger" onClick={() => remove(a)}>Delete</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
