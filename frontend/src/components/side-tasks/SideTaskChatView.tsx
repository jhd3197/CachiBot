/**
 * Side-task chat (design 11b): the child chat opened from a side-task card.
 * Header "Bot / task" with Stop (operator+, only while it can be stopped),
 * the sub-line ("Side task of <parent> · its files on branch side/… · reports
 * back when done") and the chat history rendered with the normal v2 message
 * rendering, loaded from the backend chat.
 *
 * There is deliberately NO composer: the backend has no path to resume a
 * needs-you side task from a user reply (a normal WS message would run in
 * the shared workspace, not the side task's worktree), so nothing is faked.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { getChat, getChatMessages } from '../../api/side-tasks'
import { useSideTasksStore } from '../../stores/side-tasks'
import { BotAvatar } from '../common/Avatar'
import { MessageBubbleV2 } from '../chat/MessageBubble'
import { SideTaskCard } from './SideTaskCard'
import { parseApiDate } from '../../lib/utils'
import type { BackendChat, BackendMessage, Bot, SideTask } from '../../types'

function dayKeyOf(timestamp: string): string {
  return parseApiDate(timestamp).toDateString()
}

function dayLabel(timestamp: string): string {
  // API timestamps are naive UTC — parseApiDate treats offset-less strings
  // as UTC so the label matches the local clock.
  const d = parseApiDate(timestamp)
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (dayKeyOf(timestamp) === dayKeyOf(now.toISOString())) {
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    return `Today ${time}`
  }
  if (dayKeyOf(timestamp) === yesterday.toDateString()) {
    return 'Yesterday'
  }
  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
}

interface SideTaskChatViewProps {
  task: SideTask
  bot: Bot
  /** Operator+ sees Stop / Retry merge / Discard (the APIs require it) */
  canOperate: boolean
}

export function SideTaskChatView({ task, bot, canOperate }: SideTaskChatViewProps) {
  const stop = useSideTasksStore((s) => s.stop)
  const [messages, setMessages] = useState<BackendMessage[] | null>(null)
  const [messagesFailed, setMessagesFailed] = useState(false)
  const [parent, setParent] = useState<BackendChat | null>(null)
  const [stopping, setStopping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const messagesRef = useRef<BackendMessage[] | null>(null)
  messagesRef.current = messages

  // Load the parent chat's real title for the sub-line (hidden on failure).
  useEffect(() => {
    let cancelled = false
    getChat(task.botId, task.parentChatId)
      .then((chat) => { if (!cancelled) setParent(chat) })
      .catch(() => { if (!cancelled) setParent(null) })
    return () => { cancelled = true }
  }, [task.botId, task.parentChatId])

  // Load history; while the side task runs, poll so its chat streams in.
  const loadMessages = useCallback(async () => {
    try {
      const fetched = await getChatMessages(task.botId, task.chatId, 200)
      setMessagesFailed(false)
      setMessages((prev) => {
        const prevSig = prev ? `${prev.length}:${prev[prev.length - 1]?.id ?? ''}` : null
        const nextSig = `${fetched.length}:${fetched[fetched.length - 1]?.id ?? ''}`
        return prevSig === nextSig ? prev : fetched
      })
    } catch {
      setMessagesFailed(true)
    }
  }, [task.botId, task.chatId])

  useEffect(() => {
    setMessages(null)
    void loadMessages()
  }, [loadMessages])

  const running = task.status === 'running'
  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => void loadMessages(), 4000)
    return () => window.clearInterval(id)
  }, [running, loadMessages])

  // Pin to the bottom as new messages stream in.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [messages])

  const handleStop = async () => {
    if (stopping) return
    setStopping(true)
    try {
      await stop(task.botId, task.id)
      toast.success('Side task stopped')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not stop the side task')
    } finally {
      setStopping(false)
    }
  }

  const stoppable = canOperate && (task.status === 'running' || task.status === 'waiting_for_slot')

  const startedAt = useMemo(
    () =>
      parseApiDate(task.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
    [task.createdAt]
  )

  return (
    <div className="side-chat">
      {/* Header: Bot / task title (design 11b) */}
      <div className="side-chat__header">
        <Link to={`/${bot.id}/chats`} className="side-chat__bot">
          <BotAvatar color={bot.color} name={bot.name} size={24} />
          {bot.name}
        </Link>
        <span className="side-chat__sep">/</span>
        <span className="side-chat__title">
          <GitBranch size={16} strokeWidth={1.8} />
          <span>{task.title}</span>
        </span>
        {stoppable && (
          <button type="button" className="side-chat__stop" disabled={stopping} onClick={() => void handleStop()}>
            {stopping ? 'Stopping…' : 'Stop'}
          </button>
        )}
      </div>

      {/* Sub-line: child of · its files on side/… · reports back when done */}
      <div className="side-chat__subline">
        <GitBranch size={14} strokeWidth={1.8} />
        <span>
          Side task of{' '}
          {parent ? (
            <Link to={`/${task.botId}/chats/${task.parentChatId}`}>{parent.title}</Link>
          ) : (
            'the main chat'
          )}
          {task.branch && (
            <>
              {' '}
              · its files on branch <code>{task.branch}</code>
            </>
          )}
          {' '}· reports back when done
        </span>
      </div>

      {/* Messages — the normal v2 chat rendering over the backend history */}
      <div className="side-chat__messages">
        <div className="chat-messages__inner">
          <p className="v2-day-sep">Started from the main chat at {startedAt}</p>

          {messages === null && !messagesFailed && (
            <p className="v2-status-line">
              <Loader2 className="v2-status-line__icon animate-spin" />
              <span>Loading messages…</span>
            </p>
          )}
          {messagesFailed && messages === null && (
            <p className="v2-status-line">Couldn&apos;t load the messages for this side task.</p>
          )}

          {messages?.map((msg, index) => {
            const sep =
              index === 0 || dayKeyOf(msg.timestamp) !== dayKeyOf(messages[index - 1].timestamp)
            return (
              <div key={msg.id} style={{ display: 'contents' }}>
                {sep && <p className="v2-day-sep">{dayLabel(msg.timestamp)}</p>}
                <MessageBubbleV2
                  message={{
                    id: msg.id,
                    content: msg.content,
                    timestamp: msg.timestamp,
                    isUser: msg.role === 'user',
                    isSystem: msg.role === 'system',
                    metadata: msg.metadata,
                  }}
                  botName={bot.name}
                  botColor={bot.color}
                  chatId={task.chatId}
                />
              </div>
            )
          })}

          {messages?.length === 0 && (
            <p className="v2-status-line">No messages yet — the side task is getting started.</p>
          )}

          {/* Current state with its real actions (retry merge / discard) */}
          <div className="side-task-cards">
            <SideTaskCard task={task} canOperate={canOperate} hideOpen />
          </div>

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
