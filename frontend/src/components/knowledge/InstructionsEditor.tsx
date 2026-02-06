/**
 * Instructions Editor Component
 *
 * Textarea for editing bot custom instructions.
 */

import { useEffect, useState, useCallback } from 'react'
import { Save, RefreshCw } from 'lucide-react'
import { useKnowledgeStore } from '../../stores/knowledge'

interface InstructionsEditorProps {
  botId: string
}

export function InstructionsEditor({ botId }: InstructionsEditorProps) {
  const {
    loadInstructions,
    updateInstructions,
    getInstructions,
    loadingInstructions,
  } = useKnowledgeStore()

  const savedContent = getInstructions(botId)
  const isLoading = loadingInstructions[botId]

  const [content, setContent] = useState(savedContent)
  const [isSaving, setIsSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)

  // Load instructions on mount
  useEffect(() => {
    loadInstructions(botId)
  }, [botId, loadInstructions])

  // Sync local state when saved content changes
  useEffect(() => {
    setContent(savedContent)
  }, [savedContent])

  const hasChanges = content !== savedContent

  const handleSave = useCallback(async () => {
    if (!hasChanges) return

    setIsSaving(true)
    try {
      await updateInstructions(botId, content)
      setLastSaved(new Date())
    } catch {
      // Error handled by store
    } finally {
      setIsSaving(false)
    }
  }, [botId, content, hasChanges, updateInstructions])

  // Auto-save after 2 seconds of inactivity
  useEffect(() => {
    if (!hasChanges) return

    const timeout = setTimeout(() => {
      handleSave()
    }, 2000)

    return () => clearTimeout(timeout)
  }, [content, hasChanges, handleSave])

  if (isLoading && !savedContent) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="h-5 w-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-zinc-300">
          Custom Instructions
        </label>
        <div className="flex items-center gap-2">
          {isSaving && (
            <span className="text-xs text-zinc-500">Saving...</span>
          )}
          {!isSaving && lastSaved && (
            <span className="text-xs text-zinc-500">
              Saved {lastSaved.toLocaleTimeString()}
            </span>
          )}
          {hasChanges && !isSaving && (
            <button
              onClick={handleSave}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 hover:bg-green-500 rounded transition-colors"
            >
              <Save className="h-3 w-3" />
              Save
            </button>
          )}
        </div>
      </div>

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Add custom instructions that will be included in every conversation with this bot..."
        className="w-full h-40 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-green-500 resize-none"
        maxLength={10000}
      />

      <p className="text-xs text-zinc-500">
        {content.length.toLocaleString()} / 10,000 characters
      </p>
    </div>
  )
}
