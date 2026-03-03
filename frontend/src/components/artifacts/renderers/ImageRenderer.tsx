/**
 * Image artifact renderer — displays images with metadata.
 */

import { useState } from 'react'
import { Download, Maximize2, X } from 'lucide-react'
import type { Artifact } from '../../../types'

interface ImageRendererProps {
  artifact: Artifact
}

export function ImageRenderer({ artifact }: ImageRendererProps) {
  const [fullscreen, setFullscreen] = useState(false)

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = artifact.content
    link.download = artifact.title || 'image'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="artifact-image">
      <div className="artifact-image__actions">
        <button
          onClick={() => setFullscreen(true)}
          className="artifact-code__action-btn"
          title="Fullscreen"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={handleDownload}
          className="artifact-code__action-btn"
          title="Download"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="artifact-image__content">
        <img
          src={artifact.content}
          alt={artifact.title}
          className="artifact-image__img"
        />
      </div>

      {/* Fullscreen overlay */}
      {fullscreen && (
        <div className="artifact-image__fullscreen" onClick={() => setFullscreen(false)}>
          <button
            onClick={() => setFullscreen(false)}
            className="artifact-image__fullscreen-close"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={artifact.content}
            alt={artifact.title}
            className="artifact-image__fullscreen-img"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}
