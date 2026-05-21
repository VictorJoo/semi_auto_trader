import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import Clock from './components/Clock'
import HeaderAccountInfo from './components/HeaderAccountInfo'
import MarketView, { displayName, scoreSearchResult } from './components/MarketView'
import TradingView from './components/TradingView'
import Toast from './components/Toast'
import { fetchSymbols } from './api'
import { ToastProvider } from './hooks/useToast'
import type { SymbolEntry } from './types'

type Tab = 'market' | 'trading'

const TABS: { id: Tab; label: string }[] = [
  { id: 'market', label: '실시간 차트' },
  { id: 'trading', label: '반자동 매매' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('market')
  const [symbolEntries, setSymbolEntries] = useState<SymbolEntry[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const initializedSearchInput = useRef(false)

  const loadSymbols = useCallback(async () => {
    try {
      const result = await fetchSymbols()
      setSymbolEntries(result.symbols)
    } catch {
      setSymbolEntries([])
    }
  }, [])

  useEffect(() => {
    void loadSymbols()
  }, [loadSymbols])

  function extractCode(rawInput: string): string {
    const trimmed = rawInput.trim()
    if (!trimmed) return ''
    const parenMatch = trimmed.match(/\(([^)]+)\)\s*$/)
    const value = parenMatch ? parenMatch[1].trim() : trimmed
    return value.toUpperCase().replace(/\.KS$/, '')
  }

  const searchResults = useMemo(() => {
    const query = searchInput.trim().toLowerCase()
    if (!query) return []
    const normalizedQuery = query.replace(/\.ks$/i, '')
    return symbolEntries
      .filter((entry) => {
        const code = entry.code.toLowerCase()
        const name = (entry.name ?? '').toLowerCase()
        return (
          code.includes(normalizedQuery) ||
          name.includes(normalizedQuery) ||
          `${name} (${code})`.includes(normalizedQuery)
        )
      })
      .sort((left, right) => {
        const leftScore = scoreSearchResult(left, normalizedQuery)
        const rightScore = scoreSearchResult(right, normalizedQuery)
        if (leftScore !== rightScore) return leftScore - rightScore
        return left.name.localeCompare(right.name, 'ko-KR')
      })
      .slice(0, 30)
  }, [symbolEntries, searchInput])

  function selectSearchResult(entry: SymbolEntry) {
    if (!entry.code) return
    setSelectedSymbol(entry.code)
    setSearchInput(displayName(entry.code, entry.name))
    setSearchOpen(false)
    setTab('market')
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const first = searchResults[0]
    selectSearchResult(first ?? { code: extractCode(searchInput), name: '' })
  }

  return (
    <ToastProvider>
      <header className="topbar">
        <div className="topbar-mainnav">
          <div className="topbar-brand compact-brand">
            <h1>Trading Dashboard</h1>
          </div>
          <nav className="tabs topbar-tabs" aria-label="화면 탭">
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
          {tab === 'market' && (
            <form className="nav-search" onSubmit={onSubmit}>
              <div className="search-box">
                <input
                  placeholder="종목명 또는 6자리 코드를 검색하세요"
                  value={searchInput}
                  autoComplete="off"
                  onFocus={() => setSearchOpen(Boolean(searchInput.trim()))}
                  onBlur={() => window.setTimeout(() => setSearchOpen(false), 120)}
                  onChange={(event) => {
                    setSearchInput(event.target.value)
                    initializedSearchInput.current = true
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
                          <span>
                            {entry.code}
                            {entry.market ? ` · ${entry.market}` : ''}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
              <button type="submit">검색</button>
            </form>
          )}
        </div>
        <div className="topbar-status">
          <HeaderAccountInfo />
          <Clock />
        </div>
      </header>
      <main>
        <section className="tab-panel">
          {tab === 'market' ? (
            <MarketView
              selectedSymbol={selectedSymbol}
              onSelectedSymbolChange={setSelectedSymbol}
              setNavSearchInput={(next) => {
                if (!initializedSearchInput.current) setSearchInput(next)
              }}
            />
          ) : (
            <TradingView />
          )}
        </section>
      </main>
      <Toast />
    </ToastProvider>
  )
}
