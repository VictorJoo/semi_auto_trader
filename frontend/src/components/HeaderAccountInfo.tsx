import { useCallback, useEffect, useState } from 'react'
import { fetchSnapshot } from '../api'
import { money, usd } from '../format'
import type { AccountSnapshot } from '../types'

export default function HeaderAccountInfo() {
  const [snapshot, setSnapshot] = useState<AccountSnapshot | null>(null)

  const load = useCallback(async () => {
    try {
      setSnapshot(await fetchSnapshot())
    } catch {
      setSnapshot(null)
    }
  }, [])

  useEffect(() => {
    void load()
    const intervalId = window.setInterval(load, 15000)
    return () => window.clearInterval(intervalId)
  }, [load])

  if (!snapshot) {
    return (
      <div className="header-account" aria-label="계좌 정보">
        <span>계좌 정보를 불러오는 중</span>
      </div>
    )
  }

  return (
    <div className="header-account" aria-label="현재 계좌 정보">
      <div className="header-account-title">
        <span>{snapshot.account_label}</span>
        <strong>{snapshot.account_number || '계좌번호 없음'}</strong>
      </div>
      <div className="header-account-balances">
        <span>KRW {money.format(snapshot.krw_cash)}</span>
        <span>USD {usd.format(snapshot.usd_cash)}</span>
      </div>
    </div>
  )
}
