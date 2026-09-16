import { useEffect, useState } from 'react'

// Counts from 1 up to `value` over `duration` ms, starting after `delay` ms, so several can run one after another
export default function CountUp({ value, duration = 600, delay = 0 }) {
  const [shown, setShown] = useState(value > 0 ? 1 : 0)

  useEffect(() => {
    const target = Number(value) || 0
    if (target <= 1) { setShown(target); return undefined }
    let frame
    let start
    const timer = setTimeout(() => {
      const tick = (now) => {
        if (start === undefined) start = now
        const t = Math.min((now - start) / duration, 1)
        const eased = 1 - Math.pow(1 - t, 3) // fast start, gentle landing
        setShown(Math.max(1, Math.round(1 + eased * (target - 1))))
        if (t < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    }, delay)
    return () => { clearTimeout(timer); if (frame) cancelAnimationFrame(frame) }
  }, [value, duration, delay])

  return <>{shown}</>
}
