// Rwandan mobile number: 10 digits starting 07 (0791234567) or 12 digits starting 2507 (250791234567); no + or spaces
export const PHONE_PATTERN = '(2507[0-9]{8}|07[0-9]{8})'
export const PHONE_HINT = 'Format: 0791234567 (10 digits) or 250791234567 (12 digits), no + or spaces'
export const PHONE_MAX = 12

// Props shared by every phone input so the browser checks the format before the server does
export const phoneInputProps = { type: 'tel', pattern: PHONE_PATTERN, title: PHONE_HINT, inputMode: 'numeric', maxLength: PHONE_MAX }
