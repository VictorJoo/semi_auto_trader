import { useState } from 'react'
import type { Signal } from '../types'
import { dateTime, money, pct } from '../format'
import { approveSignal } from '../api'
import { useToast } from '../hooks/useToast'
import EmptyItem from './EmptyItem'

interface Props {
  signals: Signal[]
  onApproved: () => void
}

export default function SignalList({ signals, onApproved }: Props) {
  const { show } = useToast()
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [qtyMap, setQtyMap] = useState<Record<string, number>>({})

  if (!signals.length)
    return <EmptyItem text="현재 매수/매도 신호가 없습니다." />

  async function approve(signal: Signal) {
    const qty = qtyMap[signal.id] ?? signal.suggested_qty
    setPendingId(signal.id)
    try {
      await approveSignal(signal.id, qty)
      show(`${qty}주 주문이 승인되었습니다.`, 'success')
      onApproved()
    } catch (error) {
      show((error as Error).message, 'error')
    } finally {
      setPendingId(null)
    }
  }

  return (
    <>
      {signals.map((signal) => {
        const qty = qtyMap[signal.id] ?? signal.suggested_qty
        const isPending = pendingId === signal.id
        return (
          <div className="item" key={signal.id}>
            <div className="row">
              <strong>
                {signal.symbol} @ {money.format(signal.price)}
              </strong>
              <span className={`tag ${signal.action}`}>{signal.action}</span>
            </div>
            <div className="row">
              <span>
                수량 {signal.suggested_qty} · 확신도{' '}
                {pct.format(signal.confidence * 100)}%
              </span>
              <div className="approve">
                <input
                  aria-label="승인 수량"
                  type="number"
                  min={1}
                  max={signal.suggested_qty}
                  value={qty}
                  disabled={isPending}
                  onChange={(event) =>
                    setQtyMap((current) => ({
                      ...current,
                      [signal.id]: Number(event.target.value),
                    }))
                  }
                />
                <button
                  type="button"
                  className="secondary"
                  disabled={isPending}
                  onClick={() => approve(signal)}
                >
                  {isPending ? '처리중' : '승인'}
                </button>
              </div>
            </div>
            <span>
              발생 {dateTime.format(new Date(signal.created_at))} · 오늘 날짜
              신호만 표시
            </span>
            <ul className="reasons">
              {signal.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </div>
        )
      })}
    </>
  )
}
