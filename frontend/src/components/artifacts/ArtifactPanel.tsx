/**
 * Artifact side panel — renders artifacts alongside the chat.
 *
 * Displays a header with title, type badge, version, and close button,
 * plus a content area that dispatches to type-specific renderers.
 */

import { useState, useCallback } from 'react'
import {
  X,
  Copy,
  Download,
  Maximize2,
  Minimize2,
  Code,
  Globe,
  FileText,
  Image,
  GitBranch,
  Component,
  Puzzle,
  Eye,
  CheckCircle,
} from 'lucide-react'
import { cn, copyToClipboard } from '../../lib/utils'
import { CodeRenderer } from './renderers/CodeRenderer'
import { HtmlRenderer } from './renderers/HtmlRenderer'
import { MarkdownArtifactRenderer } from './renderers/MarkdownRenderer'
import { SvgRenderer } from './renderers/SvgRenderer'
import { MermaidRenderer } from './renderers/MermaidRenderer'
import { ImageRenderer } from './renderers/ImageRenderer'
import { CustomRenderer } from './renderers/CustomRenderer'
import type { Artifact, ArtifactType } from '../../types'

interface ArtifactPanelProps {
  artifact: Artifact
  onClose: () => void
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
  html: 'HTML Preview',
  markdown: 'Document',
  svg: 'SVG',
  mermaid: 'Diagram',
  react: 'React Component',
  image: 'Image',
  custom: 'Custom',
}

export function ArtifactPanel({ artifact, onClose }: ArtifactPanelProps) {
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'content' | 'preview'>('content')

  const Icon = TYPE_ICONS[artifact.type] || Puzzle

  const handleCopy = useCallback(() => {
    copyToClipboard(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [artifact.content])

  const handleDownload = useCallback(() => {
    const ext = getFileExtension(artifact)
    const blob = new Blob([artifact.content], { type: getMimeType(artifact) })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${artifact.title.replace(/[^a-zA-Z0-9_-]/g, '_')}${ext}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [artifact])

  // For code artifacts, show Code/Preview tabs when language is html
  const showTabs = artifact.type === 'code' && artifact.language === 'html'

  return (
    <div className="artifact-panel">
      {/* Header */}
      <div className="artifact-panel__header">
        <div className="artifact-panel__title-row">
          <div className="artifact-panel__title-group">
            <Icon className="h-4 w-4 text-[var(--color-text-secondary)]" />
            <h3 className="artifact-panel__title">{artifact.title}</h3>
          </div>
          <button
            onClick={onClose}
            className="artifact-panel__close"
            title="Close panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="artifact-panel__meta-row">
          <span className="artifact-panel__badge">
            {TYPE_LABELS[artifact.type] || artifact.type}
          </span>
          {artifact.language && (
            <span className="artifact-panel__badge artifact-panel__badge--lang">
              {artifact.language}
            </span>
          )}
          {artifact.version > 1 && (
            <span className="artifact-panel__badge artifact-panel__badge--version">
              v{artifact.version}
            </span>
          )}
        </div>
      </div>

      {/* Tab bar (for code/preview toggle) */}
      {showTabs && (
        <div className="artifact-panel__tabs">
          <button
            onClick={() => setActiveTab('content')}
            className={cn(
              'artifact-panel__tab',
              activeTab === 'content' && 'artifact-panel__tab--active'
            )}
          >
            <Code className="h-3.5 w-3.5" />
            Code
          </button>
          <button
            onClick={() => setActiveTab('preview')}
            className={cn(
              'artifact-panel__tab',
              activeTab === 'preview' && 'artifact-panel__tab--active'
            )}
          >
            <Eye className="h-3.5 w-3.5" />
            Preview
          </button>
        </div>
      )}

      {/* Content area */}
      <div className="artifact-panel__content">
        {showTabs && activeTab === 'preview' ? (
          <HtmlRenderer artifact={artifact} />
        ) : (
          <ArtifactContent artifact={artifact} />
        )}
      </div>

      {/* Toolbar */}
      <div className="artifact-panel__toolbar">
        <button onClick={handleCopy} className="artifact-panel__tool-btn">
          {copied ? (
            <><CheckCircle className="h-3.5 w-3.5 text-green-400" /> Copied</>
          ) : (
            <><Copy className="h-3.5 w-3.5" /> Copy</>
          )}
        </button>
        <button onClick={handleDownload} className="artifact-panel__tool-btn">
          <Download className="h-3.5 w-3.5" /> Download
        </button>
      </div>
    </div>
  )
}

/** Dispatch to the correct renderer based on artifact type */
function ArtifactContent({ artifact }: { artifact: Artifact }) {
  switch (artifact.type) {
    case 'code':
      return <CodeRenderer artifact={artifact} />
    case 'html':
      return <HtmlRenderer artifact={artifact} />
    case 'markdown':
      return <MarkdownArtifactRenderer artifact={artifact} />
    case 'svg':
      return <SvgRenderer artifact={artifact} />
    case 'mermaid':
      return <MermaidRenderer artifact={artifact} />
    case 'image':
      return <ImageRenderer artifact={artifact} />
    case 'react':
      // React artifacts use the HTML renderer with a JSX wrapper
      return <CodeRenderer artifact={artifact} />
    case 'custom':
      return <CustomRenderer artifact={artifact} />
    default:
      return (
        <pre className="artifact-code__pre">
          <code>{artifact.content}</code>
        </pre>
      )
  }
}

function getFileExtension(artifact: Artifact): string {
  switch (artifact.type) {
    case 'code':
      return artifact.language ? `.${artifact.language}` : '.txt'
    case 'html':
      return '.html'
    case 'markdown':
      return '.md'
    case 'svg':
      return '.svg'
    case 'mermaid':
      return '.mmd'
    case 'image':
      return '.png'
    default:
      return '.txt'
  }
}

function getMimeType(artifact: Artifact): string {
  switch (artifact.type) {
    case 'html':
      return 'text/html'
    case 'markdown':
      return 'text/markdown'
    case 'svg':
      return 'image/svg+xml'
    case 'image':
      return 'image/png'
    default:
      return 'text/plain'
  }
}
