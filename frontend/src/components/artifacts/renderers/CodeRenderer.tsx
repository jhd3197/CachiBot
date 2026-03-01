/**
 * Code artifact renderer with syntax highlighting and optional editing.
 */

import { useState, useRef, useCallback } from 'react'
import { Copy, CheckCircle, Pencil, Eye } from 'lucide-react'
import { cn, copyToClipboard } from '../../../lib/utils'
import type { Artifact } from '../../../types'

interface CodeRendererProps {
  artifact: Artifact
  onContentChange?: (content: string) => void
}

export function CodeRenderer({ artifact, onContentChange }: CodeRendererProps) {
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const editable = artifact.metadata?.editable !== false

  const handleCopy = useCallback(() => {
    copyToClipboard(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [artifact.content])

  const handleEdit = useCallback(() => {
    setEditing(true)
    // Focus the textarea after render
    requestAnimationFrame(() => textareaRef.current?.focus())
  }, [])

  const handleBlur = useCallback(() => {
    if (textareaRef.current && onContentChange) {
      onContentChange(textareaRef.current.value)
    }
  }, [onContentChange])

  return (
    <div className="artifact-code">
      {/* Language badge + actions */}
      <div className="artifact-code__header">
        <span className="artifact-code__lang">
          {artifact.language || 'text'}
        </span>
        <div className="artifact-code__actions">
          {editable && (
            <button
              onClick={() => editing ? setEditing(false) : handleEdit()}
              className="artifact-code__action-btn"
              title={editing ? 'Preview' : 'Edit'}
            >
              {editing ? <Eye className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
            </button>
          )}
          <button
            onClick={handleCopy}
            className="artifact-code__action-btn"
            title="Copy code"
          >
            {copied ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Code content */}
      <div className="artifact-code__content">
        {editing ? (
          <textarea
            ref={textareaRef}
            defaultValue={artifact.content}
            onBlur={handleBlur}
            className="artifact-code__editor"
            spellCheck={false}
          />
        ) : (
          <pre className="artifact-code__pre">
            <code>{artifact.content}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
