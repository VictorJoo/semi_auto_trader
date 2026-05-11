import { useEffect, useRef } from 'react'

export function usePolling(callback: () => void, intervalMs: number) {
  const saved = useRef(callback)

  useEffect(() => {
    saved.current = callback
  }, [callback])

  useEffect(() => {
    saved.current()
    const id = window.setInterval(() => saved.current(), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
}
