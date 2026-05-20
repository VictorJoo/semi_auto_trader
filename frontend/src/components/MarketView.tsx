import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import type { MarketSnapshot, Period, SymbolEntry } from '../types'
import { fetchMarket } from '../api'
import { dateTime, money, signed } from '../format'
import { usePolling } from '../hooks/usePolling'
import { useToast } from '../hooks/useToast'
import { formatCollectedAt, getMarketStatus } from '../marketStatus'
import PriceChart from './PriceChart'
import SymbolList from './SymbolList'
import SearchedList from './SearchedList'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'today', label: '오늘' },
  { id: '1d', label: '1일' },
  { id: '1w', label: '1주' },
  { id: '3m', label: '3달' },
]

export default function MarketView() {
  const { show } = useToast()
  const [period, setPeriod] = useState<Period>('today')
  const [symbol, setSymbol] = useState<string>('')
  const [searchInput, setSearchInput] = useState<string>('')
  const [searchedSymbols, setSearchedSymbols] = useState<string[]>([])
  const [data, setData] = useState<MarketSnapshot | null>(null)
  const [chartLoading, setChartLoading] = useState<boolean>(true)
  const [searchOpen, setSearchOpen] = useState<boolean>(false)

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
        const display = result.quote?.name
          ? `${result.quote.name} (${result.selected_symbol})`
          : result.selected_symbol
        setSearchInput((current) => current || display)
      }
    } catch (error) {
      show((error as Error).message, 'error')
    } finally {
      setChartLoading(false)
    }
  }, [symbol, period, rememberSymbol, show])

  useEffect(() => {
    setChartLoading(true)
    setData((current) =>
      current ? { ...current, chart: [], period } : current,
    )
  }, [period, symbol])

  usePolling(load, 15000)

  function extractCode(rawInput: string): string {
    const trimmed = rawInput.trim()
    if (!trimmed) return ''
    const parenMatch = trimmed.match(/\(([^)]+)\)\s*$/)
    const value = parenMatch ? parenMatch[1].trim() : trimmed
    return value.toUpperCase().replace(/\.KS$/, '')
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const first = searchResults[0]
    selectSearchResult(first ?? { code: extractCode(searchInput), name: '' })
  }

  function onSelectSymbol(next: string) {
    const code = extractCode(next)
    setSymbol(code)
    const entry = data?.symbols.find((s) => s.code === code)
    setSearchInput(entry?.name ? `${entry.name} (${code})` : code)
  }

  function selectSearchResult(entry: SymbolEntry) {
    if (!entry.code) return
    setSymbol(entry.code)
    setSearchInput(entry.name ? `${entry.name} (${entry.code})` : entry.code)
    setSearchOpen(false)
  }

  const searchResults = useMemo(() => {
    const query = searchInput.trim().toLowerCase()
    if (!query) return []
    const normalizedQuery = query.replace(/\.ks$/i, '')
    return (data?.symbols ?? [])
      .filter((entry) => {
        const code = entry.code.toLowerCase()
        const name = (entry.name ?? '').toLowerCase()
        return (
          code.includes(normalizedQuery) ||
          name.includes(normalizedQuery) ||
          `${name} (${code})`.includes(normalizedQuery)
        )
      })
      .slice(0, 30)
  }, [data?.symbols, searchInput])

  const selected = data?.selected_symbol ?? ''
  const marketStatus = getMarketStatus()
  const collectedAt = data ? formatCollectedAt(new Date(data.collected_at)) : ''

  return (
    <div className="market-layout">
      <section className="panel chart-panel">
        <div className="market-head">
          <div>
            <h2>실시간 주식 가격</h2>
            <div className="market-status">
              <span
                className={`market-pill ${marketStatus.isOpen ? 'open' : 'closed'}`}
              >
                {marketStatus.label}
              </span>
              <span className="market-detail">{marketStatus.detail}</span>
              {collectedAt && (
                <span className="market-detail">· 마지막 수집 {collectedAt}</span>
              )}
            </div>
          </div>
          <form className="symbol-search" onSubmit={onSubmit}>
            <div className="search-box">
              <input
                placeholder="종목명 또는 6자리 코드"
                value={searchInput}
                autoComplete="off"
                onFocus={() => setSearchOpen(Boolean(searchInput.trim()))}
                onBlur={() => window.setTimeout(() => setSearchOpen(false), 120)}
                onChange={(event) => {
                  setSearchInput(event.target.value)
                  setSearchOpen(Boolean(event.target.value.trim()))
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setSearchOpen(false)
                }}
              />
              {searchOpen && (
                <div className="search-results" role="listbox">
                  {searchResults.length === 0 ? (
                    <div className="search-result empty">검색 결과가 없습니다.</div>
                  ) : (
                    searchResults.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        className="search-result"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => selectSearchResult(entry)}
                      >
                        <strong>{entry.name || entry.code}</strong>
                        <span>{entry.code}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
            <button type="submit">조회</button>
          </form>
        </div>

        <div className="quote">
          {data?.quote ? (
            <div className="quote-card">
              <div>
                <strong>{data.quote.name || data.quote.symbol}</strong>
                <span>
                  {data.quote.name ? `${data.quote.symbol} · ` : ''}
                  {dateTime.format(new Date(data.quote.time))}
                </span>
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

        <PriceChart
          points={data?.chart ?? []}
          period={period}
          loading={chartLoading}
        />
      </section>

      <aside className="market-sidebar">
        <section className="panel">
          <h2>검색한 주식</h2>
          <div className="list compact selectable">
            <SearchedList
              symbols={searchedSymbols}
              selectedSymbol={selected}
              entries={data?.symbols}
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
