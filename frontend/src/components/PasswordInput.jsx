import { useState } from 'react'

const EyeIcon = ({ off }) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
    <circle cx="12" cy="12" r="3" />
    {off && <line x1="3" y1="3" x2="21" y2="21" />}
  </svg>
)

// Password box with an eye button that shows or hides what was typed; the eye appears once there is something to show
export default function PasswordInput({ value, onChange, ...rest }) {
  const [visible, setVisible] = useState(false)
  const shown = visible && !!value

  return (
    <div className="password-wrap">
      <input type={shown ? 'text' : 'password'} value={value} onChange={onChange} {...rest} />
      {value && (
        <button
          type="button"
          className="password-eye"
          onClick={() => setVisible((v) => !v)}
          aria-label={shown ? 'Hide password' : 'Show password'}
          title={shown ? 'Hide password' : 'Show password'}
        >
          <EyeIcon off={shown} />
        </button>
      )}
    </div>
  )
}
