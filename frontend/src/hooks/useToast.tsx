import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastState {
  message: string
  kind: ToastKind
  visible: boolean
}

interface ToastApi {
  toast: ToastState
  show: (message: string, kind?: ToastKind) => void
  hide: () => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>({
    message: '',
    kind: 'info',
    visible: false,
  })
  const timer = useRef<number | null>(null)

  const show = useCallback((message: string, kind: ToastKind = 'success') => {
    if (timer.current) window.clearTimeout(timer.current)
    setToast({ message, kind, visible: true })
    timer.current = window.setTimeout(() => {
      setToast((current) => ({ ...current, visible: false }))
    }, 4200)
  }, [])

  const hide = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current)
    setToast((current) => ({ ...current, visible: false }))
  }, [])

  const value = useMemo<ToastApi>(
    () => ({ toast, show, hide }),
    [toast, show, hide],
  )

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
