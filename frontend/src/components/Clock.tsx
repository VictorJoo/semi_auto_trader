import { useEffect, useState } from 'react'
import { getMarketStatus } from '../marketStatus'

const SEOUL = 'Asia/Seoul'

const hourMinuteFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: SEOUL,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const secondFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: SEOUL,
  second: '2-digit',
})

const dateFormatter = new Intl.DateTimeFormat('ko-KR', {
  timeZone: SEOUL,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  weekday: 'short',
})

function formatDateLine(date: Date): string {
  const parts = dateFormatter.formatToParts(date).reduce<Record<string, string>>(
    (acc, part) => {
      if (part.type !== 'literal') acc[part.type] = part.value
      return acc
    },
    {},
  )
  const year = parts.year ?? ''
  const month = parts.month ?? ''
  const day = parts.day ?? ''
  const weekday = parts.weekday ?? ''
  return `${year}.${month}.${day} · ${weekday}`
}

export default function Clock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const tick = () => setNow(new Date())
    const initialDelay = 1000 - (Date.now() % 1000)
    let intervalId: number | null = null
    const timeoutId = window.setTimeout(() => {
      tick()
      intervalId = window.setInterval(tick, 1000)
    }, initialDelay)
    return () => {
      window.clearTimeout(timeoutId)
      if (intervalId !== null) window.clearInterval(intervalId)
    }
  }, [])

  const hhmm = hourMinuteFormatter.format(now)
  const ss = secondFormatter.format(now)
  const dateLine = formatDateLine(now)
  const status = getMarketStatus(now)

  return (
    <div className="clock" aria-label="현재 시각 KST">
      <div className="clock-time">
        <span className="clock-hhmm">{hhmm}</span>
        <span className="clock-ss">:{ss}</span>
      </div>
      <div className="clock-meta">
        <span className={`clock-dot ${status.isOpen ? 'open' : 'closed'}`} aria-hidden />
        <span className="clock-date">{dateLine} · KST</span>
      </div>
    </div>
  )
}
