import type { VolumeRow } from '../types'
import { money, signed } from '../format'
import EmptyItem from './EmptyItem'

interface Props {
  rows: VolumeRow[]
  selectedSymbol: string
  onSelect: (symbol: string) => void
}

export default function SymbolList({ rows, selectedSymbol, onSelect }: Props) {
  if (!rows.length) return <EmptyItem text="거래량 데이터가 없습니다." />
  return (
    <>
      {rows.map((row, index) => (
        <button
          key={row.symbol}
          type="button"
          className={`item stock-row ${row.symbol === selectedSymbol ? 'selected' : ''}`}
          onClick={() => onSelect(row.symbol)}
        >
          <div>
            <strong>
              {index + 1}. {row.symbol}
            </strong>
            <span>거래량 {money.format(row.volume)}</span>
          </div>
          <div>
            <strong>{money.format(row.price)}</strong>
            <span className={row.change_pct >= 0 ? 'BUY' : 'SELL'}>
              {signed(row.change_pct)}%
            </span>
          </div>
        </button>
      ))}
    </>
  )
}
