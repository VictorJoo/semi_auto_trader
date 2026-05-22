import { useCallback, useEffect, useMemo, useState } from 'react'
import type {
  AccountSnapshot,
  MarketSnapshot,
  Period,
  Position,
  SymbolEntry,
  Trade,
  VolumeRow,
} from '../types'
import { fetchMarket, fetchSnapshot } from '../api'
import { dateTime, money, signed } from '../format'
import { usePolling } from '../hooks/usePolling'
import { useToast } from '../hooks/useToast'
import { formatCollectedAt, getMarketStatus } from '../marketStatus'
import EmptyItem from './EmptyItem'
import OrderbookPanel from './OrderbookPanel'
import PriceChart from './PriceChart'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'today', label: '오늘' },
  { id: '1w', label: '1주' },
  { id: '3m', label: '3달' },
]

const FUND_PREFIXES = [
  '1Q ',
  'ACE ',
  'ARIRANG ',
  'HANARO ',
  'KODEX ',
  'KOSEF ',
  'PLUS ',
  'RISE ',
  'SOL ',
  'TIGER ',
  'TIMEFOLIO ',
  'UNICORN ',
  'WOORI ',
]

interface MarketViewProps {
  selectedSymbol: string
  onSelectedSymbolChange: (symbol: string) => void
  setNavSearchInput: (value: string) => void
}

export default function MarketView({
  selectedSymbol,
  onSelectedSymbolChange,
  setNavSearchInput,
}: MarketViewProps) {
  const { show } = useToast()
  const [period, setPeriod] = useState<Period>('today')
  const [data, setData] = useState<MarketSnapshot | null>(null)
  const [account, setAccount] = useState<AccountSnapshot | null>(null)
  const [chartLoading, setChartLoading] = useState<boolean>(true)

  const load = useCallback(async () => {
    try {
      const result = await fetchMarket(selectedSymbol, period)
      setData(result)
      if (selectedSymbol && result.selected_symbol) {
        setNavSearchInput(displayName(result.selected_symbol, result.quote?.name))
      }
    } catch (error) {
      show((error as Error).message, 'error')
    } finally {
      setChartLoading(false)
    }
  }, [selectedSymbol, period, show, setNavSearchInput])

  const loadAccount = useCallback(async () => {
    try {
      setAccount(await fetchSnapshot())
    } catch (error) {
      show((error as Error).message, 'error')
    }
  }, [show])

  useEffect(() => {
    setChartLoading(true)
    setData((current) =>
      current ? { ...current, chart: [], period } : current,
    )
  }, [period, selectedSymbol])

  usePolling(load, 10000)
  usePolling(loadAccount, 15000)

  const marketStatus = getMarketStatus()
  const collectedAt = data ? formatCollectedAt(new Date(data.collected_at)) : ''
  const ranking = useMemo(() => {
    return [...(data?.top_volume ?? [])].sort(
      (a, b) => tradingValue(b) - tradingValue(a),
    )
  }, [data?.top_volume])
  const selected = selectedSymbol || ranking[0]?.symbol || data?.selected_symbol || ''
  const selectedDataReady = Boolean(
    selected && data?.selected_symbol === selected,
  )

  useEffect(() => {
    const first = ranking[0]
    if (!selectedSymbol && first && data?.selected_symbol !== first.symbol) {
      onSelectedSymbolChange(first.symbol)
      setNavSearchInput(displayName(first.symbol, first.name))
    }
  }, [
    data?.selected_symbol,
    onSelectedSymbolChange,
    ranking,
    selectedSymbol,
    setNavSearchInput,
  ])

  function selectSymbol(symbol: string, name?: string) {
    onSelectedSymbolChange(symbol)
    setNavSearchInput(displayName(symbol, name))
  }

  return (
    <div className="toss-market-screen">
      <div className="toss-market-board">
        <section className="panel ranking-panel">
          <div className="ranking-head">
            <div>
              <div className="market-status">
                <span
                  className={`market-pill ${marketStatus.isOpen ? 'open' : 'closed'}`}
                >
                  {marketStatus.label}
                </span>
                {collectedAt && (
                  <span className="market-detail">오늘 {collectedAt} 기준</span>
                )}
              </div>
            </div>
            <div className="ranking-tabs">
              <button type="button" className="secondary active">
                토스증권 거래대금
              </button>
              <button type="button" className="secondary">
                실시간
              </button>
            </div>
          </div>
          <div className="market-list-detail">
            <div
              className="ranking-table"
              role="table"
              aria-label="거래대금 순위"
            >
              <div className="ranking-row ranking-row-head" role="row">
                <span>순위</span>
                <span>종목</span>
                <span>현재가</span>
                <span>등락률</span>
                <span>거래대금</span>
                <span>거래량</span>
              </div>
              {ranking.length === 0 ? (
                <RankingSkeleton />
              ) : (
                ranking.map((row, index) => (
                  <RankingRow
                    key={row.symbol}
                    row={row}
                    rank={index + 1}
                    selected={selected === row.symbol}
                    onSelect={() => selectSymbol(row.symbol, row.name)}
                  />
                ))
              )}
            </div>
            <aside className="selected-stock-panel selected-side-panel">
              {selected ? (
                <>
                <div className="selected-panel-head">
                  <SelectedQuote
                    data={selectedDataReady ? data : null}
                    fallbackSymbol={selected}
                  />
                </div>
                <div className="selected-trading-grid">
                  <div className="selected-chart-area">
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
                      points={selectedDataReady ? (data?.chart ?? []) : []}
                      period={period}
                      loading={chartLoading || !selectedDataReady}
                    />
                  </div>
                  <OrderbookPanel
                    symbol={selected}
                    name={selectedDataReady ? data?.quote?.name : undefined}
                    currentPrice={selectedDataReady ? data?.quote?.price : undefined}
                    onOrderPlaced={() => {
                      void load()
                      void loadAccount()
                    }}
                  />
                </div>
                </>
              ) : (
                <EmptyItem text="차트 정보를 불러오는 중입니다." />
              )}
            </aside>
          </div>
        </section>

        <AccountSidePanel account={account} />
      </div>
    </div>
  )
}

function RankingSkeleton() {
  return (
    <div className="ranking-skeleton" aria-label="순위 데이터를 불러오는 중">
      {Array.from({ length: 8 }, (_, index) => (
        <div className="ranking-row ranking-skeleton-row" key={index}>
          <span className="skeleton-line short" />
          <span className="skeleton-line wide" />
          <span className="skeleton-line" />
          <span className="skeleton-line" />
        </div>
      ))}
    </div>
  )
}

function RankingRow({
  row,
  rank,
  selected,
  onSelect,
}: {
  row: VolumeRow
  rank: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`ranking-row stock-rank-row ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      role="row"
    >
      <span className="rank-heart">♡ {rank}</span>
      <span className="rank-symbol">
        <strong>{row.name || row.symbol}</strong>
        <small>{row.symbol}</small>
      </span>
      <span>{money.format(row.price)}원</span>
      <span className={row.change_pct >= 0 ? 'SELL' : 'BUY'}>
        {signed(row.change_pct)}%
      </span>
      <span>{formatTradingValue(tradingValue(row))}</span>
      <span>{money.format(row.volume)}주</span>
    </button>
  )
}

function SelectedQuote({
  data,
  fallbackSymbol,
}: {
  data: MarketSnapshot | null
  fallbackSymbol: string
}) {
  if (!data?.quote) {
    return (
      <div className="selected-quote">
        <div>
          <strong>{fallbackSymbol}</strong>
          <span>종목 정보를 불러오는 중입니다.</span>
        </div>
      </div>
    )
  }
  const quote = data.quote
  return (
    <div className="selected-quote">
      <div>
        <strong>{quote.name || quote.symbol}</strong>
        <span>
          {quote.symbol} · {dateTime.format(new Date(quote.time))}
        </span>
      </div>
      <div>
        <strong>{money.format(quote.price)}원</strong>
        <span className={quote.change >= 0 ? 'SELL' : 'BUY'}>
          {signed(quote.change)} · {signed(quote.change_pct)}%
        </span>
      </div>
    </div>
  )
}

function AccountSidePanel({ account }: { account: AccountSnapshot | null }) {
  return (
    <aside className="account-side-panel">
      <section className="panel account-box">
        <div className="account-box-head">
          <h2>기본계좌</h2>
          <span>{account?.account_number || '-'}</span>
        </div>
        <div className="currency-boxes">
          <div>
            <span>원화</span>
            <strong>{money.format(account?.krw_cash ?? 0)}원</strong>
          </div>
          <div>
            <span>달러</span>
            <strong>${(account?.usd_cash ?? 0).toLocaleString('en-US')}</strong>
          </div>
        </div>
        <div className="investment-summary">
          <span>내 투자</span>
          <strong>{money.format(account?.total_value ?? 0)}원</strong>
          <em>{account?.account_label ?? '계좌 조회 중'}</em>
        </div>
      </section>

      <section className="panel holdings-box">
        <h2>보유 주식</h2>
        <div className="side-list">
          {(account?.positions ?? []).length === 0 ? (
            <EmptyItem text="보유 주식이 없습니다." />
          ) : (
            account!.positions.map((position) => (
              <HoldingRow key={position.symbol} position={position} />
            ))
          )}
        </div>
      </section>

      <section className="panel orders-box">
        <h2>주문내역</h2>
        <div className="order-tabs">
          <button type="button" className="secondary active">
            대기
          </button>
          <button type="button" className="secondary">
            완료
          </button>
          <button type="button" className="secondary">
            조건주문
          </button>
        </div>
        <div className="side-list">
          {(account?.trades ?? []).length === 0 ? (
            <EmptyItem text="표시할 주문 내역이 없습니다." />
          ) : (
            account!.trades.map((trade, index) => (
              <OrderRow key={`${trade.created_at}-${index}`} trade={trade} />
            ))
          )}
        </div>
      </section>
    </aside>
  )
}

function HoldingRow({ position }: { position: Position }) {
  return (
    <div className="holding-row">
      <div>
        <strong>{position.name || position.symbol}</strong>
        <span>
          {position.qty}주 · 평균 {money.format(position.avg_price)}원
        </span>
      </div>
      <div>
        <strong>{money.format(position.value ?? 0)}원</strong>
        <span className={(position.pnl_pct ?? 0) >= 0 ? 'SELL' : 'BUY'}>
          {signed(position.pnl_pct ?? 0)}%
        </span>
      </div>
    </div>
  )
}

function OrderRow({ trade }: { trade: Trade }) {
  return (
    <div className="holding-row">
      <div>
        <strong>
          {trade.action} {trade.symbol}
        </strong>
        <span>
          {trade.qty}주 · {trade.reason}
        </span>
      </div>
      <div>
        <strong>{money.format(trade.price)}원</strong>
        <span>{new Date(trade.created_at).toLocaleTimeString('ko-KR')}</span>
      </div>
    </div>
  )
}

function tradingValue(row: VolumeRow) {
  return row.trading_value ?? row.price * row.volume
}

function formatTradingValue(value: number) {
  const eok = value / 100000000
  if (eok >= 1) return `${money.format(eok)}억원`
  return `${money.format(value)}원`
}

export function displayName(code: string, name?: string) {
  return name ? `${name} (${code})` : code
}

export function scoreSearchResult(entry: SymbolEntry, query: string) {
  const code = entry.code.toLowerCase()
  const name = (entry.name ?? '').toLowerCase()
  const nameWithoutLeadingLetters = name.replace(/^[a-z0-9\s]+/, '')
  const display = `${name} (${code})`
  let score = 100
  if (name === query) score = 0
  else if (code === query) score = 1
  else if (nameWithoutLeadingLetters.startsWith(query)) score = 4
  else if (name.startsWith(query)) score = 5
  else if (code.startsWith(query)) score = 8
  else if (display.includes(query)) score = 20

  if (isFundLikeName(entry.name)) score += 25
  if (entry.market === 'KOSDAQ') score += 1
  return score + Math.min((entry.name || entry.code).length, 40) / 100
}

function isFundLikeName(name: string) {
  return FUND_PREFIXES.some((prefix) => name.startsWith(prefix))
}
