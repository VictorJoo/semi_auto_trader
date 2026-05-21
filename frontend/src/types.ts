export type Action = 'BUY' | 'SELL'

export interface Quote {
  symbol: string
  name?: string
  price: number
  change: number
  change_pct: number
  volume: number
  time: string
}

export type ChartSession = 'pre' | 'regular' | 'after'

export interface ChartPoint {
  label: string
  tooltip_label?: string
  close: number
  volume: number
  realtime?: boolean
  session?: ChartSession
}

export interface VolumeRow {
  symbol: string
  name?: string
  price: number
  change_pct: number
  volume: number
  trading_value?: number
}

export interface OrderbookLevel {
  level: number
  price: number
  qty: number
}

export interface OrderbookSnapshot {
  symbol: string
  name?: string
  asks: OrderbookLevel[]
  bids: OrderbookLevel[]
  expected_price: number
  expected_qty: number
  total_ask_qty: number
  total_bid_qty: number
  collected_at: string
}

export interface SymbolEntry {
  code: string
  name: string
  market?: string
}

export interface MarketSnapshot {
  symbols: SymbolEntry[]
  selected_symbol: string
  period: 'today' | '1w' | '3m'
  quote: Quote | null
  chart: ChartPoint[]
  top_volume: VolumeRow[]
  collected_at: string
}

export interface SymbolMasterSnapshot {
  symbols: SymbolEntry[]
  count: number
  collected_at: string
}

export interface Signal {
  id: string
  created_at: string
  symbol: string
  action: Action
  price: number
  confidence: number
  reasons: string[]
  suggested_qty: number
}

export interface Position {
  symbol: string
  name?: string
  qty: number
  avg_price: number
  current_price?: number
  value?: number
  pnl_pct: number
}

export interface Trade {
  created_at: string
  symbol: string
  action: Action
  qty: number
  price: number
  reason: string
}

export interface Backtest {
  symbol: string
  start_cash: number
  final_value: number
  return_pct: number
  trade_count: number
}

export interface AccountSnapshot {
  broker_source: string
  broker_error: string | null
  account_label: string
  account_number: string
  cash: number
  krw_cash: number
  usd_cash: number
  market_value: number
  total_value: number
  prices: Record<string, number>
  positions: Position[]
  signals: Signal[]
  trades: Trade[]
  backtests: Backtest[]
}

export type Period = MarketSnapshot['period']
