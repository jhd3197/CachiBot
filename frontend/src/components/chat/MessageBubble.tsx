import { useState } from 'react'
import {
  Copy,
  RotateCcw,
  ChevronDown,
  Code,
  Zap,
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
} from 'lucide-react'
import { ReactionBar as ReactionBarLazy } from '../rooms/ReactionBar'
import { useChatStore, useBotStore } from '../../stores/bots'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
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

function MessageToolCallItem({ call }: { call: ToolCall }) {
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

          {/* Inline media previews from tool results */}
          {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
            <MediaPreviews artifacts={extractMediaArtifacts(message.toolCalls)} />
          )}

          {/* Tool calls collapsible section */}
          {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3">
              <button
                onClick={() => setShowToolCalls(!showToolCalls)}
                className="chat-tool-toggle"
              >
                <Zap className="h-3 w-3" />
                <span>{message.toolCalls.length} tool action{message.toolCalls.length > 1 ? 's' : ''}</span>
                <ChevronDown
                  className={cn(
                    'h-3 w-3 transition-transform',
                    showToolCalls && 'rotate-180'
                  )}
                />
              </button>
              {showToolCalls && (
                <div className="mt-2 space-y-1.5">
                  {message.toolCalls.map((call) => (
                    <MessageToolCallItem key={call.id} call={call} />
                  ))}
                </div>
              )}
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
        </div>

        {/* Actions */}
        <div className="chat-message__actions">
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

        {/* Reaction bar (rooms only) */}
        {roomId && message.reactions && (
          <ReactionBarLazy roomId={roomId} messageId={message.id} reactions={message.reactions} />
        )}
      </div>
    </div>
  )
}

// Re-export ChatMessage type alias for convenience
export type { ChatMessage, ToolCall }
