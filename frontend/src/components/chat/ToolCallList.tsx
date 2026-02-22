import { Wrench, Check, X, Loader2 } from 'lucide-react'
import type { ToolCall } from '../../types'
import { cn } from '../../lib/utils'

/** Extract the first markdown image data URI from a string, if any. */
function extractImageDataUri(text: string): string | null {
  const match = text.match(/!\[.*?\]\((data:image\/[^;]+;base64,[A-Za-z0-9+/=]+)\)/)
  return match ? match[1] : null
}

/** Extract the first markdown audio data URI from a string, if any. */
function extractAudioDataUri(text: string): string | null {
  const match = text.match(/!\[.*?\]\((data:audio\/[^;]+;base64,[A-Za-z0-9+/=\s]+)\)/)
  if (match) return match[1].replace(/\s/g, '')
  // Also check for raw data URI not wrapped in markdown
  const raw = text.match(/(data:audio\/[^;]+;base64,[A-Za-z0-9+/=\s]+)/)
  return raw ? raw[1].replace(/\s/g, '') : null
}

/** Extract metadata text that follows the media markdown. */
function extractResultMeta(text: string): string | null {
  // Strip markdown image/audio portions to get remaining metadata
  const stripped = text
    .replace(/!\[.*?\]\(data:(?:image|audio)\/[^;]+;base64,[A-Za-z0-9+/=\s]+\)/g, '')
    .trim()
  return stripped || null
}

interface ToolCallListProps {
  toolCalls: ToolCall[]
  instructionDeltas?: Record<string, string>
}

export function ToolCallList({ toolCalls, instructionDeltas }: ToolCallListProps) {
  return (
    <div className="space-y-2">
      {toolCalls.map((call) => (
        <ToolCallItem
          key={call.id}
          call={call}
          instructionText={instructionDeltas?.[call.id]}
        />
      ))}
    </div>
  )
}

interface ToolCallItemProps {
  call: ToolCall
  instructionText?: string
}

function ToolCallItem({ call, instructionText }: ToolCallItemProps) {
  const isComplete = call.endTime !== undefined
  const isSuccess = call.success !== false

  const resultStr = call.result != null ? String(call.result) : ''
  const imageUri = isComplete && isSuccess ? extractImageDataUri(resultStr) : null
  const audioUri = isComplete && isSuccess && !imageUri ? extractAudioDataUri(resultStr) : null
  const mediaUri = imageUri || audioUri
  const resultMeta = mediaUri ? extractResultMeta(resultStr) : null

  const statusClass = isComplete
    ? isSuccess ? 'tool-call--success' : 'tool-call--error'
    : 'tool-call--loading'

  const iconStatusClass = isComplete
    ? isSuccess ? 'tool-call__status-icon--success' : 'tool-call__status-icon--error'
    : 'tool-call__status-icon--loading'

  return (
    <div className={cn('tool-call', statusClass)}>
      <div className="tool-call__header">
        {/* Status icon */}
        <div className={cn('tool-call__status-icon', iconStatusClass)}>
          {isComplete ? (
            isSuccess ? (
              <Check className="h-3 w-3" />
            ) : (
              <X className="h-3 w-3" />
            )
          ) : (
            <Loader2 className="h-3 w-3 animate-spin" />
          )}
        </div>

        {/* Tool name */}
        <div className="tool-call__name">
          <Wrench className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
          <span>{call.tool}</span>
        </div>

        {/* Duration */}
        {isComplete && (
          <span className="tool-call__duration">
            {((call.endTime! - call.startTime) / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      {/* Arguments preview */}
      {Object.keys(call.args).length > 0 ? (
        <div className="tool-call__args">
          <pre>
            {JSON.stringify(call.args, null, 2).slice(0, 200)}
            {JSON.stringify(call.args, null, 2).length > 200 ? '...' : null}
          </pre>
        </div>
      ) : null}

      {/* Instruction delta (streaming text during tool execution) */}
      {!isComplete && instructionText ? (
        <div className="tool-call__instruction">
          <pre>{instructionText}</pre>
        </div>
      ) : null}

      {/* Media result (image or audio) */}
      {imageUri ? (
        <div className="tool-call__media">
          <img
            src={imageUri}
            alt="Generated"
          />
          {resultMeta ? (
            <p className="meta">
              {resultMeta}
            </p>
          ) : null}
        </div>
      ) : audioUri ? (
        <div className="tool-call__media">
          <audio controls src={audioUri} />
          {resultMeta ? (
            <p className="meta">
              {resultMeta}
            </p>
          ) : null}
        </div>
      ) : isComplete && call.result ? (
        <div className="tool-call__result">
          <pre>
            {resultStr.slice(0, 300)}
            {resultStr.length > 300 ? '...' : null}
          </pre>
        </div>
      ) : null}
    </div>
  )
}
