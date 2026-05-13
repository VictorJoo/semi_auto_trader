import { useEffect } from 'react'

export function usePolling(callback: () => void, intervalMs: number) {
  useEffect(() => {
    callback()
    const id = window.setInterval(callback, intervalMs)
    return () => window.clearInterval(id)
  }, [callback, intervalMs])
}
