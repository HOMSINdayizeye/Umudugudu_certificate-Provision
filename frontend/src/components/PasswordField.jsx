import { useMemo } from 'react'

const RULES = [
  { key: 'length', label: 'At least 8 characters', test: (v) => v.length >= 8 },
  { key: 'upper', label: 'An uppercase letter (A–Z)', test: (v) => /[A-Z]/.test(v) },
  { key: 'lower', label: 'A lowercase letter (a–z)', test: (v) => /[a-z]/.test(v) },
  { key: 'digit', label: 'A number (0–9)', test: (v) => /\d/.test(v) },
  { key: 'special', label: 'A special character (!@#$…)', test: (v) => /[^A-Za-z0-9]/.test(v) },
]

export function passwordIsStrong(value) {
  return RULES.every((r) => r.test(value))
}

// Password input with a live strength meter and rule checklist.
export default function PasswordField({ value, onChange, label = 'Password' }) {
  const passed = useMemo(() => RULES.filter((r) => r.test(value)).length, [value])
  const strength = passed <= 2 ? 'weak' : passed <= 4 ? 'medium' : 'strong'
  const labels = { weak: 'Weak', medium: 'Medium', strong: 'Strong' }

  return (
    <div className="form-group">
      <label>{label}</label>
      <input type="password" value={value} onChange={onChange} required autoComplete="new-password" />
      {value && (
        <>
          <div className="strength-bar">
            <div className={`strength-fill strength-${strength}`} style={{ width: `${(passed / RULES.length) * 100}%` }} />
          </div>
          <div className={`strength-label strength-text-${strength}`}>{labels[strength]} password</div>
          <ul className="password-rules">
            {RULES.map((r) => (
              <li key={r.key} className={r.test(value) ? 'rule-ok' : 'rule-missing'}>
                {r.test(value) ? '✔' : '○'} {r.label}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
