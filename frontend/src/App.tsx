import { useState } from 'react'
import MarketView from './components/MarketView'
import TradingView from './components/TradingView'
import Toast from './components/Toast'
import { ToastProvider } from './hooks/useToast'

type Tab = 'market' | 'trading'

const TABS: { id: Tab; label: string }[] = [
  { id: 'market', label: '실시간 차트' },
  { id: 'trading', label: '모의 매매' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('market')

  return (
    <ToastProvider>
      <header className="topbar">
        <div>
          <h1>Paper Trading Dashboard</h1>
          <p>실시간 차트와 모의 매매</p>
        </div>
      </header>
      <main>
        <nav className="tabs" aria-label="화면 탭">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`tab ${tab === item.id ? 'active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <section className="tab-panel">
          {tab === 'market' ? <MarketView /> : <TradingView />}
        </section>
      </main>
      <Toast />
    </ToastProvider>
  )
}
