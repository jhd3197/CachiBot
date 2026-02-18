import { Brain } from 'lucide-react'

interface ThinkingIndicatorProps {
  content: string
}

export function ThinkingIndicator({ content }: ThinkingIndicatorProps) {
  return (
    <div className="chat-thinking">
      <div className="chat-thinking__icon">
        <Brain className="h-4 w-4" />
      </div>

      <div className="chat-thinking__body">
        <p className="chat-thinking__label">
          Thinking...
        </p>
        <p className="chat-thinking__content">
          {content}
        </p>
      </div>
    </div>
  )
}
