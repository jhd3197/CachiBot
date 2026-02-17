import { useState } from 'react'
import { X, Send, Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

interface BotEditPanelProps {
  open: boolean
  onClose: () => void
  scriptName: string
  currentCode: string
  onApplyEdit: (newCode: string) => void
}

export function BotEditPanel({
  open,
  onClose,
  scriptName,
  currentCode,
  onApplyEdit,
}: BotEditPanelProps) {
  const [instruction, setInstruction] = useState('')
  const [loading, setLoading] = useState(false)

  if (!open) return null

  const handleSubmit = async () => {
    if (!instruction.trim()) return
    setLoading(true)

    // In a full implementation, this would call the bot's chat API
    // with the current code and instruction, and return the edited code.
    // For now, this is a placeholder.
    setTimeout(() => {
      setLoading(false)
      setInstruction('')
    }, 2000)
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-96 flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Ask Bot to Edit
          </h3>
          <p className="text-xs text-zinc-500">Editing: {scriptName}</p>
        </div>
        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-auto p-4">
        <div className="text-xs text-zinc-400">
          Describe what changes you want the bot to make to this script.
          The bot will modify the code and show you the result for approval.
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <div className="flex items-end gap-2">
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g., Add error handling for the API call..."
            rows={3}
            className="flex-1 resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 placeholder-zinc-400 focus:border-accent-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleSubmit()
              }
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!instruction.trim() || loading}
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
              instruction.trim() && !loading
                ? 'bg-accent-600 text-white hover:bg-accent-700'
                : 'bg-zinc-100 text-zinc-400 dark:bg-zinc-800'
            )}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
