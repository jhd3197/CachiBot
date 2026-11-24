/**
 * useComputerPreview (C2) — live preview plumbing for the C4 computer views.
 *
 * While mounted and the tab is visible it:
 *  - sends a watch heartbeat every 15 s (watching keeps the computer awake;
 *    the server expires a watcher ~30 s after the beats stop), and
 *  - refetches the preview frame by revision: immediately when the
 *    `computer_update` WS reports a new `previewRevision`, plus a slow poll
 *    with If-None-Match as the fallback (a 304 costs nothing and means the
 *    bytes on screen are current).
 *
 * Everything stops while the tab is hidden and on unmount; nothing is faked
 * — a computer that is asleep or has nothing to show simply yields no frame.
 */

import { useEffect, useRef, useState } from 'react'
import { getComputerPreview, watchComputer } from '../api/computer'
import { useComputerStore } from '../stores/computer'

const WATCH_HEARTBEAT_MS = 15_000
const PREVIEW_POLL_MS = 3_000

export interface ComputerPreview {
  /** Object URL of the latest frame, or null when there is nothing real to show. */
  previewUrl: string | null
  /** Content revision of that frame (matches `previewRevision` when current). */
  revision: string | null
}

export function useComputerPreview(botId: string | null): ComputerPreview {
  const [frame, setFrame] = useState<ComputerPreview>({ previewUrl: null, revision: null })
  const etagRef = useRef<string | null>(null)
  const urlRef = useRef<string | null>(null)

  useEffect(() => {
    if (!botId) {
      setFrame({ previewUrl: null, revision: null })
      return
    }
    let cancelled = false
    let heartbeatTimer: number | undefined
    let pollTimer: number | undefined

    const heartbeat = async () => {
      try {
        await watchComputer(botId)
      } catch {
        // Asleep or unreachable: the next beat retries; nothing is faked.
      }
    }

    const poll = async () => {
      try {
        const next = await getComputerPreview(botId, etagRef.current)
        if (cancelled || next === null) return // 304: the frame on screen is current
        etagRef.current = next.etag
        const url = URL.createObjectURL(next.blob)
        if (urlRef.current) URL.revokeObjectURL(urlRef.current)
        urlRef.current = url
        setFrame({ previewUrl: url, revision: next.revision })
      } catch {
        // 409 (asleep) / 404 (nothing to show): keep the last real frame.
      }
    }

    const stop = () => {
      window.clearInterval(heartbeatTimer)
      window.clearInterval(pollTimer)
      heartbeatTimer = undefined
      pollTimer = undefined
    }

    const start = () => {
      if (heartbeatTimer !== undefined) return
      void heartbeat()
      void poll()
      heartbeatTimer = window.setInterval(() => void heartbeat(), WATCH_HEARTBEAT_MS)
      pollTimer = window.setInterval(() => void poll(), PREVIEW_POLL_MS)
    }

    const onVisibility = () => {
      if (document.hidden) {
        stop()
      } else {
        start()
      }
    }

    // Refetch as soon as the WS reports a new preview revision; the slow
    // poll above is the fallback for a missed event.
    const unsubscribe = useComputerStore.subscribe((state, previous) => {
      const revision = state.byBot[botId]?.previewRevision ?? null
      const before = previous.byBot[botId]?.previewRevision ?? null
      if (revision !== before && !document.hidden) {
        void poll()
      }
    })

    if (!document.hidden) {
      start()
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      cancelled = true
      stop()
      unsubscribe()
      document.removeEventListener('visibilitychange', onVisibility)
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
      etagRef.current = null
      setFrame({ previewUrl: null, revision: null })
    }
  }, [botId])

  return frame
}
