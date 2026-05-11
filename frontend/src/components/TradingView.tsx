import { useCallback, useEffect, useState } from 'react'
import type { AccountSnapshot } from '../types'
import { fetchSnapshot } from '../api'
import { money, pct } from '../format'
import { useToast } from '../hooks/useToast'
import EmptyItem from './EmptyItem'
import SignalList from './SignalList'
import ManualOrderForm from './ManualOrderForm'

export default function TradingView() {
  const { show } = useToast()
  const [data, setData] = useState<AccountSnapshot | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await fetchSnapshot())
    } catch (error) {
      show((error as Error).message, 'error')
    }
  }, [show])

  useEffect(() => {
    load()
  }, [load])

  if (!data) {
    return (
      <section className="panel">
        <p>계좌 정보를 불러오는 중…</p>
      </section>
    )
  }

  const isKis = data.broker_source === 'korea_investment'
  const status = data.broker_error
    ? `계좌 조회 실패: ${data.broker_error}`
    : `계좌 기준: ${isKis ? '한국투자증권 모의투자' : '로컬 모의투자'}`

  return (
    <>
      <header className="metrics-header">
        <button
          type="button"
          className="secondary"
          onClick={load}
          aria-label="새로고침"
        >
          새로고침
        </button>
      </header>
      <section className="metrics">
        <div>
          <span>총 평가금액</span>
          <strong>{money.format(data.total_value)}</strong>
        </div>
        <div>
          <span>현금</span>
          <strong>{money.format(data.cash)}</strong>
        </div>
        <div>
          <span>주식 평가액</span>
          <strong>{money.format(data.market_value)}</strong>
        </div>
        <div>
          <span>신호</span>
          <strong>{data.signals.length}</strong>
        </div>
      </section>
      <p className={`status ${data.broker_error ? 'error' : ''}`}>{status}</p>

      <section className="grid">
        <div className="panel">
          <h2>매수·매도 신호</h2>
          <div className="list">
            <SignalList signals={data.signals} onApproved={load} />
          </div>
        </div>
        <div className="panel">
          <h2>보유 포지션</h2>
          <div className="list compact">
            {data.positions.length === 0 ? (
              <EmptyItem text="보유 포지션이 없습니다." />
            ) : (
              data.positions.map((position) => (
                <div className="item" key={position.symbol}>
                  <div>
                    <strong>{position.symbol}</strong>
                    <span>{position.name || position.symbol}</span>
                    <span>
                      {position.qty}주 · 평균 {money.format(position.avg_price)}
                    </span>
                  </div>
                  <strong>{pct.format(position.pnl_pct)}%</strong>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="grid">
        <div className="panel">
          <h2>백테스트</h2>
          <div className="list compact">
            {data.backtests.length === 0 ? (
              <EmptyItem text="백테스트 결과가 없습니다." />
            ) : (
              data.backtests.map((result) => (
                <div className="item" key={result.symbol}>
                  <div>
                    <strong>{result.symbol}</strong>
                    <span>{result.trade_count}회 거래</span>
                  </div>
                  <strong>{pct.format(result.return_pct)}%</strong>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="panel">
          <h2>최근 주문</h2>
          <div className="list compact">
            {isKis ? (
              <EmptyItem text="한국투자증권 주문 내역 조회는 아직 연결되지 않았습니다." />
            ) : data.trades.length === 0 ? (
              <EmptyItem text="주문 내역이 없습니다." />
            ) : (
              data.trades.map((trade, index) => (
                <div className="item" key={index}>
                  <div>
                    <strong>
                      {trade.action} {trade.symbol} x {trade.qty}
                    </strong>
                    <span>{trade.reason}</span>
                  </div>
                  <strong>{money.format(trade.price)}</strong>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>수동 모의 주문</h2>
        <ManualOrderForm onPlaced={load} />
      </section>
    </>
  )
}
