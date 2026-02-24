import { useEffect, useRef, useState } from 'react'

/**
 * Truncate text to fit a container's width, recalculating on resize.
 * Uses canvas measureText for pixel-accurate measurement.
 */
export function useTruncate(text: string, font = '600 14px sans-serif') {
  const ref = useRef<HTMLElement>(null)
  const [display, setDisplay] = useState(text)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!
    ctx.font = font

    const update = () => {
      if (!ref.current) return
      const width = ref.current.clientWidth
      if (width === 0) return

      if (ctx.measureText(text).width <= width) {
        setDisplay(text)
        return
      }

      // Binary search for the max chars that fit with ellipsis
      let lo = 0
      let hi = text.length
      while (lo < hi) {
        const mid = Math.ceil((lo + hi) / 2)
        if (ctx.measureText(text.slice(0, mid) + '\u2026').width <= width) {
          lo = mid
        } else {
          hi = mid - 1
        }
      }
      setDisplay(lo > 0 ? text.slice(0, lo) + '\u2026' : '\u2026')
    }

    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [text, font])

  return { ref, display }
}
