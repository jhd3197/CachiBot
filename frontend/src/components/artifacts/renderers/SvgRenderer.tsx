/**
 * SVG artifact renderer — inline SVG display with sanitization.
 */

import { useMemo } from 'react'
import DOMPurify from 'dompurify'
import type { Artifact } from '../../../types'

interface SvgRendererProps {
  artifact: Artifact
}

export function SvgRenderer({ artifact }: SvgRendererProps) {
  const sanitized = useMemo(
    () => DOMPurify.sanitize(artifact.content, { USE_PROFILES: { svg: true, svgFilters: true } }),
    [artifact.content]
  )

  return (
    <div className="artifact-svg">
      <div
        className="artifact-svg__content"
        dangerouslySetInnerHTML={{ __html: sanitized }}
      />
    </div>
  )
}
