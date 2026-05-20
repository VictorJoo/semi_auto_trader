import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import type { ChartPoint, Period } from '../types'
import { money } from '../format'
import EmptyItem from './EmptyItem'

interface Props {
  points: ChartPoint[]
  period: Period
  loading?: boolean
}

const TOOLTIP_OFFSET = 14
const TOOLTIP_VIEWPORT_MARGIN = 8

function shouldShowXLabel(
  label: string,
  period: Period,
  index: number,
  total: number,
): boolean {
  if (!label) return false
  if (period === 'today' || period === '1d') {
    return /^[0-9]{2}:00$/.test(label)
  }
  if (period === '1w') {
    return / 09:00$/.test(label) || index === total - 1
  }
  if (period === '3m') {
    if (index === 0 || index === total - 1) return true
    const match = label.match(/^([0-9]{2})-([0-9]{2})$/)
    if (!match) return false
    return match[2] === '01'
  }
  return true
}

function displayXLabel(label: string, period: Period): string {
  if (period === '1w') {
    const match = label.match(/^([0-9]{2}-[0-9]{2})\s/)
    return match ? match[1] : label
  }
  return label
}

interface SessionSegment {
  session: 'pre' | 'regular' | 'after'
  pointsAttr: string
}

const SESSION_LABELS: Record<'pre' | 'regular' | 'after', string> = {
  pre: '프리마켓',
  regular: '정규장',
  after: '시간외',
}

function sessionLabel(session: 'pre' | 'regular' | 'after' | undefined): string {
  if (!session || session === 'regular') return ''
  return SESSION_LABELS[session] ?? ''
}

interface PlacedSeed {
  x: number
  y: number
  session?: 'pre' | 'regular' | 'after'
}

function buildSessionSegments(coords: PlacedSeed[]): SessionSegment[] {
  if (coords.length === 0) return []
  const segments: SessionSegment[] = []
  let currentSession: 'pre' | 'regular' | 'after' = coords[0].session ?? 'regular'
  let currentPoints: PlacedSeed[] = [coords[0]]
  for (let i = 1; i < coords.length; i++) {
    const point = coords[i]
    const session = point.session ?? 'regular'
    if (session !== currentSession) {
      currentPoints.push(point)
      segments.push({
        session: currentSession,
        pointsAttr: currentPoints.map((p) => `${p.x},${p.y}`).join(' '),
      })
      currentSession = session
      currentPoints = [point]
    } else {
      currentPoints.push(point)
    }
  }
  segments.push({
    session: currentSession,
    pointsAttr: currentPoints.map((p) => `${p.x},${p.y}`).join(' '),
  })
  return segments
}

const periodNames: Record<Period, string> = {
  today: '오늘 차트',
  '1d': '1일 차트',
  '1w': '1주 차트',
  '3m': '3개월 차트',
}

const unitNames: Record<Period, string> = {
  today: '5분 단위',
  '1d': '5분 단위',
  '1w': '10분 단위',
  '3m': '1일 단위',
}

const rangeLabels: Record<Period, string> = {
  today: '09:00-15:30',
  '1d': '09:00-현재 (시간외 포함)',
  '1w': '최근 거래일 10분 단위',
  '3m': '최근 90일',
}

interface Tooltip {
  text: string
  x: number
  y: number
}

interface PlacedPoint extends ChartPoint {
  x: number
  y: number
}

export default function PriceChart({ points, period, loading = false }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{
    left: number
    top: number
  } | null>(null)

  const layout = useMemo(() => {
    if (!points.length) return null
    const width = 920
    const height = 390
    const padding = {
      top: 34,
      right: 26,
      bottom: 72,
      left: 78,
    }
    const values = points.map((point) => point.close)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const average =
      values.reduce((sum, value) => sum + value, 0) / values.length
    const range = max - min || 1
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom
    const step = points.length > 1 ? chartWidth / (points.length - 1) : 0
    const coords: PlacedPoint[] = points.map((point, index) => ({
      ...point,
      x: padding.left + step * index,
      y:
        padding.top + chartHeight - ((point.close - min) / range) * chartHeight,
    }))
    const yTicks = Array.from(
      { length: 5 },
      (_, index) => min + (range / 4) * index,
    ).reverse()
    const segments = buildSessionSegments(coords)
    const hitWidth = Math.max(8, step || chartWidth)
    return {
      width,
      height,
      padding,
      min,
      max,
      average,
      range,
      chartHeight,
      coords,
      yTicks,
      segments,
      hitWidth,
    }
  }, [points, period])

  useLayoutEffect(() => {
    if (!tooltip) {
      if (tooltipPos !== null) setTooltipPos(null)
      return
    }
    const node = tooltipRef.current
    const width = node?.offsetWidth ?? 0
    const height = node?.offsetHeight ?? 0
    const vw = window.innerWidth
    const vh = window.innerHeight
    let left = tooltip.x + TOOLTIP_OFFSET
    let top = tooltip.y + TOOLTIP_OFFSET
    if (left + width > vw - TOOLTIP_VIEWPORT_MARGIN) {
      left = Math.max(
        TOOLTIP_VIEWPORT_MARGIN,
        tooltip.x - width - TOOLTIP_OFFSET,
      )
    }
    if (top + height > vh - TOOLTIP_VIEWPORT_MARGIN) {
      top = Math.max(
        TOOLTIP_VIEWPORT_MARGIN,
        tooltip.y - height - TOOLTIP_OFFSET,
      )
    }
    if (
      !tooltipPos ||
      Math.abs(tooltipPos.left - left) > 0.5 ||
      Math.abs(tooltipPos.top - top) > 0.5
    ) {
      setTooltipPos({ left, top })
    }
  }, [tooltip, tooltipPos])

  if (!layout) {
    if (loading) {
      return (
        <div className="chart chart-loading" role="status" aria-live="polite">
          <div className="chart-loading-inner">
            <span className="chart-spinner" aria-hidden="true" />
            <span className="chart-loading-text">차트를 불러오는 중…</span>
          </div>
        </div>
      )
    }
    return <EmptyItem text="차트 데이터가 없습니다." />
  }

  const {
    width,
    height,
    padding,
    min,
    max,
    average,
    range,
    chartHeight,
    coords,
    yTicks,
    segments,
    hitWidth,
  } = layout

  function showTooltip(point: PlacedPoint) {
    return (event: MouseEvent) => {
      const sessionTag = sessionLabel(point.session)
      const head = sessionTag
        ? `${point.tooltip_label || point.label} · ${sessionTag}`
        : `${point.tooltip_label || point.label}`
      setTooltip({
        text: `${head} | 가격 ${money.format(point.close)}원`,
        x: event.clientX,
        y: event.clientY,
      })
    }
  }

  function hideTooltip() {
    setTooltip(null)
    setTooltipPos(null)
  }

  const last = coords[coords.length - 1]
  const sessionLegendItems = Array.from(
    new Set(
      segments.map((segment) => segment.session),
    ),
  ).sort((a, b) => {
    const order = { pre: 0, regular: 1, after: 2 }
    return order[a] - order[b]
  })

  return (
    <div className="chart" ref={containerRef} onMouseLeave={hideTooltip}>
      <div className="chart-summary">
        <span>기간: {periodNames[period]}</span>
        <span>X축 단위: {unitNames[period]}</span>
        <span>범위: {rangeLabels[period]}</span>
        <span>최고가: {money.format(max)}</span>
        <span>최저가: {money.format(min)}</span>
        <span>평균가: {money.format(average)}</span>
        <span>최근가: {money.format(last.close)}</span>
      </div>
      {sessionLegendItems.length > 1 && (
        <div className="chart-legend">
          {sessionLegendItems.map((session) => (
            <span key={session} className={`chart-legend-item legend-${session}`}>
              <span className={`legend-swatch legend-swatch-${session}`} aria-hidden />
              {SESSION_LABELS[session]}
            </span>
          ))}
        </div>
      )}
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="가격 차트">
        <text
          x={width / 2}
          y={height - 14}
          textAnchor="middle"
          className="axis-title"
        >
          X축: {unitNames[period]}
        </text>
        <text
          x={18}
          y={height / 2}
          transform={`rotate(-90 18 ${height / 2})`}
          textAnchor="middle"
          className="axis-title"
        >
          Y축: 가격
        </text>
        {yTicks.map((value) => {
          const y =
            padding.top + chartHeight - ((value - min) / range) * chartHeight
          return (
            <g key={`ytick-${value}`}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                className="grid-line"
              />
              <text
                x={padding.left - 10}
                y={y + 4}
                textAnchor="end"
                className="axis-label"
              >
                {money.format(value)}
              </text>
            </g>
          )
        })}
        {coords.map((point, index) => {
          if (!shouldShowXLabel(point.label, period, index, coords.length)) {
            return null
          }
          return (
            <g key={`xtick-${index}`}>
              <line
                x1={point.x}
                y1={height - padding.bottom}
                x2={point.x}
                y2={height - padding.bottom + 6}
                className="axis"
              />
              <text
                x={point.x}
                y={height - padding.bottom + 22}
                textAnchor="middle"
                className="axis-label"
              >
                {displayXLabel(point.label, period)}
              </text>
            </g>
          )
        })}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={height - padding.bottom}
          className="axis"
        />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          className="axis"
        />
        {segments.map((seg, index) => (
          <polyline
            key={`seg-${index}`}
            points={seg.pointsAttr}
            className={`price-line price-line-${seg.session}`}
          />
        ))}
        {coords.map((point, index) => (
          <rect
            key={`hit-${index}`}
            x={point.x - hitWidth / 2}
            y={padding.top}
            width={hitWidth}
            height={chartHeight}
            className="hover-zone"
            onMouseMove={showTooltip(point)}
          />
        ))}
        {coords.map((point, index) => (
          <circle
            key={`pt-${index}`}
            cx={point.x}
            cy={point.y}
            r={point.realtime ? 5 : 3}
            className={`${point.realtime ? 'live-point' : 'point'} session-${point.session ?? 'regular'}`}
            onMouseMove={showTooltip(point)}
          />
        ))}
      </svg>
      {tooltip && (
        <div
          ref={tooltipRef}
          className="chart-tooltip show"
          style={{
            left: tooltipPos?.left ?? tooltip.x + TOOLTIP_OFFSET,
            top: tooltipPos?.top ?? tooltip.y + TOOLTIP_OFFSET,
            visibility: tooltipPos ? 'visible' : 'hidden',
          }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  )
}
