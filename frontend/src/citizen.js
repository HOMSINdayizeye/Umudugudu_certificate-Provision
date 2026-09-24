// Identity document and age rules shared by the citizen forms and lists

export const ID_TYPES = [
  { value: 'national_id', label: 'National ID' },
  { value: 'passport', label: 'Passport' },
]
export const NATIONAL_ID_HINT = '16 digits; the birth year (digits 2–5) fills in the age'
export const PASSPORT_HINT = '6 to 20 letters and digits; type the age yourself'

// Citizens aged 16 to 30 inclusive are youth; everyone else is an ordinary citizen
export const YOUTH_MIN = 16
export const YOUTH_MAX = 30

// Age implied by a Rwandan national ID (digits 2–5 are the birth year), or null while it cannot be read
export function ageFromNationalId(id, now = new Date()) {
  const digits = (id || '').trim()
  if (!/^\d{5,16}$/.test(digits)) return null
  const year = Number(digits.slice(1, 5))
  const current = now.getFullYear()
  if (year < 1900 || year > current) return null
  return current - year
}

export function isYouth(age) {
  const n = Number(age)
  return Number.isFinite(n) && n >= YOUTH_MIN && n <= YOUTH_MAX
}

export function categoryOf(age) {
  return isYouth(age) ? 'youth' : 'citizen'
}

export const CATEGORY_LABELS = { youth: 'Youth', citizen: 'Citizen' }

// Youth leader roles and the level they cover
export const YOUTH_ROLES = ['cell_youth_leader', 'sector_youth_leader']
export const YOUTH_LEVEL = { cell_youth_leader: 'cell', sector_youth_leader: 'sector' }
