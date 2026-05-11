import EmptyItem from './EmptyItem'

interface Props {
  symbols: string[]
  selectedSymbol: string
  onSelect: (symbol: string) => void
}

export default function SearchedList({
  symbols,
  selectedSymbol,
  onSelect,
}: Props) {
  if (!symbols.length) return <EmptyItem text="검색한 종목이 없습니다." />
  return (
    <>
      {symbols.map((symbol) => (
        <button
          key={symbol}
          type="button"
          className={`item stock-row ${symbol === selectedSymbol ? 'selected' : ''}`}
          onClick={() => onSelect(symbol)}
        >
          <div>
            <strong>{symbol}</strong>
            <span>
              {symbol === selectedSymbol
                ? '현재 차트 표시 중'
                : '클릭해서 차트 보기'}
            </span>
          </div>
        </button>
      ))}
    </>
  )
}
