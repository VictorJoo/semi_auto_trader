const MARKET_OPEN_MIN = 9 * 60
const MARKET_CLOSE_MIN = 15 * 60 + 30
const SEOUL_TIME_ZONE = 'Asia/Seoul'

export interface MarketStatus {
  isOpen: boolean
  label: string
  detail: string
}

interface SeoulParts {
  weekday: string
  hour: string
  minute: string
  minOfDay: number
  isWeekday: boolean
}

const seoulPartsFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: SEOUL_TIME_ZONE,
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const seoulTimeFormatter = new Intl.DateTimeFormat('ko-KR', {
  timeZone: SEOUL_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function readSeoulParts(date: Date): SeoulParts {
  const parts = seoulPartsFormatter
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, part) => {
      if (part.type !== 'literal') acc[part.type] = part.value
      return acc
    }, {})
  const weekday = parts.weekday ?? ''
  const hourRaw = parts.hour ?? '00'
  const hour = hourRaw === '24' ? '00' : hourRaw
  const minute = parts.minute ?? '00'
  const minOfDay = parseInt(hour, 10) * 60 + parseInt(minute, 10)
  const isWeekday = weekday !== 'Sat' && weekday !== 'Sun'
  return { weekday, hour, minute, minOfDay, isWeekday }
}

function formatSeoulTime(date: Date): string {
  return seoulTimeFormatter.format(date)
}

function nextOpenLabel(parts: SeoulParts): string {
  if (parts.isWeekday && parts.minOfDay < MARKET_OPEN_MIN) {
    return '다음 개장 오늘 09:00'
  }
  if (parts.weekday === 'Fri' || parts.weekday === 'Sat') {
    return '다음 개장 월요일 09:00'
  }
  return '다음 개장 내일 09:00'
}

export function getMarketStatus(now: Date = new Date()): MarketStatus {
  const parts = readSeoulParts(now)
  const isOpen =
    parts.isWeekday &&
    parts.minOfDay >= MARKET_OPEN_MIN &&
    parts.minOfDay < MARKET_CLOSE_MIN
  if (isOpen) {
    return {
      isOpen: true,
      label: '장중',
      detail: `현재 ${parts.hour}:${parts.minute} KST`,
    }
  }
  return {
    isOpen: false,
    label: '장 마감',
    detail: nextOpenLabel(parts),
  }
}

export function formatCollectedAt(date: Date): string {
  return formatSeoulTime(date)
}
