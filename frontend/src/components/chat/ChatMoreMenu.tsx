import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Pencil,
  History,
  Clock,
  BookOpen,
  Download,
  X,
  FolderOpen,
} from 'lucide-react'
import { toast } from 'sonner'
import { useChatStore } from '../../stores/bots'
import { usePluginsStore } from '../../stores/plugins'
import { useApprovalsStore } from '../../stores/approvals'
import { useBotAccess } from '../../hooks/useBotAccess'
import { getSchedules } from '../../api/client'
import { clearChatMessages } from '../../api/client'
import { resolveIconName } from '../common/ToolIconRenderer'
import { V2Menu, V2MenuItem, V2MenuLabel, V2MenuDivider } from '../common/V2Menu'
import { downloadText, slugify } from '../../lib/utils'
import type { Bot, Chat } from '../../types'

interface ChatMoreMenuProps {
  bot: Bot
  chat: Chat | null
  onClose: () => void
  /** Mobile top bar has no room for the Files pill — it opens the sheet from
   * this menu instead (design 10's header button is the desktop home). */
  onOpenFiles?: () => void
}

/**
 * Chat header "..." menu (design view 14): Bot settings / Runs / Routines /
 * Knowledge for this bot, plugin view pages under "From plugins", then
 * Export chat and Clear chat. Everything is gated by the caller's role —
 * items the user can't use are hidden, never greyed (view 12).
 *
 * Per view 12, Tools / Plugins / Developer live in Bot settings
 * ("What it can use" / "Advanced") — no separate entries here.
 * Knowledge deep-links to the anchored section (/:botId/settings#knowledge).
 */
export function ChatMoreMenu({ bot, chat, onClose, onOpenFiles }: ChatMoreMenuProps) {
  const navigate = useNavigate()
  const { canOperate, canEdit } = useBotAccess(bot.id)
  const { getMessages, clearMessages } = useChatStore()
  const { plugins } = usePluginsStore()
  const [routines, setRoutines] = useState<number | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)

  // Real "needs you": live pending approvals for this bot (per-tab WS state)
  const pendingApprovals = useApprovalsStore((s) => s.pending)
  const needsYou = useMemo(
    () => pendingApprovals.filter((a) => a.botId === bot.id).length,
    [pendingApprovals, bot.id]
  )

  // Real enabled-routines count (same schedules API as Workspace)
  useEffect(() => {
    let cancelled = false
    getSchedules(bot.id)
      .then((schedules) => {
        if (!cancelled) setRoutines(schedules.filter((s) => s.enabled).length)
      })
      .catch(() => { if (!cancelled) setRoutines(null) })
    return () => { cancelled = true }
  }, [bot.id])

  // Enabled view-type plugins for this bot (same source as the old icon row)
  const capabilities = (bot.capabilities ?? {}) as Record<string, boolean>
  const pluginLinks = useMemo(
    () =>
      plugins
        .filter((p) => p.type === 'view' && p.view && p.loaded && capabilities[p.capabilityKey] === true)
        .map((p) => ({ name: p.name, label: p.view!.navLabel, icon: resolveIconName(p.view!.navIcon) })),
    [plugins, capabilities]
  )

  const go = (path: string) => {
    onClose()
    navigate(path)
  }

  const handleExport = () => {
    const messages = chat ? getMessages(chat.id) : []
    const date = new Date().toISOString().slice(0, 10)
    const lines = [
      `# ${chat?.title || `Chat with ${bot.name}`}`,
      '',
      `Bot: ${bot.name} (${bot.id})`,
      chat ? `Chat: ${chat.id}` : null,
      `Exported: ${new Date().toISOString()}`,
      '',
      ...messages.map((m) => {
        const who = m.role === 'user' ? 'You' : bot.name
        return `**${who}:** ${m.content}`
      }),
    ].filter((l): l is string => l !== null)
    downloadText(lines.join('\n\n'), `chat-${slugify(bot.name)}-${date}.md`)
    toast.success('Chat exported')
    onClose()
  }

  const handleClear = async () => {
    if (!chat) return
    try {
      if (chat.platform) {
        await clearChatMessages(bot.id, chat.id)
      }
      clearMessages(chat.id)
      toast.success('Chat cleared')
    } catch {
      toast.error('Failed to clear chat')
    }
    onClose()
  }

  return (
    <V2Menu className="chat-header__menu" onClose={onClose}>
      <V2MenuLabel>{bot.name}</V2MenuLabel>

      {onOpenFiles && (
        <V2MenuItem icon={<FolderOpen size={16} strokeWidth={1.8} />} onClick={onOpenFiles}>
          Files
        </V2MenuItem>
      )}
      {canEdit && (
        <V2MenuItem icon={<Pencil size={16} strokeWidth={1.8} />} onClick={() => go(`/${bot.id}/settings`)}>
          Bot settings
        </V2MenuItem>
      )}
      {canOperate && (
        <V2MenuItem
          icon={<History size={16} strokeWidth={1.8} />}
          suffix={needsYou > 0 ? `${needsYou} needs you` : undefined}
          onClick={() => go(`/runs?bot=${bot.id}`)}
        >
          Runs
        </V2MenuItem>
      )}
      {canOperate && (
        <V2MenuItem
          icon={<Clock size={16} strokeWidth={1.8} />}
          suffix={routines && routines > 0 ? routines : undefined}
          onClick={() => go(`/${bot.id}/routines`)}
        >
          Routines
        </V2MenuItem>
      )}
      {canEdit && (
        <V2MenuItem icon={<BookOpen size={16} strokeWidth={1.8} />} onClick={() => go(`/${bot.id}/settings#knowledge`)}>
          Knowledge
        </V2MenuItem>
      )}

      {pluginLinks.length > 0 && (
        <>
          <V2MenuDivider />
          <V2MenuLabel>From plugins</V2MenuLabel>
          {pluginLinks.map((p) => (
            <V2MenuItem
              key={p.name}
              icon={<p.icon size={16} strokeWidth={1.8} />}
              onClick={() => go(`/${bot.id}/plugins/${p.name}`)}
            >
              {p.label}
            </V2MenuItem>
          ))}
        </>
      )}

      <V2MenuDivider />
      <V2MenuItem icon={<Download size={16} strokeWidth={1.8} />} onClick={handleExport}>
        Export chat
      </V2MenuItem>
      {confirmClear ? (
        <V2MenuItem icon={<X size={16} strokeWidth={1.8} />} danger onClick={handleClear}>
          {chat?.platform ? 'Clear messages? This cannot be undone' : 'Clear messages in this chat?'}
        </V2MenuItem>
      ) : (
        <V2MenuItem icon={<X size={16} strokeWidth={1.8} />} danger onClick={() => setConfirmClear(true)}>
          Clear chat
        </V2MenuItem>
      )}
    </V2Menu>
  )
}
