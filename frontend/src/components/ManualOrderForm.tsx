import { useState, type FormEvent } from 'react'
import { placeOrder } from '../api'
import { useToast } from '../hooks/useToast'
import type { Action } from '../types'

interface Props {
  onPlaced: () => void
}

export default function ManualOrderForm({ onPlaced }: Props) {
  const { show } = useToast()
  const [action, setAction] = useState<Action>('BUY')
  const [symbol, setSymbol] = useState('')
  const [qty, setQty] = useState(1)
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState('')

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    try {
      await placeOrder(symbol.trim().toUpperCase(), action, qty)
      const message = '수동 모의 주문이 처리되었습니다.'
      setNotice(message)
      show(message, 'success')
      onPlaced()
    } catch (error) {
      const message = (error as Error).message
      setNotice(message)
      show(message, 'error')
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <form className="order" onSubmit={onSubmit}>
        <select
          value={action}
          onChange={(event) => setAction(event.target.value as Action)}
        >
          <option>BUY</option>
          <option>SELL</option>
        </select>
        <input
          name="symbol"
          placeholder="AAPL"
          required
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
        />
        <input
          name="qty"
          type="number"
          min={1}
          required
          value={qty}
          onChange={(event) => setQty(Number(event.target.value))}
        />
        <button type="submit" disabled={pending}>
          {pending ? '처리중' : '주문'}
        </button>
      </form>
      <p className="notice">{notice}</p>
    </>
  )
}
