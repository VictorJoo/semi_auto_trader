import { useMemo, useRef, useState, type MouseEvent } from 'react'
import type { ChartPoint, Period } from '../types'
import { money } from '../format'
import EmptyItem from './EmptyItem'

interface Props {
  points: ChartPoint[]
  period: Period
}

const periodNames: Record<Period, string> = {
  day: '일 차트',
  week: '주 차트',
  month: '월 차트',
}

const unitNames: Record<Period, string> = {
  day: '5분 단위 시간',
  week: '일 단위 날짜',
  month: '주 단위 시작일',
}

const rangeLabels: Record<Period, string> = {
  day: '09:00-15:30',
  week: '오늘 기준 1주',
  month: '오늘 기준 4주',
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

export default function PriceChart({ points, period }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)

  const layout = useMemo(() => {
    if (!points.length) return null
    const width = 920
    const height = period === 'day' ? 430 : 390
    const padding = {
      top: 34,
      right: 26,
      bottom: period === 'day' ? 112 : 72,
      left: 78,
    }
    const values = points.map((point) => point.close)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const average = values.reduce((sum, value) => sum + value, 0) / values.length
    const range = max - min || 1
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom
    const step = points.length > 1 ? chartWidth / (points.length - 1) : 0
    const coords: PlacedPoint[] = points.map((point, index) => ({
      ...point,
      x: padding.left + step * index,
      y:
        padding.top +
        chartHeight -
        ((point.close - min) / range) * chartHeight,
    }))
    const yTicks = Array.from(
      { length: 5 },
      (_, index) => min + (range / 4) * index,
    ).reverse()
    const polyline = coords.map((point) => `${point.x},${point.y}`).join(' ')
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
      polyline,
      hitWidth,
    }
  }, [points, period])

  if (!layout) return <EmptyItem text="차트 데이터가 없습니다." />

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
    polyline,
    hitWidth,
  } = layout

  function showTooltip(point: PlacedPoint) {
    return (event: MouseEvent) => {
      const container = containerRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      setTooltip({
        text: `${point.tooltip_label || point.label} | 가격 ${money.format(point.close)}`,
        x: event.clientX - rect.left + 14,
        y: event.clientY - rect.top + 14,
      })
    }
  }

  const last = coords[coords.length - 1]

  return (
    <div className="chart" ref={containerRef} onMouseLeave={() => setTooltip(null)}>
      <div className="chart-summary">
        <span>기간: {periodNames[period]}</span>
        <span>X축 단위: {unitNames[period]}</span>
        <span>범위: {rangeLabels[period]}</span>
        <span>최고가: {money.format(max)}</span>
        <span>최저가: {money.format(min)}</span>
        <span>평균가: {money.format(average)}</span>
        <span>최근가: {money.format(last.close)}</span>
      </div>
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
          const rotate =
            period === 'day'
              ? `rotate(-55 ${point.x} ${height - padding.bottom + 24})`
              : undefined
          const anchor = period === 'day' ? 'end' : 'middle'
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
                y={height - padding.bottom + 24}
                textAnchor={anchor}
                transform={rotate}
                className="axis-label"
              >
                {point.label}
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
        <polyline points={polyline} className="price-line" />
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
            className={point.realtime ? 'live-point' : 'point'}
            onMouseMove={showTooltip(point)}
          />
        ))}
      </svg>
      {tooltip && (
        <div
          className="chart-tooltip show"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  )
}
