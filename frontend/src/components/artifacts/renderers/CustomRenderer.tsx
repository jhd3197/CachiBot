/**
 * Custom artifact renderer — loads a plugin-provided iframe renderer.
 */

import { useEffect, useRef } from 'react'
import type { Artifact } from '../../../types'

interface CustomRendererProps {
  artifact: Artifact
}

export function CustomRenderer({ artifact }: CustomRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  // Communicate artifact data to the iframe via postMessage
  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const handleLoad = () => {
      iframe.contentWindow?.postMessage(
        {
          type: 'artifact_data',
          artifact: {
            id: artifact.id,
            type: artifact.type,
            title: artifact.title,
            content: artifact.content,
            metadata: artifact.metadata,
            version: artifact.version,
          },
        },
        '*'
      )
    }

    iframe.addEventListener('load', handleLoad)
    return () => iframe.removeEventListener('load', handleLoad)
  }, [artifact])

  // Build the renderer URL from the plugin name
  const rendererUrl = artifact.plugin
    ? `/api/plugins/external/${artifact.plugin}/static/renderer.html`
    : 'about:blank'

  return (
    <div className="artifact-custom">
      <iframe
        ref={iframeRef}
        src={rendererUrl}
        sandbox="allow-scripts allow-same-origin"
        className="artifact-custom__iframe"
        title={`${artifact.plugin} renderer`}
      />
    </div>
  )
}
