import { CATEGORY_LABELS, YOUTH_MIN, YOUTH_MAX } from '../citizen.js'

// Youth (16–30) or ordinary citizen, as a small badge
export default function CategoryBadge({ category }) {
  if (!category) return null
  const title = category === 'youth' ? `Aged ${YOUTH_MIN} to ${YOUTH_MAX}` : `Outside the ${YOUTH_MIN}–${YOUTH_MAX} youth bracket`
  return <span className={`badge badge-${category}`} title={title}>{CATEGORY_LABELS[category] || category}</span>
}
