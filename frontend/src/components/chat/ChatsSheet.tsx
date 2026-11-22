import { useState, useEffect, useRef } from 'react'
import {
  Plus,
  Search,
  X,
  Pin,
  Trash2,
  Archive,
  MoreHorizontal,
  MessageSquare,
  MessageCircle,
  Eraser,
  Download,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useChatStore } from '../../stores/bots'
import { clearChatMessages } from '../../api/client'
import { BotAvatar } from '../common/Avatar'
import { cn, downloadJson, slugify } from '../../lib/utils'
import type { Bot, Chat } from '../../types'

interface ChatsSheetProps {
  bot: Bot
  onClose: () => void
}

/**
 * "Earlier chats" sheet (design view 02 header action). Keeps the full
 * multi-chat UX reachable: new chat, platform chats, pin, export,
 * clear/archive and delete.
 */
export function ChatsSheet({ bot, onClose }: ChatsSheetProps) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const { getChatsByBot, activeChatId, setActiveChat, addChat, updateChat, deleteChat, clearMessages, archiveChat } =
    useChatStore()
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  // Close an open context menu on any outside click
  useEffect(() => {
    if (!menuOpen) return
    const handler = () => setMenuOpen(null)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [menuOpen])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const q = query.trim().toLowerCase()
  const chats = getChatsByBot(bot.id).filter(
    (c) => !q || c.title.toLowerCase().includes(q) || c.lastMessage?.toLowerCase().includes(q)
  )

  const openChat = (chat: Chat) => {
    setActiveChat(chat.id)
    navigate(`/${bot.id}/chats/${chat.platform ?? chat.id}`)
    onClose()
  }

  const handleNewChat = () => {
    const newChat: Chat = {
      id: crypto.randomUUID(),
      botId: bot.id,
      title: 'New Chat',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0,
    }
    addChat(newChat)
    setActiveChat(newChat.id)
    navigate(`/${bot.id}/chats/${newChat.id}`)
    onClose()
  }

  const getChatIcon = (chat: Chat) => {
    if (chat.platform === 'telegram' || chat.platform === 'discord') {
      return <MessageCircle size={16} className="v2-chat-item__icon" />
    }
    return <MessageSquare size={16} className="v2-chat-item__icon" />
  }

  return (
    <div className="v2-sheet-backdrop" onClick={onClose}>
      <div
        className="v2-sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${bot.name} chats`}
      >
        <div className="v2-sheet__header">
          <BotAvatar color={bot.color} name={bot.name} size={32} />
          <h2>{bot.name}</h2>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            <button type="button" className="v2-btn v2-btn--secondary" onClick={handleNewChat}>
              <Plus size={15} strokeWidth={1.8} />
              New chat
            </button>
            <button type="button" className="v2-icon-btn" aria-label="Close" title="Close" onClick={onClose}>
              <X size={17} strokeWidth={1.8} />
            </button>
          </span>
        </div>

        <div className="v2-search" style={{ margin: '8px 8px 0' }}>
          <Search size={16} strokeWidth={1.8} aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            className="v2-search__input"
            placeholder="Search chats"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="v2-sheet__body">
          {chats.length === 0 ? (
            <div className="v2-sheet__empty">
              {q ? `No chats match "${query}"` : 'No chats yet — start a new one.'}
            </div>
          ) : (
            chats.map((chat) => (
              <div key={chat.id} style={{ position: 'relative' }}>
                <button
                  type="button"
                  onClick={() => openChat(chat)}
                  className={cn('v2-chat-item', activeChatId === chat.id && 'v2-chat-item--active')}
                >
                  {getChatIcon(chat)}
                  <span className="v2-chat-item__main">
                    <span className="v2-chat-item__title-row">
                      <span className="v2-chat-item__name">{chat.title}</span>
                      {chat.pinned && <Pin size={12} className="v2-chat-item__pin" />}
                      {chat.platform && (
                        <span className="v2-chat-item__platform-badge">{chat.platform}</span>
                      )}
                      <span className="v2-chat-item__time">{formatRelativeTime(chat.updatedAt)}</span>
                    </span>
                    {chat.lastMessage && (
                      <span className="v2-chat-item__preview">{chat.lastMessage}</span>
                    )}
                  </span>
                </button>

                <button
                  type="button"
                  aria-label="Chat options"
                  onClick={(e) => {
                    e.stopPropagation()
                    setMenuOpen(menuOpen === chat.id ? null : chat.id)
                  }}
                  className={cn('v2-chat-item__menu-btn', menuOpen === chat.id && 'v2-chat-item__menu-btn--open')}
                >
                  <MoreHorizontal size={14} />
                </button>

                {menuOpen === chat.id && (
                  <div className="context-menu absolute right-2 top-9 z-10 w-48">
                    <button
                      onClick={() => {
                        updateChat(chat.id, { pinned: !chat.pinned })
                        setMenuOpen(null)
                      }}
                      className="context-menu__item"
                    >
                      <Pin className="h-4 w-4" />
                      {chat.pinned ? 'Unpin' : 'Pin'}
                    </button>

                    <button
                      onClick={() => {
                        const msgs = useChatStore.getState().getMessages(chat.id)
                        const date = new Date().toISOString().slice(0, 10)
                        downloadJson(
                          {
                            chat: { id: chat.id, title: chat.title, botId: chat.botId, createdAt: chat.createdAt, updatedAt: chat.updatedAt },
                            messages: msgs,
                            exportedAt: new Date().toISOString(),
                          },
                          `chat-${slugify(chat.title)}-${date}.json`
                        )
                        setMenuOpen(null)
                      }}
                      className="context-menu__item"
                    >
                      <Download className="h-4 w-4" />
                      Export JSON
                    </button>

                    {chat.platform ? (
                      <>
                        <button
                          onClick={async () => {
                            setMenuOpen(null)
                            try {
                              await clearChatMessages(bot.id, chat.id)
                              clearMessages(chat.id)
                              toast.success('Messages cleared')
                            } catch {
                              toast.error('Failed to clear messages')
                            }
                          }}
                          className="context-menu__item"
                        >
                          <Eraser className="h-4 w-4" />
                          Clear Messages
                        </button>
                        <button
                          onClick={async () => {
                            setMenuOpen(null)
                            try {
                              await archiveChat(bot.id, chat.id)
                              toast.success('Chat archived')
                            } catch {
                              toast.error('Failed to archive chat')
                            }
                          }}
                          className="context-menu__item"
                        >
                          <Archive className="h-4 w-4" />
                          Archive Chat
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            updateChat(chat.id, { archived: true })
                            setMenuOpen(null)
                          }}
                          className="context-menu__item"
                        >
                          <Archive className="h-4 w-4" />
                          Archive
                        </button>
                        <div className="context-menu__divider" />
                        <button
                          onClick={() => {
                            deleteChat(chat.id)
                            setMenuOpen(null)
                          }}
                          className="context-menu__item context-menu__item--danger"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
