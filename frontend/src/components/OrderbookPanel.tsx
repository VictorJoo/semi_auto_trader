import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchOrderbook, placeOrder } from '../api'
import { money } from '../format'
import { useToast } from '../hooks/useToast'
import type { Action, OrderbookSnapshot } from '../types'
import EmptyItem from './EmptyItem'

interface Props {
  symbol: string
  name?: string
  currentPrice?: number
  onOrderPlaced?: () => void
}

interface PendingOrder {
  action: Action
  price: number
}

export default function OrderbookPanel({
  symbol,
  name,
  currentPrice,
  onOrderPlaced,
}: Props) {
  const { show } = useToast()
  const [orderbook, setOrderbook] = useState<OrderbookSnapshot | null>(null)
  const [selectedPrice, setSelectedPrice] = useState<number>(0)
  const [action, setAction] = useState<Action>('BUY')
  const [qty, setQty] = useState<number>(1)
  const [pendingOrder, setPendingOrder] = useState<PendingOrder | null>(null)
  const [lastAcceptedPrice, setLastAcceptedPrice] = useState<number | null>(null)
  const loadingRef = useRef(false)

  const load = useCallback(async () => {
    if (!symbol || loadingRef.current) return
    loadingRef.current = true
    try {
      setOrderbook(await fetchOrderbook(symbol))
    } catch (error) {
      show((error as Error).message, 'error')
    } finally {
      loadingRef.current = false
    }
  }, [show, symbol])

  useEffect(() => {
    setOrderbook(null)
    setSelectedPrice(0)
    setLastAcceptedPrice(null)
    loadingRef.current = false
    void load()
    const intervalId = window.setInterval(load, 2000)
    return () => window.clearInterval(intervalId)
  }, [load])

  useEffect(() => {
    if (!selectedPrice && currentPrice) setSelectedPrice(currentPrice)
  }, [currentPrice, selectedPrice])

  const levels = useMemo(() => {
    const asks = [...(orderbook?.asks ?? [])].sort((a, b) => b.price - a.price)
    const bids = orderbook?.bids ?? []
    return { asks, bids }
  }, [orderbook])

  async function submitOrder() {
    if (!symbol || !selectedPrice || qty <= 0 || pendingOrder) return
    setPendingOrder({ action, price: selectedPrice })
    setLastAcceptedPrice(null)
    try {
      await placeOrder(symbol, action, qty, selectedPrice)
      setLastAcceptedPrice(selectedPrice)
      show(
        `${action === 'BUY' ? '매수' : '매도'} 주문이 접수되었습니다. ${money.format(
          selectedPrice,
        )}원 x ${qty}주`,
        'success',
      )
      onOrderPlaced?.()
      void load()
    } catch (error) {
      show((error as Error).message, 'error')
    } finally {
      setPendingOrder(null)
    }
  }

  function selectPrice(price: number) {
    setSelectedPrice(price)
  }

  if (!symbol) {
    return (
      <section className="panel orderbook-panel">
        <h2>호가 주문</h2>
        <EmptyItem text="종목을 선택하면 호가가 표시됩니다." />
      </section>
    )
  }

  return (
    <section className="panel orderbook-panel">
      <div className="orderbook-head">
        <div>
          <h2>호가 주문</h2>
          <span>{name ? `${name} (${symbol})` : symbol}</span>
        </div>
        <button type="button" className="secondary" onClick={load}>
          새로고침
        </button>
      </div>

      <div className="unified-order-ticket">
        <div className="order-ticket-head">
          <span>통합 주문</span>
          <div className="side-toggle" aria-label="주문 구분">
            <button
              type="button"
              className={action === 'BUY' ? 'active BUY' : ''}
              onClick={() => setAction('BUY')}
            >
              매수
            </button>
            <button
              type="button"
              className={action === 'SELL' ? 'active SELL' : ''}
              onClick={() => setAction('SELL')}
            >
              매도
            </button>
          </div>
        </div>
        <div className="order-ticket-fields">
          <label>
            <span>가격</span>
            <input
              type="number"
              min={1}
              value={selectedPrice || ''}
              onChange={(event) => setSelectedPrice(Number(event.target.value))}
            />
          </label>
          <label>
            <span>수량</span>
            <input
              type="number"
              min={1}
              value={qty}
              onChange={(event) => setQty(Number(event.target.value))}
            />
          </label>
        </div>
        <button
          type="button"
          className={`order-submit ${action}`}
          disabled={Boolean(pendingOrder)}
          onClick={submitOrder}
        >
          {pendingOrder ? '주문 대기중' : `${action === 'BUY' ? '매수' : '매도'} 주문`}
        </button>
      </div>

      {!orderbook ? (
        <EmptyItem text="호가를 불러오는 중입니다." />
      ) : (
        <div className="orderbook-ladder">
          <div className="orderbook-updated">
            실시간 갱신 {formatOrderbookTime(orderbook.collected_at)}
          </div>
          {levels.asks.map((level) => (
            <OrderbookRow
              key={`ask-${level.level}`}
              side="SELL"
              level={level.level}
              price={level.price}
              qty={level.qty}
              selected={selectedPrice === level.price}
              pending={pendingOrder?.price === level.price}
              accepted={lastAcceptedPrice === level.price}
              onClick={() => selectPrice(level.price)}
            />
          ))}
          {currentPrice ? (
            <div className="orderbook-current">현재가 {money.format(currentPrice)}원</div>
          ) : null}
          {levels.bids.map((level) => (
            <OrderbookRow
              key={`bid-${level.level}`}
              side="BUY"
              level={level.level}
              price={level.price}
              qty={level.qty}
              selected={selectedPrice === level.price}
              pending={pendingOrder?.price === level.price}
              accepted={lastAcceptedPrice === level.price}
              onClick={() => selectPrice(level.price)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function formatOrderbookTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

interface RowProps {
  side: Action
  level: number
  price: number
  qty: number
  selected: boolean
  pending: boolean
  accepted: boolean
  onClick: () => void
}

function OrderbookRow({
  side,
  level,
  price,
  qty,
  selected,
  pending,
  accepted,
  onClick,
}: RowProps) {
  return (
    <button
      type="button"
      className={[
        'orderbook-row',
        side === 'BUY' ? 'bid' : 'ask',
        selected ? 'selected' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onClick}
    >
      <span className="orderbook-level">{level}</span>
      <strong>{money.format(price)}</strong>
      <span>{money.format(qty)}주</span>
      {pending ? <em>대기중</em> : null}
      {accepted ? <em>접수</em> : null}
    </button>
  )
}
