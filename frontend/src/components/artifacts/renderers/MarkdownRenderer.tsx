/**
 * Markdown artifact renderer — rich document display.
 *
 * Reuses the existing MarkdownRenderer component from common/.
 */

import { MarkdownRenderer as BaseMarkdownRenderer } from '../../common/MarkdownRenderer'
import type { Artifact } from '../../../types'

interface MarkdownArtifactRendererProps {
  artifact: Artifact
}

export function MarkdownArtifactRenderer({ artifact }: MarkdownArtifactRendererProps) {
  return (
    <div className="artifact-markdown">
      <BaseMarkdownRenderer content={artifact.content} />
    </div>
  )
}
