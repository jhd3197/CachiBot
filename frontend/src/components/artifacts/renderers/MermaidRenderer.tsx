/**
 * Mermaid diagram artifact renderer — lazy-loads mermaid.js.
 */

import { useEffect, useRef, useState } from 'react'
import type { Artifact } from '../../../types'

interface MermaidRendererProps {
  artifact: Artifact
}

let mermaidLoaded = false
let mermaidPromise: Promise<void> | null = null

function loadMermaid(): Promise<void> {
  if (mermaidLoaded) return Promise.resolve()
  if (mermaidPromise) return mermaidPromise

  mermaidPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'
    script.onload = () => {
      mermaidLoaded = true
      // Initialize mermaid with dark theme detection
      const isDark = document.documentElement.classList.contains('dark')
      ;(window as unknown as Record<string, unknown>).mermaid &&
        (window as unknown as { mermaid: { initialize: (config: Record<string, unknown>) => void } }).mermaid.initialize({
          startOnLoad: false,
          theme: isDark ? 'dark' : 'default',
          securityLevel: 'strict',
        })
      resolve()
    }
    script.onerror = reject
    document.head.appendChild(script)
  })

  return mermaidPromise
}

export function MermaidRenderer({ artifact }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        setLoading(true)
        setError(null)
        await loadMermaid()

        if (cancelled || !containerRef.current) return

        const mermaid = (window as unknown as { mermaid: { render: (id: string, text: string) => Promise<{ svg: string }> } }).mermaid
        const id = `mermaid-${artifact.id.replace(/[^a-zA-Z0-9]/g, '')}`
        const { svg } = await mermaid.render(id, artifact.content)

        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to render diagram')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    render()
    return () => { cancelled = true }
  }, [artifact.content, artifact.id])

  return (
    <div className="artifact-mermaid">
      {loading && (
        <div className="artifact-mermaid__loading">
          Loading diagram...
        </div>
      )}
      {error && (
        <div className="artifact-mermaid__error">
          <p>Failed to render Mermaid diagram:</p>
          <pre>{error}</pre>
        </div>
      )}
      <div ref={containerRef} className="artifact-mermaid__content" />
    </div>
  )
}
