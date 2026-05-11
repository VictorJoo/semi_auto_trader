import { useCallback, useState, type FormEvent } from 'react'
import type { MarketSnapshot, Period } from '../types'
import { fetchMarket } from '../api'
import { dateTime, money, signed } from '../format'
import { usePolling } from '../hooks/usePolling'
import { useToast } from '../hooks/useToast'
import PriceChart from './PriceChart'
import SymbolList from './SymbolList'
import SearchedList from './SearchedList'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'day', label: '일' },
  { id: 'week', label: '주' },
  { id: 'month', label: '월' },
]

export default function MarketView() {
  const { show } = useToast()
  const [period, setPeriod] = useState<Period>('day')
  const [symbol, setSymbol] = useState<string>('')
  const [searchInput, setSearchInput] = useState<string>('')
  const [searchedSymbols, setSearchedSymbols] = useState<string[]>([])
  const [data, setData] = useState<MarketSnapshot | null>(null)

  const rememberSymbol = useCallback((next: string) => {
    if (!next) return
    setSearchedSymbols((current) =>
      [next, ...current.filter((item) => item !== next)].slice(0, 8),
    )
  }, [])

  const load = useCallback(async () => {
    try {
      const result = await fetchMarket(symbol, period)
      setData(result)
      if (result.selected_symbol) {
        rememberSymbol(result.selected_symbol)
        if (!searchInput) setSearchInput(result.selected_symbol)
      }
    } catch (error) {
      show((error as Error).message, 'error')
    }
  }, [symbol, period, rememberSymbol, searchInput, show])

  usePolling(load, 2000)

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSymbol(searchInput.trim().toUpperCase())
  }

  function onSelectSymbol(next: string) {
    setSymbol(next)
    setSearchInput(next)
  }

  const selected = data?.selected_symbol ?? ''

  return (
    <div className="market-layout">
      <section className="panel chart-panel">
        <div className="market-head">
          <div>
            <h2>실시간 주식 가격</h2>
            <p>
              {data
                ? `마지막 수집: ${dateTime.format(new Date(data.collected_at))}`
                : '2초 단위로 가격을 수집합니다.'}
            </p>
          </div>
          <form className="symbol-search" onSubmit={onSubmit}>
            <input
              list="symbolOptions"
              placeholder="종목 검색 또는 입력"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <datalist id="symbolOptions">
              {(data?.symbols ?? []).map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
            <button type="submit">조회</button>
          </form>
        </div>

        <div className="quote">
          {data?.quote ? (
            <div className="quote-card">
              <div>
                <strong>{data.quote.symbol}</strong>
                <span>{dateTime.format(new Date(data.quote.time))}</span>
              </div>
              <div>
                <strong>{money.format(data.quote.price)}</strong>
                <span className={data.quote.change >= 0 ? 'BUY' : 'SELL'}>
                  {signed(data.quote.change)} · {signed(data.quote.change_pct)}%
                </span>
              </div>
              <div>
                <span>거래량</span>
                <strong>{money.format(data.quote.volume)}</strong>
              </div>
            </div>
          ) : (
            <div className="item">
              <span>표시할 종목이 없습니다.</span>
            </div>
          )}
        </div>

        <div className="periods" aria-label="차트 기간">
          {PERIODS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`secondary ${period === item.id ? 'active' : ''}`}
              onClick={() => setPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <PriceChart points={data?.chart ?? []} period={period} />
      </section>

      <aside className="market-sidebar">
        <section className="panel">
          <h2>검색한 주식</h2>
          <div className="list compact selectable">
            <SearchedList
              symbols={searchedSymbols}
              selectedSymbol={selected}
              onSelect={onSelectSymbol}
            />
          </div>
        </section>
        <section className="panel">
          <h2>상위 거래량 5개</h2>
          <div className="list compact selectable">
            <SymbolList
              rows={data?.top_volume ?? []}
              selectedSymbol={selected}
              onSelect={onSelectSymbol}
            />
          </div>
        </section>
      </aside>
    </div>
  )
}
