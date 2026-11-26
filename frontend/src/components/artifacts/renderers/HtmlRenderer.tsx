/**
 * HTML artifact renderer — sandboxed iframe with live HTML/CSS/JS preview.
 *
 * Optionally enters click-to-edit mode (html artifacts only): the preview
 * swaps to a srcDoc iframe carrying the htmlstudio bridge, and every edit is
 * patched into the clean source and saved through the artifacts store and
 * the server-side artifact store (which bumps the version).
 */

import { useRef, useEffect, useState } from 'react'
import { RefreshCw, ExternalLink, Printer, MousePointerClick } from 'lucide-react'
import { cn } from '../../../lib/utils'
import { useChatStore } from '../../../stores/bots'
import { useHtmlEdit } from '../../../hooks/useHtmlEdit'
import { HtmlEditInspector } from '../HtmlEditInspector'
import type { Artifact } from '../../../types'

interface HtmlRendererProps {
  artifact: Artifact
}

export function HtmlRenderer({ artifact }: HtmlRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [key, setKey] = useState(0)
  // Edit mode is keyed to the artifact id so switching artifacts exits it.
  const [editingId, setEditingId] = useState<string | null>(null)
  const editing = editingId === artifact.id
  // Agents replace artifact content wholesale while a run is in flight; a
  // manual edit racing that would be lost, so Edit hides until the run ends.
  const isRunning = useChatStore((s) => s.isLoading)
  const canEdit = artifact.type === 'html' && artifact.content.trim() !== '' && !isRunning
  const edit = useHtmlEdit(artifact, editing)

  // Update iframe content when artifact changes (view mode only — the edit
  // iframe renders from the hook's srcDoc instead).
  useEffect(() => {
    if (editing) return
    const iframe = iframeRef.current
    if (!iframe) return

    const doc = iframe.contentDocument
    if (doc) {
      doc.open()
      doc.write(artifact.content)
      doc.close()
    }
  }, [artifact.content, key, editing])

  const handleRefresh = () => setKey((k) => k + 1)

  const handleToggleEdit = () => {
    if (editing) {
      // Leaving edit mode: let the in-flight server save settle first (and
      // re-send the source if it changed since the last PUT), then close.
      void edit.flushSave().finally(() => setEditingId(null))
    } else {
      setEditingId(artifact.id)
    }
  }

  const handleOpenExternal = () => {
    const blob = new Blob([artifact.content], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    // Clean up after a delay
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  }

  const handlePrint = () => {
    // Open in a new window to avoid sandbox restrictions, then trigger print
    const printWindow = window.open('', '_blank')
    if (!printWindow) return
    printWindow.document.open()
    printWindow.document.write(artifact.content)
    printWindow.document.close()
    // Wait for content/styles to load before printing
    printWindow.addEventListener('load', () => {
      printWindow.focus()
      printWindow.print()
    })
    // Fallback if load already fired
    setTimeout(() => {
      printWindow.focus()
      printWindow.print()
    }, 500)
  }

  return (
    <div className="artifact-html">
      <div className="artifact-html__toolbar">
        {!editing && (
          <>
            <button
              onClick={handleRefresh}
              className="artifact-code__action-btn"
              title="Refresh preview"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handlePrint}
              className="artifact-code__action-btn"
              title="Print / Save as PDF"
            >
              <Printer className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handleOpenExternal}
              className="artifact-code__action-btn"
              title="Open in new tab"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </button>
          </>
        )}
        {(canEdit || editing) && (
          <button
            onClick={handleToggleEdit}
            className={cn('artifact-html__edit-toggle', editing && 'artifact-html__edit-toggle--active')}
            title={editing ? 'Back to preview' : 'Click elements in the preview to edit them'}
          >
            <MousePointerClick className="h-3.5 w-3.5" />
            {editing ? 'Editing' : 'Edit'}
          </button>
        )}
      </div>
      {editing ? (
        <div className="artifact-html__edit">
          <iframe
            ref={edit.iframeRef}
            onLoad={edit.handlePreviewLoad}
            srcDoc={edit.srcDoc ?? ''}
            sandbox="allow-scripts allow-same-origin allow-modals"
            className="artifact-html__iframe"
            title={`${artifact.title} (editing)`}
          />
          <HtmlEditInspector
            selection={edit.selection}
            error={edit.error}
            saveStatus={edit.saveStatus}
            canUndo={edit.canUndo}
            canRedo={edit.canRedo}
            onPatch={edit.applyEdit}
            onUndo={edit.undo}
            onRedo={edit.redo}
            onDone={handleToggleEdit}
          />
        </div>
      ) : (
        <iframe
          key={key}
          ref={iframeRef}
          sandbox="allow-scripts allow-same-origin allow-modals"
          className="artifact-html__iframe"
          title={artifact.title}
        />
      )}
    </div>
  )
}
