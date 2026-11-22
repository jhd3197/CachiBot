import { useState, useMemo } from 'react'
import {
  Copy,
  RotateCcw,
  ChevronDown,
  Code,
  CheckCircle,
  XCircle,
  User,
  Info,
  Reply,
  X,
  Image,
  Volume2,
  Brain,
  Pin,
  Bookmark,
  Check,
  Clock,
  Pencil,
  MoreHorizontal,
  GitBranch,
} from 'lucide-react'
import { ReactionBar as ReactionBarLazy } from '../rooms/ReactionBar'
import { useChatStore, useBotStore } from '../../stores/bots'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { useArtifactsStore } from '../../stores/artifacts'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { BotAvatar } from '../common/Avatar'
import { V2Menu, V2MenuItem } from '../common/V2Menu'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { ArtifactCard } from '../artifacts/ArtifactCard'
import { cn, copyToClipboard, darkenColor } from '../../lib/utils'
import type { ChatMessage, ToolCall, BotIcon, BotModels } from '../../types'

// =============================================================================
// CITATION UTILITIES
// =============================================================================

export function parseCiteMarkers(content: string): string[] {
  return [...content.matchAll(/\[cite:([a-f0-9-]+)\]/g)].map(m => m[1])
}

export function stripCiteMarkers(content: string): string {
  return content.replace(/\[cite:[a-f0-9-]+\]/g, '')
}

export function scrollToMessage(messageId: string) {
  const el = document.getElementById(`msg-${messageId}`)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.add('reply-highlight')
  setTimeout(() => el.classList.remove('reply-highlight'), 1500)
}

// =============================================================================
// REPLY PREVIEW
// =============================================================================

interface ReplyPreviewProps {
  content: string
  authorLabel: string
  onClick?: () => void
}

function ReplyPreview({ content, authorLabel, onClick }: ReplyPreviewProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="chat-reply-preview"
    >
      <Reply className="chat-reply-preview__icon" />
      <div className="min-w-0">
        <span className="chat-reply-preview__author">
          {authorLabel}
        </span>
        <p className="chat-reply-preview__text">
          {stripCiteMarkers(content).slice(0, 80)}{content.length > 80 ? '...' : ''}
        </p>
      </div>
    </button>
  )
}

// =============================================================================
// MEDIA DETECTION & EXTRACTION
// =============================================================================

/** Check if a tool result contains rendered media (image/audio data URIs). */
export function isMediaResult(result: unknown): boolean {
  if (typeof result !== 'string') return false
  return /!\[.*?\]\(data:(?:image|audio)\//.test(result)
}

interface MediaArtifact {
  type: 'image' | 'audio'
  dataUri: string
  toolName: string
  caption?: string
}

/** Extract media artifacts (images/audio) from tool call results. */
export function extractMediaArtifacts(toolCalls: ToolCall[]): MediaArtifact[] {
  const artifacts: MediaArtifact[] = []
  for (const call of toolCalls) {
    if (typeof call.result !== 'string') continue

    // Extract images: ![alt](data:image/...)
    const imgMatch = call.result.match(/!\[([^\]]*)\]\((data:image\/[^)]+)\)/)
    if (imgMatch) {
      const afterMedia = call.result.replace(/!\[[^\]]*\]\(data:[^)]+\)/, '').trim()
      artifacts.push({
        type: 'image',
        dataUri: imgMatch[2],
        toolName: call.tool,
        caption: afterMedia || undefined,
      })
      continue
    }

    // Extract audio: ![alt](data:audio/...)
    const audioMatch = call.result.match(/!\[([^\]]*)\]\((data:audio\/[^\s)]+(?:\s[^)]*)?)\)/)
    if (audioMatch) {
      const rawUri = audioMatch[2].replace(/\s+/g, '')
      const afterMedia = call.result.replace(/!\[[^\]]*\]\(data:audio\/[^)]+\)/, '').trim()
      artifacts.push({
        type: 'audio',
        dataUri: rawUri,
        toolName: call.tool,
        caption: afterMedia || undefined,
      })
    }
  }
  return artifacts
}

// =============================================================================
// IMAGE LIGHTBOX
// =============================================================================

function ImageLightbox({ src, onClose }: { src: string; onClose: () => void }) {
  return (
    <div
      className="chat-lightbox"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="chat-lightbox__close"
      >
        <X className="h-5 w-5" />
      </button>
      <img
        src={src}
        alt="Full size"
        className="chat-lightbox__image"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}

// =============================================================================
// MEDIA PREVIEWS
// =============================================================================

function MediaPreviews({ artifacts }: { artifacts: MediaArtifact[] }) {
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)

  if (artifacts.length === 0) return null

  return (
    <>
      {lightboxSrc && <ImageLightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />}
      <div className="chat-media-previews">
        {artifacts.map((artifact, i) => (
          artifact.type === 'image' ? (
            <button
              key={i}
              onClick={() => setLightboxSrc(artifact.dataUri)}
              className="chat-media-thumb"
            >
              <img
                src={artifact.dataUri}
                alt="Generated"
                className="chat-media-thumb__img"
              />
              <div className="chat-media-thumb__overlay">
                <Image className="h-5 w-5 text-white opacity-0 transition-opacity group-hover/thumb:opacity-100" />
              </div>
              {artifact.caption && (
                <div className="chat-media-thumb__caption">
                  <span>{artifact.caption}</span>
                </div>
              )}
            </button>
          ) : (
            <div
              key={i}
              className="chat-media-audio"
            >
              <div className="chat-media-audio__icon">
                <Volume2 className="h-4 w-4 text-cachi-400" />
              </div>
              <div className="min-w-0 flex-1">
                <audio controls className="chat-media-audio__player">
                  <source src={artifact.dataUri} type={artifact.dataUri.split(';')[0].replace('data:', '')} />
                </audio>
                {artifact.caption && (
                  <p className="chat-media-audio__caption">{artifact.caption}</p>
                )}
              </div>
            </div>
          )
        ))}
      </div>
    </>
  )
}

// =============================================================================
// MESSAGE TOOL CALL ITEM
// =============================================================================

// Map tool names to bot model slots
const TOOL_MODEL_SLOTS: Record<string, string> = {
  generate_image: 'image',
  generate_audio: 'audio',
  transcribe_audio: 'audio',
}

function getToolModel(toolName: string): string | undefined {
  const slot = TOOL_MODEL_SLOTS[toolName]
  if (!slot) return undefined
  const bot = useBotStore.getState().getActiveBot()
  return bot?.models?.[slot as keyof BotModels] || undefined
}

export function MessageToolCallItem({ call }: { call: ToolCall }) {
  const resultStr = typeof call.result === 'string' ? call.result : JSON.stringify(call.result ?? '', null, 2)
  const hasMedia = isMediaResult(call.result)
  const [expanded, setExpanded] = useState(hasMedia)
  const isSuccess = call.success !== false
  const toolModel = getToolModel(call.tool)

  return (
    <div className="chat-msg-tool-call">
      <button
        onClick={() => setExpanded(!expanded)}
        className="chat-msg-tool-call__header"
      >
        {isSuccess ? (
          <CheckCircle className="h-3 w-3 flex-shrink-0 text-green-400" />
        ) : (
          <XCircle className="h-3 w-3 flex-shrink-0 text-red-400" />
        )}
        <Code className="h-3 w-3 flex-shrink-0 text-[var(--color-text-secondary)]" />
        <span className="chat-msg-tool-call__name">{call.tool}</span>
        {toolModel && (
          <span className="chat-msg-tool-call__model">
            {toolModel}
          </span>
        )}
        <ChevronDown
          className={cn(
            'h-3 w-3 flex-shrink-0 text-[var(--color-text-secondary)] transition-transform',
            expanded && 'rotate-180'
          )}
        />
      </button>

      {expanded && (
        <div className="chat-msg-tool-call__body">
          <div className="space-y-2 text-xs">
            <div className="font-mono">
              <span className="text-[var(--color-text-secondary)]">Arguments:</span>
              <pre className="chat-msg-tool-call__code">
                {JSON.stringify(call.args, null, 2)}
              </pre>
            </div>
            {call.result !== undefined && (
              <div>
                <span className="font-mono text-[var(--color-text-secondary)]">Result:</span>
                {hasMedia ? (
                  <div className="mt-1">
                    <MarkdownRenderer content={resultStr} />
                  </div>
                ) : (
                  <pre className="chat-msg-tool-call__code max-h-32 overflow-auto">
                    {resultStr}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// MESSAGE ARTIFACT CARDS
// =============================================================================

function MessageArtifactCards({ messageId }: { messageId: string }) {
  const allArtifacts = useArtifactsStore((s) => s.artifacts)
  const artifacts = useMemo(
    () => Object.values(allArtifacts).filter((a) => a.messageId === messageId),
    [allArtifacts, messageId]
  )
  if (artifacts.length === 0) return null

  return (
    <div className="chat-message__artifacts">
      {artifacts.map((artifact) => (
        <ArtifactCard key={artifact.id} artifact={artifact} />
      ))}
    </div>
  )
}

// =============================================================================
// MESSAGE BUBBLE — SHARED COMPONENT
// =============================================================================

export interface MessageBubbleProps {
  message: {
    id: string
    content: string
    timestamp: string
    isUser: boolean
    isSystem?: boolean
    senderName?: string
    toolCalls?: ToolCall[]
    metadata?: Record<string, unknown>
    replyToId?: string
    thinking?: string
    reactions?: Array<{ emoji: string; count: number; userIds: string[] }>
  }
  botIcon?: BotIcon
  botColor?: string
  userColor?: string
  chatId?: string           // For reply/citation lookups (chat only)
  showSenderName?: boolean  // true for rooms
  isStreaming?: boolean      // true while bot is still generating
  onReply?: () => void      // Chat only (omit to hide Reply btn)
  onRetry?: () => void      // Future use
  onPin?: () => void        // Room only: pin this message
  onBookmark?: () => void   // Room only: bookmark this message
  isPinned?: boolean
  isBookmarked?: boolean
  roomId?: string           // Room context for reactions
}

export function MessageBubble({
  message,
  botIcon,
  botColor,
  userColor: userColorProp,
  chatId,
  showSenderName,
  isStreaming,
  onReply,
  onRetry,
  onPin,
  onBookmark,
  isPinned,
  isBookmarked,
  roomId,
}: MessageBubbleProps) {
  const { isUser, isSystem } = message
  const [copied, setCopied] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
  const [showToolCalls, setShowToolCalls] = useState(false)
  const [showThinkingPanel, setShowThinkingPanel] = useState(false)
  const { accentColor, customHex, showThinking } = useUIStore()
  const userColor = userColorProp ?? (
    accentColor === 'custom'
      ? generatePalette(customHex)[600]
      : accentColors[accentColor].palette[600]
  )
  const getMessageById = useChatStore((s) => s.getMessageById)

  // System messages: render inline
  if (isSystem) {
    return (
      <div className="chat-message chat-message--system">
        {message.content}
      </div>
    )
  }

  // Resolve reply-to message (chat only, when chatId is provided)
  const replyToMessage = chatId && message.replyToId
    ? getMessageById(chatId, message.replyToId)
    : undefined

  // Parse inline citations from bot messages (chat only)
  const citedIds = !isUser && chatId ? parseCiteMarkers(message.content) : []
  const displayContent = !isUser ? stripCiteMarkers(message.content) : message.content

  const handleCopy = () => {
    copyToClipboard(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasMetadata = !isUser && message.metadata && (
    message.metadata.tokens !== undefined ||
    message.metadata.cost !== undefined ||
    message.metadata.model !== undefined
  )

  return (
    <div
      id={`msg-${message.id}`}
      className={cn(
        'chat-message',
        isUser ? 'chat-message--user' : 'chat-message--bot'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'chat-message__avatar',
          isUser ? 'chat-message__avatar--user' : 'chat-message__avatar--bot'
        )}
        style={isUser ? { backgroundColor: userColor } : (botColor ? { backgroundColor: botColor + '30' } : undefined)}
      >
        {isUser ? (
          <User className="h-5 w-5" />
        ) : (
          <BotIconRenderer icon={botIcon || 'shield'} size={20} />
        )}
      </div>

      {/* Content */}
      <div className={cn(
        'chat-message__content',
        isUser ? 'chat-message__content--user' : 'chat-message__content--bot'
      )}>
        {/* Sender name header (rooms) */}
        {showSenderName && message.senderName && (
          <div className="chat-message__header">
            <span
              className={cn(
                'chat-message__sender',
                isUser ? 'chat-message__sender--user' : 'chat-message__sender--bot'
              )}
              style={!isUser && botColor ? { color: botColor } : undefined}
            >
              {message.senderName}
            </span>
            <span className="chat-message__time">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        )}

        {/* Reply preview (chat only) */}
        {replyToMessage && (
          <ReplyPreview
            content={replyToMessage.content}
            authorLabel={replyToMessage.role === 'user' ? 'You' : 'Assistant'}
            onClick={() => scrollToMessage(replyToMessage.id)}
          />
        )}

        {/* Inline citation previews (chat only) */}
        {citedIds.length > 0 && !replyToMessage && chatId && citedIds.map((citeId) => {
          const cited = getMessageById(chatId, citeId)
          if (!cited) return null
          return (
            <ReplyPreview
              key={citeId}
              content={cited.content}
              authorLabel={cited.role === 'user' ? 'You' : 'Assistant'}
              onClick={() => scrollToMessage(citeId)}
            />
          )
        })}

        <div
          className={cn(
            'chat-message__bubble',
            isUser ? 'chat-message__bubble--user' : 'chat-message__bubble--bot'
          )}
          style={isUser ? { background: `linear-gradient(135deg, ${userColor}, ${darkenColor(userColor, 15)})` } : undefined}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{displayContent}</div>
          ) : !displayContent && isStreaming ? (
            <div className="chat-typing-dots">
              <span className="chat-typing-dots__dot" />
              <span className="chat-typing-dots__dot" />
              <span className="chat-typing-dots__dot" />
            </div>
          ) : (
            <MarkdownRenderer content={displayContent} />
          )}
        </div>

        {/* Media previews from tool results — always visible */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <MediaPreviews artifacts={extractMediaArtifacts(message.toolCalls)} />
        )}

        {/* Artifact cards — rendered inline when a message has associated artifacts */}
        {!isUser && <MessageArtifactCards messageId={message.id} />}

        {/* Tool calls collapsible section */}
        {!isUser && showToolCalls && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="chat-message__tools-panel">
            {message.toolCalls.map((call) => (
              <MessageToolCallItem key={call.id} call={call} />
            ))}
          </div>
        )}

        {/* Thinking collapsible section */}
        {!isUser && message.thinking && showThinking && showThinkingPanel && (
          <div className="chat-msg-thinking">
            <div className="chat-msg-thinking__header">
              <Brain className="h-3 w-3" />
              <span>Thinking</span>
            </div>
            <div className="chat-msg-thinking__content">
              {message.thinking}
            </div>
          </div>
        )}

        {/* Usage info popover */}
        {showInfo && hasMetadata && (
          <div className="chat-message__info-panel">
            <div className="chat-message__info-grid">
              {message.metadata?.model !== undefined && (
                <>
                  <span>Model:</span>
                  <span className="chat-message__info-value">{String(message.metadata.model)}</span>
                </>
              )}
              {message.metadata?.tokens !== undefined && (
                <>
                  <span>Tokens:</span>
                  <span className="chat-message__info-value">
                    {Number(message.metadata.tokens).toLocaleString()}
                    {(message.metadata.promptTokens !== undefined || message.metadata.completionTokens !== undefined) && (
                      <span className="text-[var(--color-text-secondary)] ml-1">
                        ({Number(message.metadata.promptTokens || 0).toLocaleString()} in / {Number(message.metadata.completionTokens || 0).toLocaleString()} out)
                      </span>
                    )}
                  </span>
                </>
              )}
              {message.metadata?.cost !== undefined && (
                <>
                  <span>Cost:</span>
                  <span className="chat-message__info-value">${Number(message.metadata.cost).toFixed(6)}</span>
                </>
              )}
              {message.metadata?.iterations !== undefined && Number(message.metadata.iterations) > 1 && (
                <>
                  <span>Iterations:</span>
                  <span className="chat-message__info-value">{Number(message.metadata.iterations)}</span>
                </>
              )}
              {message.metadata?.elapsedMs !== undefined && Number(message.metadata.elapsedMs) > 0 && (
                <>
                  <span>Time:</span>
                  <span className="chat-message__info-value">
                    {Number(message.metadata.elapsedMs) < 1000
                      ? `${Math.round(Number(message.metadata.elapsedMs))}ms`
                      : `${(Number(message.metadata.elapsedMs) / 1000).toFixed(1)}s`}
                  </span>
                </>
              )}
              {message.metadata?.tokensPerSecond !== undefined && Number(message.metadata.tokensPerSecond) > 0 && (
                <>
                  <span>Speed:</span>
                  <span className="chat-message__info-value">{Number(message.metadata.tokensPerSecond).toFixed(1)} tok/s</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="chat-message__actions">
          {/* Reaction bar (rooms only) — first in actions */}
          {roomId && (
            <ReactionBarLazy roomId={roomId} messageId={message.id} reactions={message.reactions ?? []} />
          )}
          <button
            onClick={handleCopy}
            className="chat-message__action-btn"
          >
            {copied ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          {onReply && (
            <button
              onClick={onReply}
              className="chat-message__action-btn"
            >
              <Reply className="h-3 w-3" />
              Reply
            </button>
          )}
          {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
            <button
              onClick={() => setShowToolCalls(!showToolCalls)}
              className={cn(
                'chat-message__action-btn',
                showToolCalls && 'chat-message__action-btn--active'
              )}
            >
              <Code className="h-3 w-3" />
              Tools ({message.toolCalls.length})
            </button>
          )}
          {!isUser && message.thinking && showThinking && (
            <button
              onClick={() => setShowThinkingPanel(!showThinkingPanel)}
              className={cn(
                'chat-message__action-btn',
                showThinkingPanel && 'chat-message__action-btn--active'
              )}
            >
              <Brain className="h-3 w-3" />
              Thinking
            </button>
          )}
          {hasMetadata && (
            <button
              onClick={() => setShowInfo(!showInfo)}
              className={cn(
                'chat-message__action-btn',
                showInfo && 'chat-message__action-btn--active'
              )}
            >
              <Info className="h-3 w-3" />
              Info
            </button>
          )}
          {onRetry && !isUser && (
            <button onClick={onRetry} className="chat-message__action-btn">
              <RotateCcw className="h-3 w-3" />
              Retry
            </button>
          )}
          {onPin && (
            <button
              onClick={onPin}
              className={cn('chat-message__action-btn', isPinned && 'chat-message__action-btn--active')}
            >
              <Pin className="h-3 w-3" />
              {isPinned ? 'Unpin' : 'Pin'}
            </button>
          )}
          {onBookmark && (
            <button
              onClick={onBookmark}
              className={cn('chat-message__action-btn', isBookmarked && 'chat-message__action-btn--active')}
            >
              <Bookmark className="h-3 w-3" />
              {isBookmarked ? 'Saved' : 'Save'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Re-export ChatMessage type alias for convenience
export type { ChatMessage, ToolCall }

// =============================================================================
// UI v2 — bot-first chat message (design 02/03)
// =============================================================================

// Friendly verbs for the collapsed tool-activity line ("Read 3 files · …"),
// keyed by the real tool names the backend emits (cachibot/plugins/*).
const TOOL_SUMMARY_RULES: Array<{ match: RegExp; singular: string; plural: string }> = [
  { match: /^file_read$/, singular: 'read 1 file', plural: 'read {n} files' },
  { match: /^file_write$/, singular: 'wrote 1 file', plural: 'wrote {n} files' },
  { match: /^file_edit$/, singular: 'edited 1 file', plural: 'edited {n} files' },
  { match: /^file_(list|info)$/, singular: 'checked 1 file', plural: 'checked {n} files' },
  { match: /^python_execute$/, singular: 'ran code once', plural: 'ran code {n} times' },
  { match: /^(shell|bash|run_command|execute_command)$/, singular: 'ran 1 command', plural: 'ran {n} commands' },
  { match: /^(web_search|kb_search|note_search)$/, singular: 'ran 1 search', plural: 'ran {n} searches' },
  { match: /^generate_image$/, singular: 'generated 1 image', plural: 'generated {n} images' },
  { match: /^generate_audio$/, singular: 'generated 1 audio clip', plural: 'generated {n} audio clips' },
  { match: /^transcribe_audio$/, singular: 'transcribed 1 audio clip', plural: 'transcribed {n} audio clips' },
  { match: /^coding_agent$/, singular: 'ran the coding agent once', plural: 'ran the coding agent {n} times' },
  { match: /^(work_|todo_|schedule_|task_complete)/, singular: 'updated work once', plural: 'updated work {n} times' },
  { match: /^note_save$/, singular: 'saved 1 note', plural: 'saved {n} notes' },
]

function toolSummarySegment(tool: string, count: number): string {
  const rule = TOOL_SUMMARY_RULES.find((r) => r.match.test(tool))
  if (!rule) {
    return `used ${tool} ${count === 1 ? 'once' : `${count} times`}`
  }
  return count === 1 ? rule.singular : rule.plural.replace('{n}', String(count))
}

/** Collapsed "✓ Read 3 files · ran 2 commands" line from real tool calls. */
export function buildToolSummary(toolCalls: ToolCall[]): string {
  const order: string[] = []
  const counts = new Map<string, number>()
  for (const call of toolCalls) {
    if (!counts.has(call.tool)) {
      counts.set(call.tool, 0)
      order.push(call.tool)
    }
    counts.set(call.tool, (counts.get(call.tool) || 0) + 1)
  }
  const summary = order
    .map((tool) => toolSummarySegment(tool, counts.get(tool) || 0))
    .join(' · ')
  return summary.charAt(0).toUpperCase() + summary.slice(1)
}

/**
 * Hover "More" menu (design 11c): on any message, "Do this on the side"
 * starts a side task prefilled from that message's text. Anchored to the
 * side the turn sits on so it never clips off-screen (user turns are
 * right-aligned, bot turns left-aligned).
 */
function DoOnSideMenu({ onDoOnSide, align }: { onDoOnSide: () => void; align: 'left' | 'right' }) {
  const [open, setOpen] = useState(false)
  return (
    <span style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="v2-icon-action"
        title="More"
        aria-label="More"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open && (
        <V2Menu
          className={cn('v2-msg-more-menu', align === 'left' ? 'v2-msg-more-menu--left' : 'v2-msg-more-menu--right')}
          onClose={() => setOpen(false)}
        >
          <V2MenuItem
            icon={<GitBranch size={16} strokeWidth={1.8} />}
            onClick={() => {
              setOpen(false)
              onDoOnSide()
            }}
          >
            Do this on the side
          </V2MenuItem>
        </V2Menu>
      )}
    </span>
  )
}

export interface MessageBubbleV2Props {
  message: {
    id: string
    content: string
    timestamp: string
    isUser: boolean
    isSystem?: boolean
    toolCalls?: ToolCall[]
    metadata?: Record<string, unknown>
    replyToId?: string
    thinking?: string
  }
  botName: string
  botColor?: string
  chatId?: string
  isStreaming?: boolean
  onReply?: () => void
  onRegenerate?: () => void
  /** Edit-and-resend: called with the edited text for user messages */
  onEditSend?: (newContent: string) => void
  /** More › "Do this on the side": starts a side task prefilled from this message */
  onDoOnSide?: () => void
}

/**
 * UI v2 message: centered-column turn with a small BotAvatar + name label,
 * plain bubbles (#1a1b1e pill), hover icon actions, edit-in-place for user
 * messages, and tool activity collapsed into one muted line (design 02/03).
 */
export function MessageBubbleV2({
  message,
  botName,
  botColor,
  chatId,
  isStreaming,
  onReply,
  onRegenerate,
  onEditSend,
  onDoOnSide,
}: MessageBubbleV2Props) {
  const { isUser, isSystem } = message
  const [copied, setCopied] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
  const [showToolCalls, setShowToolCalls] = useState(false)
  const [showThinkingPanel, setShowThinkingPanel] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(message.content)
  const { showThinking } = useUIStore()
  const getMessageById = useChatStore((s) => s.getMessageById)

  if (isSystem) {
    return (
      <div className="chat-message chat-message--system">
        {message.content}
      </div>
    )
  }

  const replyToMessage = chatId && message.replyToId
    ? getMessageById(chatId, message.replyToId)
    : undefined

  const citedIds = !isUser && chatId ? parseCiteMarkers(message.content) : []
  const displayContent = !isUser ? stripCiteMarkers(message.content) : message.content

  const handleCopy = () => {
    copyToClipboard(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasToolCalls = !isUser && !!message.toolCalls && message.toolCalls.length > 0
  const hasThinking = !isUser && !!message.thinking && showThinking
  const hasMetadata = !isUser && message.metadata && (
    message.metadata.tokens !== undefined ||
    message.metadata.cost !== undefined ||
    message.metadata.model !== undefined
  )
  const isScheduled = !isUser && message.metadata?.scheduled === true

  // --- User turn -------------------------------------------------------------
  if (isUser) {
    return (
      <div id={`msg-${message.id}`} className="v2-msg v2-msg--user">
        {replyToMessage && (
          <ReplyPreview
            content={replyToMessage.content}
            authorLabel={replyToMessage.role === 'user' ? 'You' : botName}
            onClick={() => scrollToMessage(replyToMessage.id)}
          />
        )}
        {editing ? (
          <div className="v2-msg__edit">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  const trimmed = draft.trim()
                  if (trimmed) {
                    setEditing(false)
                    onEditSend?.(trimmed)
                  }
                }
                if (e.key === 'Escape') {
                  setEditing(false)
                  setDraft(message.content)
                }
              }}
              rows={Math.min(6, Math.max(1, draft.split('\n').length))}
              autoFocus
              className="v2-msg__edit-input"
            />
            <div className="v2-msg__edit-actions">
              <button
                type="button"
                className="v2-mini-btn"
                onClick={() => {
                  setEditing(false)
                  setDraft(message.content)
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="v2-mini-btn v2-mini-btn--primary"
                disabled={!draft.trim()}
                onClick={() => {
                  const trimmed = draft.trim()
                  setEditing(false)
                  if (trimmed) onEditSend?.(trimmed)
                }}
              >
                Send
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="v2-msg__bubble v2-msg__bubble--user">
              <div className="whitespace-pre-wrap">{displayContent}</div>
            </div>
            <div className="v2-msg__actions v2-msg__actions--user">
              <button
                type="button"
                onClick={() => {
                  setDraft(message.content)
                  setEditing(true)
                }}
                className="v2-icon-action"
                title="Edit"
                aria-label="Edit"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={handleCopy}
                className="v2-icon-action"
                title={copied ? 'Copied' : 'Copy'}
                aria-label={copied ? 'Copied' : 'Copy'}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              {onDoOnSide && <DoOnSideMenu onDoOnSide={onDoOnSide} align="right" />}
            </div>
          </>
        )}
      </div>
    )
  }

  // --- Bot turn ---------------------------------------------------------------
  return (
    <div id={`msg-${message.id}`} className="v2-msg v2-msg--bot">
      <div className="v2-msg__who">
        <BotAvatar color={botColor} name={botName} size={22} />
        <span className="v2-msg__name">{botName}</span>
      </div>

      {isScheduled && (
        <div className="v2-work-line">
          <Clock className="v2-work-line__icon" />
          <span>Scheduled routine</span>
        </div>
      )}

      {hasToolCalls && (
        <button
          type="button"
          onClick={() => setShowToolCalls(!showToolCalls)}
          className="v2-work-line v2-work-line--button"
          aria-expanded={showToolCalls}
        >
          {message.toolCalls!.every((c) => c.success !== false) ? (
            <Check className="v2-work-line__icon" />
          ) : (
            <XCircle className="v2-work-line__icon v2-work-line__icon--error" />
          )}
          <span>{buildToolSummary(message.toolCalls!)}</span>
          <ChevronDown
            className={cn(
              'v2-work-line__chevron',
              showToolCalls && 'v2-work-line__chevron--open'
            )}
          />
        </button>
      )}

      {replyToMessage && (
        <ReplyPreview
          content={replyToMessage.content}
          authorLabel={replyToMessage.role === 'user' ? 'You' : botName}
          onClick={() => scrollToMessage(replyToMessage.id)}
        />
      )}

      {citedIds.length > 0 && !replyToMessage && chatId && citedIds.map((citeId) => {
        const cited = getMessageById(chatId, citeId)
        if (!cited) return null
        return (
          <ReplyPreview
            key={citeId}
            content={cited.content}
            authorLabel={cited.role === 'user' ? 'You' : botName}
            onClick={() => scrollToMessage(citeId)}
          />
        )
      })}

      <div className="v2-msg__bubble v2-msg__bubble--bot">
        {!displayContent && isStreaming ? (
          <div className="chat-typing-dots">
            <span className="chat-typing-dots__dot" />
            <span className="chat-typing-dots__dot" />
            <span className="chat-typing-dots__dot" />
          </div>
        ) : (
          <MarkdownRenderer content={displayContent} />
        )}
      </div>

      {/* Media previews from tool results — always visible */}
      {hasToolCalls && (
        <MediaPreviews artifacts={extractMediaArtifacts(message.toolCalls!)} />
      )}

      {/* Artifact cards — rendered inline when a message has associated artifacts */}
      <MessageArtifactCards messageId={message.id} />

      {/* Expanded tool call details (existing ToolCallList item) */}
      {showToolCalls && hasToolCalls && (
        <div className="chat-message__tools-panel">
          {message.toolCalls!.map((call) => (
            <MessageToolCallItem key={call.id} call={call} />
          ))}
        </div>
      )}

      {/* Thinking collapsible section */}
      {hasThinking && showThinkingPanel && (
        <div className="chat-msg-thinking">
          <div className="chat-msg-thinking__header">
            <Brain className="h-3 w-3" />
            <span>Thinking</span>
          </div>
          <div className="chat-msg-thinking__content">
            {message.thinking}
          </div>
        </div>
      )}

      {/* Usage info popover */}
      {showInfo && hasMetadata && (
        <div className="chat-message__info-panel">
          <div className="chat-message__info-grid">
            {message.metadata?.model !== undefined && (
              <>
                <span>Model:</span>
                <span className="chat-message__info-value">{String(message.metadata.model)}</span>
              </>
            )}
            {message.metadata?.tokens !== undefined && (
              <>
                <span>Tokens:</span>
                <span className="chat-message__info-value">
                  {Number(message.metadata.tokens).toLocaleString()}
                  {(message.metadata.promptTokens !== undefined || message.metadata.completionTokens !== undefined) && (
                    <span className="text-[var(--color-text-secondary)] ml-1">
                      ({Number(message.metadata.promptTokens || 0).toLocaleString()} in / {Number(message.metadata.completionTokens || 0).toLocaleString()} out)
                    </span>
                  )}
                </span>
              </>
            )}
            {message.metadata?.cost !== undefined && (
              <>
                <span>Cost:</span>
                <span className="chat-message__info-value">${Number(message.metadata.cost).toFixed(6)}</span>
              </>
            )}
            {message.metadata?.iterations !== undefined && Number(message.metadata.iterations) > 1 && (
              <>
                <span>Iterations:</span>
                <span className="chat-message__info-value">{Number(message.metadata.iterations)}</span>
              </>
            )}
            {message.metadata?.elapsedMs !== undefined && Number(message.metadata.elapsedMs) > 0 && (
              <>
                <span>Time:</span>
                <span className="chat-message__info-value">
                  {Number(message.metadata.elapsedMs) < 1000
                    ? `${Math.round(Number(message.metadata.elapsedMs))}ms`
                    : `${(Number(message.metadata.elapsedMs) / 1000).toFixed(1)}s`}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Hover actions (design 03 — quiet icon row) */}
      <div className="v2-msg__actions">
        <button
          type="button"
          onClick={handleCopy}
          className="v2-icon-action"
          title={copied ? 'Copied' : 'Copy'}
          aria-label={copied ? 'Copied' : 'Copy'}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            className="v2-icon-action"
            title="Regenerate"
            aria-label="Regenerate"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
        {onReply && (
          <button
            type="button"
            onClick={onReply}
            className="v2-icon-action"
            title="Reply"
            aria-label="Reply"
          >
            <Reply className="h-3.5 w-3.5" />
          </button>
        )}
        {hasToolCalls && (
          <button
            type="button"
            onClick={() => setShowToolCalls(!showToolCalls)}
            className={cn('v2-icon-action', showToolCalls && 'v2-icon-action--active')}
            title={`Tools (${message.toolCalls!.length})`}
            aria-label={`Tools (${message.toolCalls!.length})`}
          >
            <Code className="h-3.5 w-3.5" />
          </button>
        )}
        {hasThinking && (
          <button
            type="button"
            onClick={() => setShowThinkingPanel(!showThinkingPanel)}
            className={cn('v2-icon-action', showThinkingPanel && 'v2-icon-action--active')}
            title="Thinking"
            aria-label="Thinking"
          >
            <Brain className="h-3.5 w-3.5" />
          </button>
        )}
        {hasMetadata && (
          <button
            type="button"
            onClick={() => setShowInfo(!showInfo)}
            className={cn('v2-icon-action', showInfo && 'v2-icon-action--active')}
            title="Info"
            aria-label="Info"
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        )}
        {onDoOnSide && <DoOnSideMenu onDoOnSide={onDoOnSide} align="left" />}
      </div>
    </div>
  )
}
