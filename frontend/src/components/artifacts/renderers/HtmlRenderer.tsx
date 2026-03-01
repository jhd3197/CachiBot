/**
 * HTML artifact renderer — sandboxed iframe with live HTML/CSS/JS preview.
 */

import { useRef, useEffect, useState } from 'react'
import { RefreshCw, ExternalLink } from 'lucide-react'
import type { Artifact } from '../../../types'

interface HtmlRendererProps {
  artifact: Artifact
}

export function HtmlRenderer({ artifact }: HtmlRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [key, setKey] = useState(0)

  // Update iframe content when artifact changes
  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const doc = iframe.contentDocument
    if (doc) {
      doc.open()
      doc.write(artifact.content)
      doc.close()
    }
  }, [artifact.content, key])

  const handleRefresh = () => setKey((k) => k + 1)

  const handleOpenExternal = () => {
    const blob = new Blob([artifact.content], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    // Clean up after a delay
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  }

  return (
    <div className="artifact-html">
      <div className="artifact-html__toolbar">
        <button
          onClick={handleRefresh}
          className="artifact-code__action-btn"
          title="Refresh preview"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={handleOpenExternal}
          className="artifact-code__action-btn"
          title="Open in new tab"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>
      <iframe
        key={key}
        ref={iframeRef}
        sandbox="allow-scripts allow-same-origin"
        className="artifact-html__iframe"
        title={artifact.title}
      />
    </div>
  )
}
