export const money = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 0,
})

export const usd = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
})

export const pct = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 2,
})

export const dateTime = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

export function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${pct.format(value)}`
}
