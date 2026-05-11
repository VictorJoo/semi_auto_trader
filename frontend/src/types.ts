export type Action = 'BUY' | 'SELL'

export interface Quote {
  symbol: string
  price: number
  change: number
  change_pct: number
  volume: number
  time: string
}

export interface ChartPoint {
  label: string
  tooltip_label?: string
  close: number
  volume: number
  realtime?: boolean
}

export interface VolumeRow {
  symbol: string
  price: number
  change_pct: number
  volume: number
}

export interface MarketSnapshot {
  symbols: string[]
  selected_symbol: string
  period: 'day' | 'week' | 'month'
  quote: Quote | null
  chart: ChartPoint[]
  top_volume: VolumeRow[]
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
  cash: number
  market_value: number
  total_value: number
  prices: Record<string, number>
  positions: Position[]
  signals: Signal[]
  trades: Trade[]
  backtests: Backtest[]
}

export type Period = MarketSnapshot['period']
