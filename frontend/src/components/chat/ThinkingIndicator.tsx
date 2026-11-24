import { StatusLine } from '../common/StatusLine'

interface ThinkingIndicatorProps {
  content: string
  label?: string
  /** The bot's real color for the small status mark (omit for no mark). */
  markColor?: string
}

/**
 * Live thinking state (L3): a quiet v2 status line ("<Bot> is thinking")
 * with the streaming thought text below it. The text sits outside the
 * role="status" line so screen readers are not re-announced on every token.
 */
export function ThinkingIndicator({ content, label = 'Thinking', markColor }: ThinkingIndicatorProps) {
  return (
    <div className="v2-thinking">
      <StatusLine pending markColor={markColor}>
        {label}
      </StatusLine>
      <p className="v2-thinking__content">{content}</p>
    </div>
  )
}
