import type { AccountSnapshot, MarketSnapshot, Period, Trade } from './types'

interface ApiOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
}

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new Error(`요청 실패 (${response.status})`)
  }
  if (!response.ok || (payload as { ok?: boolean }).ok === false) {
    throw new Error(
      (payload as { error?: string })?.error || `요청 실패 (${response.status})`,
    )
  }
  return payload as T
}

export function fetchSnapshot(signal?: AbortSignal) {
  return request<AccountSnapshot>('/api/snapshot', { signal })
}

export function fetchMarket(
  symbol: string,
  period: Period,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ period })
  if (symbol) params.set('symbol', symbol)
  return request<MarketSnapshot>(`/api/market?${params.toString()}`, { signal })
}

export function approveSignal(signalId: string, qty?: number) {
  return request<{ ok: true; trade: Trade }>('/api/approve', {
    method: 'POST',
    body: { signal_id: signalId, qty },
  })
}

export function placeOrder(
  symbol: string,
  action: 'BUY' | 'SELL',
  qty: number,
) {
  return request<{ ok: true; trade: Trade }>('/api/order', {
    method: 'POST',
    body: { symbol, action, qty },
  })
}
