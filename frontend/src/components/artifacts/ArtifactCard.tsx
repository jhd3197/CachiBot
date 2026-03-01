/**
 * Inline artifact card displayed within message bubbles.
 *
 * Shows a compact preview of an artifact with an "Open" button
 * that activates the artifact in the side panel.
 */

import {
  Code,
  Globe,
  FileText,
  Image,
  GitBranch,
  Component,
  Puzzle,
  ExternalLink,
} from 'lucide-react'
import { useArtifactsStore } from '../../stores/artifacts'
import type { Artifact, ArtifactType } from '../../types'

interface ArtifactCardProps {
  artifact: Artifact
}

const TYPE_ICONS: Record<ArtifactType, typeof Code> = {
  code: Code,
  html: Globe,
  markdown: FileText,
  svg: Image,
  mermaid: GitBranch,
  react: Component,
  image: Image,
  custom: Puzzle,
}

const TYPE_LABELS: Record<ArtifactType, string> = {
  code: 'Code',
  html: 'HTML',
  markdown: 'Document',
  svg: 'SVG',
  mermaid: 'Diagram',
  react: 'React',
  image: 'Image',
  custom: 'Custom',
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const setActive = useArtifactsStore((s) => s.setActive)
  const Icon = TYPE_ICONS[artifact.type] || Puzzle

  return (
    <button
      type="button"
      onClick={() => setActive(artifact.id)}
      className="artifact-card"
    >
      <div className="artifact-card__icon">
        <Icon className="h-4 w-4" />
      </div>
      <div className="artifact-card__info">
        <span className="artifact-card__title">{artifact.title}</span>
        <span className="artifact-card__meta">
          {TYPE_LABELS[artifact.type] || artifact.type}
          {artifact.language && ` \u00b7 ${artifact.language}`}
          {artifact.version > 1 && ` \u00b7 v${artifact.version}`}
        </span>
      </div>
      <ExternalLink className="artifact-card__open h-3.5 w-3.5" />
    </button>
  )
}
