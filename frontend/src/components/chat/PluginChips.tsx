import { useEffect } from 'react'
import { useBotStore } from '../../stores/bots'
import { usePluginsStore } from '../../stores/plugins'
import { resolveIconName } from '../common/ToolIconRenderer'
import { cn } from '../../lib/utils'

interface PluginChipsProps {
  /** When true, the chat already has messages — hide plugins that weren't
   *  active at chat start unless they declare allowLateActivation. */
  inChat?: boolean
}

/**
 * Shows only external (user-installed) plugins as toggleable chips.
 * Internal capabilities (Git, Shell, Web, etc.) are managed in bot settings.
 *
 * Behavior based on context:
 *  - Hero mode (inChat=false):  All loaded plugins shown, fully toggleable.
 *  - Active chat (inChat=true): Only show plugins that are already active
 *    OR have allowLateActivation=true. Inactive plugins without late
 *    activation are hidden to prevent mid-conversation opt-in.
 */
export function PluginChips({ inChat = false }: PluginChipsProps) {
  const { getActiveBot, updateBot } = useBotStore()
  const { plugins, fetchPlugins, togglePlugin } = usePluginsStore()
  const activeBot = getActiveBot()

  useEffect(() => {
    fetchPlugins()
  }, [fetchPlugins])

  const loaded = plugins.filter((p) => p.loaded)

  if (!activeBot || loaded.length === 0) return null

  const capabilities = (activeBot.capabilities ?? {}) as Record<string, boolean>

  // Filter visible plugins based on context
  const visible = inChat
    ? loaded.filter((p) => {
        const isActive = capabilities[p.capabilityKey] === true
        // In-chat: show if already active OR plugin opts into late activation
        return isActive || p.allowLateActivation
      })
    : loaded

  if (visible.length === 0) return null

  const handleToggle = async (plugin: (typeof loaded)[0]) => {
    const enabling = capabilities[plugin.capabilityKey] !== true
    const result = await togglePlugin(plugin.name, enabling)
    if (result) {
      const newCaps = { ...capabilities, [result.capabilityKey]: result.enabled }
      updateBot(activeBot.id, { capabilities: newCaps as typeof activeBot.capabilities })
    }
  }

  return (
    <div className="plugin-chips">
      {visible.map((plugin) => {
        const isActive = capabilities[plugin.capabilityKey] === true
        const Icon = resolveIconName(plugin.icon)
        return (
          <button
            key={plugin.name}
            type="button"
            onClick={() => handleToggle(plugin)}
            className={cn('plugin-chip', isActive && 'plugin-chip--active')}
            style={
              isActive && plugin.color
                ? {
                    backgroundColor: plugin.color + '18',
                    borderColor: plugin.color + '50',
                    color: plugin.color,
                    boxShadow: `0 0 8px ${plugin.color}20`,
                  }
                : undefined
            }
          >
            <Icon className="plugin-chip__icon" />
            <span className="plugin-chip__label">{plugin.displayName}</span>
          </button>
        )
      })}
    </div>
  )
}
