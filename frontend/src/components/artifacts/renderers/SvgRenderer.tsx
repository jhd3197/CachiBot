/**
 * SVG artifact renderer — inline SVG display with sanitization.
 */

import { useMemo } from 'react'
import type { Artifact } from '../../../types'

interface SvgRendererProps {
  artifact: Artifact
}

/**
 * Basic SVG sanitization — strips script tags and event handlers.
 */
function sanitizeSvg(svg: string): string {
  // Remove script tags
  let clean = svg.replace(/<script[\s\S]*?<\/script>/gi, '')
  // Remove on* event attributes
  clean = clean.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '')
  return clean
}

export function SvgRenderer({ artifact }: SvgRendererProps) {
  const sanitized = useMemo(() => sanitizeSvg(artifact.content), [artifact.content])

  return (
    <div className="artifact-svg">
      <div
        className="artifact-svg__content"
        dangerouslySetInnerHTML={{ __html: sanitized }}
      />
    </div>
  )
}
