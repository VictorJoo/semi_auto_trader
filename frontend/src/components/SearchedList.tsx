import type { SymbolEntry } from '../types'
import EmptyItem from './EmptyItem'

interface Props {
  symbols: string[]
  selectedSymbol: string
  entries?: SymbolEntry[]
  onSelect: (symbol: string) => void
}

export default function SearchedList({
  symbols,
  selectedSymbol,
  entries,
  onSelect,
}: Props) {
  if (!symbols.length) return <EmptyItem text="검색한 종목이 없습니다." />
  return (
    <>
      {symbols.map((symbol) => {
        const code = symbol.toUpperCase().replace(/\.KS$/, '')
        const name = entries?.find((entry) => entry.code === code)?.name
        return (
          <button
            key={code}
            type="button"
            className={`item stock-row ${code === selectedSymbol ? 'selected' : ''}`}
            onClick={() => onSelect(code)}
          >
            <div>
              <strong>{name || code}</strong>
              <span>
                {name ? `${code} · ` : ''}
                {code === selectedSymbol
                  ? '현재 차트 표시 중'
                  : '클릭해서 차트 보기'}
              </span>
            </div>
          </button>
        )
      })}
    </>
  )
}
