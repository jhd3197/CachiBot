/**
 * Hook to determine the current user's access level to a bot.
 *
 * Returns access flags that components can use to conditionally
 * show/hide UI elements based on permissions.
 */

import { useMemo } from 'react'
import { useAuthStore } from '../stores/auth'
import { useBotStore } from '../stores/bots'

interface BotAccess {
  /** User owns this bot */
  isOwner: boolean
  /** The effective access level ('owner' | 'admin' | BotAccessLevel | null) */
  accessLevel: string | null
  /** Can view bot info, chats, logs (viewer+) */
  canView: boolean
  /** Can interact: send messages, run scripts (operator+) */
  canOperate: boolean
  /** Can edit bot config, settings, connections (editor+) */
  canEdit: boolean
}

const LEVEL_RANK: Record<string, number> = {
  viewer: 1,
  operator: 2,
  editor: 3,
  owner: 4,
  admin: 4,
}

export function useBotAccess(botId: string | null): BotAccess {
  const { user } = useAuthStore()
  const { bots } = useBotStore()

  return useMemo(() => {
    if (!botId || !user) {
      return { isOwner: false, accessLevel: null, canView: false, canOperate: false, canEdit: false }
    }

    // Admin has full access
    if (user.role === 'admin') {
      return { isOwner: false, accessLevel: 'admin', canView: true, canOperate: true, canEdit: true }
    }

    // Find the bot in the store — the list_bots endpoint now includes access_level
    const bot = bots.find((b) => b.id === botId)
    const level = bot ? (bot as unknown as Record<string, unknown>).access_level as string | undefined : undefined

    if (!level) {
      return { isOwner: false, accessLevel: null, canView: false, canOperate: false, canEdit: false }
    }

    const isOwner = level === 'owner'
    const rank = LEVEL_RANK[level] ?? 0

    return {
      isOwner,
      accessLevel: level,
      canView: rank >= 1,
      canOperate: rank >= 2,
      canEdit: rank >= 3,
    }
  }, [botId, user, bots])
}
