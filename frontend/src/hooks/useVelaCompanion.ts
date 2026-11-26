/**
 * Polls the Vela companion status while the settings view is mounted.
 *
 * Deliberately scoped to the settings section: nothing polls outside it, so
 * a machine without Vela pays no polling cost anywhere else in the app.
 */

import { useEffect, useState } from 'react'
import { getVelaCompanionStatus, type VelaCompanionStatus } from '../api/vela-companion'

const POLL_MS = 5000

export interface VelaCompanionState {
  /** Latest status answer; null until the first one arrives. */
  status: VelaCompanionStatus | null
  /** True when the status call failed (the section hides then). */
  failed: boolean
}

export function useVelaCompanionStatus(): VelaCompanionState {
  const [status, setStatus] = useState<VelaCompanionStatus | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const next = await getVelaCompanionStatus()
        if (cancelled) return
        setStatus(next)
        setFailed(false)
      } catch {
        if (!cancelled) setFailed(true)
      }
    }
    void tick()
    const id = window.setInterval(() => void tick(), POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  return { status, failed }
}
