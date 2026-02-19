import { useState } from 'react'
import { X, Send, Loader2 } from 'lucide-react'

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

  const isActive = instruction.trim() && !loading

  return (
    <div className="bot-edit-panel">
      {/* Header */}
      <div className="bot-edit-panel__header">
        <div>
          <h3 className="bot-edit-panel__title">
            Ask Bot to Edit
          </h3>
          <p className="bot-edit-panel__subtitle">Editing: {scriptName}</p>
        </div>
        <button onClick={onClose} className="bot-edit-panel__close">
          <X size={16} />
        </button>
      </div>

      {/* Chat area */}
      <div className="bot-edit-panel__chat">
        <div className="bot-edit-panel__hint">
          Describe what changes you want the bot to make to this script.
          The bot will modify the code and show you the result for approval.
        </div>
      </div>

      {/* Input */}
      <div className="bot-edit-panel__input">
        <div className="bot-edit-panel__input-row">
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g., Add error handling for the API call..."
            rows={3}
            className="bot-edit-panel__textarea"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleSubmit()
              }
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!isActive}
            className={`bot-edit-panel__send bot-edit-panel__send--${isActive ? 'active' : 'disabled'}`}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
