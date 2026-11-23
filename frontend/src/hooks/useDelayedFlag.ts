import { useEffect, useState } from 'react'

/**
 * Returns false until `pending` has stayed true for `delayMs`, and false
 * again immediately when `pending` turns false. Use it to keep spinners
 * (and other pending UI) from flashing on sub-200ms work:
 *
 *   const showSpinner = useDelayedFlag(saving)
 *
 * Skeletons may still render immediately when a caller chooses not to delay.
 */
export function useDelayedFlag(pending: boolean, delayMs = 200): boolean {
  const [elapsed, setElapsed] = useState(false)

  useEffect(() => {
    if (!pending) {
      setElapsed(false)
      return
    }
    const id = window.setTimeout(() => setElapsed(true), delayMs)
    return () => window.clearTimeout(id)
  }, [pending, delayMs])

  return pending && elapsed
}
