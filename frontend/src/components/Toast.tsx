import { useToast } from '../hooks/useToast'

export default function Toast() {
  const { toast } = useToast()
  const className = ['toast', toast.visible ? 'show' : '', toast.kind]
    .filter(Boolean)
    .join(' ')
  return (
    <div className={className} role="status" aria-live="polite">
      {toast.message}
    </div>
  )
}
