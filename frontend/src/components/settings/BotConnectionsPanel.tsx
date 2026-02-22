/**
 * BotConnectionsPanel Component
 *
 * UI for managing bot platform connections.
 * Platform list and config fields are driven dynamically by the AdapterRegistry.
 */

import { useState, useEffect } from 'react'
import { copyToClipboard } from '../../lib/utils'
import { Plus, Pencil, Trash2, X, Check, MessageCircle, Power, PowerOff, Loader2, Archive, ArchiveRestore, ChevronDown, ChevronRight, Copy, ExternalLink } from 'lucide-react'
import * as connectionsApi from '../../api/connections'
import type { Connection, ConnectionPlatform, PlatformMeta, CustomPlatformSpec } from '../../api/connections'
import { useBotStore, useChatStore } from '../../stores/bots'
import { syncBot, getPlatformChatsIncludingArchived, unarchivePlatformChat, deletePlatformChat, type PlatformChat } from '../../api/client'

interface BotConnectionsPanelProps {
  botId: string
}

export function BotConnectionsPanel({ botId }: BotConnectionsPanelProps) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [platforms, setPlatforms] = useState<Record<string, PlatformMeta>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Archived chats state
  const [showArchived, setShowArchived] = useState(false)
  const [archivedChats, setArchivedChats] = useState<PlatformChat[]>([])
  const [loadingArchived, setLoadingArchived] = useState(false)
  const [archiveActionLoading, setArchiveActionLoading] = useState<string | null>(null)

  // Custom platform spec
  const [customSpec, setCustomSpec] = useState<CustomPlatformSpec | null>(null)
  const [copiedText, setCopiedText] = useState<string | null>(null)

  // Form state
  const [isAdding, setIsAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formPlatform, setFormPlatform] = useState<ConnectionPlatform>('')
  const [formName, setFormName] = useState('')
  const [formConfig, setFormConfig] = useState<Record<string, string>>({})

  // Load connections and platforms in parallel
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [conns, plats] = await Promise.all([
          connectionsApi.getConnections(botId),
          connectionsApi.getPlatforms(),
        ])
        setConnections(conns)
        setPlatforms(plats)
        // Default to first platform
        const platformIds = Object.keys(plats)
        if (platformIds.length > 0 && !formPlatform) {
          setFormPlatform(platformIds[0])
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load connections')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [botId])

  // Listen for real-time connection status changes via WebSocket
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        connectionId: string
        botId: string
        status: string
        platform: string
        error?: string
      }
      // Only update connections for this bot
      if (detail.botId !== botId) return
      setConnections((prev) =>
        prev.map((c) =>
          c.id === detail.connectionId
            ? { ...c, status: detail.status as Connection['status'], error: detail.error || null }
            : c
        )
      )
    }
    window.addEventListener('connection-status-change', handler)
    return () => window.removeEventListener('connection-status-change', handler)
  }, [botId])

  // Load custom spec when custom platform is selected
  useEffect(() => {
    if (formPlatform === 'custom' && !customSpec) {
      connectionsApi.getCustomSpec().then(setCustomSpec).catch(() => {})
    }
  }, [formPlatform, customSpec])

  const handleCopy = (text: string) => {
    copyToClipboard(text)
    setCopiedText(text)
    setTimeout(() => setCopiedText(null), 2000)
  }

  const platformIds = Object.keys(platforms)

  const handleAdd = async () => {
    if (!formName.trim() || !formPlatform) return
    // Validate required config
    const meta = platforms[formPlatform]
    if (meta) {
      for (const key of meta.required_config) {
        if (!formConfig[key]?.trim()) return
      }
    }
    setError(null)
    try {
      const connection = await connectionsApi.createConnection(botId, {
        platform: formPlatform,
        name: formName.trim(),
        config: formConfig,
      })
      setConnections((prev) => [connection, ...prev])
      cancelForm()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create connection')
    }
  }

  const handleUpdate = async (connectionId: string) => {
    if (!formName.trim()) return
    setError(null)
    try {
      const updates: connectionsApi.ConnectionUpdate = { name: formName.trim() }
      // Only include config fields that have values
      const configUpdates: Record<string, string> = {}
      for (const [key, val] of Object.entries(formConfig)) {
        if (val.trim()) configUpdates[key] = val.trim()
      }
      if (Object.keys(configUpdates).length > 0) {
        updates.config = configUpdates
      }
      const updated = await connectionsApi.updateConnection(botId, connectionId, updates)
      setConnections((prev) => prev.map((c) => (c.id === connectionId ? updated : c)))
      cancelForm()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update connection')
    }
  }

  const handleDelete = async (connectionId: string) => {
    setError(null)
    try {
      await connectionsApi.deleteConnection(botId, connectionId)
      setConnections((prev) => prev.filter((c) => c.id !== connectionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete connection')
    }
  }

  const handleConnect = async (connectionId: string) => {
    setError(null)
    setActionLoading(connectionId)
    try {
      // Ensure bot is synced to backend before connecting
      const bot = useBotStore.getState().bots.find((b) => b.id === botId)
      if (bot && bot.systemPrompt) {
        await syncBot({
          id: bot.id,
          name: bot.name,
          description: bot.description,
          icon: bot.icon,
          color: bot.color,
          model: bot.model,
          systemPrompt: bot.systemPrompt,
          capabilities: bot.capabilities as Record<string, boolean> | undefined,
          createdAt: bot.createdAt,
          updatedAt: bot.updatedAt,
        })
      }

      const updated = await connectionsApi.connectPlatform(botId, connectionId)
      setConnections((prev) => prev.map((c) => (c.id === connectionId ? updated : c)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDisconnect = async (connectionId: string) => {
    setError(null)
    setActionLoading(connectionId)
    try {
      const updated = await connectionsApi.disconnectPlatform(botId, connectionId)
      setConnections((prev) => prev.map((c) => (c.id === connectionId ? updated : c)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to disconnect')
    } finally {
      setActionLoading(null)
    }
  }

  const startEdit = (connection: Connection) => {
    setEditingId(connection.id)
    setFormPlatform(connection.platform)
    setFormName(connection.name)
    // Reset config — don't show existing secrets
    const meta = platforms[connection.platform]
    const cfg: Record<string, string> = {}
    if (meta) {
      for (const key of meta.required_config) cfg[key] = ''
      for (const key of Object.keys(meta.optional_config)) {
        // Carry over boolean-style options from the connection
        cfg[key] = connection.strip_markdown && key === 'strip_markdown' ? 'true' : ''
      }
    }
    setFormConfig(cfg)
    setIsAdding(false)
  }

  const startAdd = () => {
    setIsAdding(true)
    setEditingId(null)
    const first = platformIds[0] || ''
    setFormPlatform(first)
    setFormName('')
    setFormConfig({})
  }

  const cancelForm = () => {
    setIsAdding(false)
    setEditingId(null)
    setFormName('')
    setFormConfig({})
  }

  const getStatusColor = (status: Connection['status']) => {
    switch (status) {
      case 'connected':
        return 'text-green-400'
      case 'connecting':
        return 'text-yellow-400'
      case 'error':
        return 'text-red-400'
      default:
        return 'text-[var(--color-text-secondary)]'
    }
  }

  const getStatusText = (status: Connection['status']) => {
    switch (status) {
      case 'connected':
        return 'Connected'
      case 'connecting':
        return 'Connecting...'
      case 'error':
        return 'Error'
      default:
        return 'Disconnected'
    }
  }

  const getPlatformDisplayName = (platform: string) => {
    return platforms[platform]?.display_name || platform
  }

  // Load archived chats when section is expanded
  const loadArchivedChats = async () => {
    setLoadingArchived(true)
    try {
      const allChats = await getPlatformChatsIncludingArchived(botId)
      const archived = allChats.filter((c) => c.archived && c.platform)
      setArchivedChats(archived)
    } catch (e) {
      console.error('Failed to load archived chats:', e)
    } finally {
      setLoadingArchived(false)
    }
  }

  const handleToggleArchived = () => {
    const newState = !showArchived
    setShowArchived(newState)
    if (newState) {
      loadArchivedChats()
    }
  }

  const handleUnarchive = async (chatId: string) => {
    setArchiveActionLoading(chatId)
    try {
      await unarchivePlatformChat(botId, chatId)
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId))
      useChatStore.getState().syncPlatformChats(botId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to unarchive chat')
    } finally {
      setArchiveActionLoading(null)
    }
  }

  const handlePermanentDelete = async (chatId: string) => {
    if (!confirm('Permanently delete this chat and all its messages? This cannot be undone.')) {
      return
    }
    setArchiveActionLoading(chatId)
    try {
      await deletePlatformChat(botId, chatId)
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete chat')
    } finally {
      setArchiveActionLoading(null)
    }
  }

  if (loading) {
    return <div className="text-sm text-[var(--color-text-secondary)]">Loading connections...</div>
  }

  // Render config fields for the selected platform
  const renderConfigFields = (platformId: string, isEdit: boolean) => {
    const meta = platforms[platformId]
    if (!meta) return null

    return (
      <>
        {/* Required config fields */}
        {meta.required_config.map((key) => (
          <div key={key} className="space-y-2">
            <label className="block text-xs text-[var(--color-text-secondary)]">
              {formatConfigLabel(key)}
              {isEdit ? ' (leave blank to keep current)' : ''}
            </label>
            <input
              type={isSecretField(key) ? 'password' : 'text'}
              value={formConfig[key] || ''}
              onChange={(e) => setFormConfig({ ...formConfig, [key]: e.target.value })}
              placeholder={isEdit ? 'Enter new value to update...' : `Enter ${key}...`}
              className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
            />
          </div>
        ))}
        {/* Optional config fields */}
        {Object.entries(meta.optional_config).map(([key, description]) => (
          <label key={key} className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={formConfig[key] === 'true'}
              onChange={(e) =>
                setFormConfig({ ...formConfig, [key]: e.target.checked ? 'true' : 'false' })
              }
              className="h-4 w-4 rounded border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] text-cachi-500 focus:ring-[var(--color-border-focus)]"
            />
            <span className="text-xs text-[var(--color-text-secondary)]">{description}</span>
          </label>
        ))}
      </>
    )
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Connection list */}
      <div className="space-y-2">
        {connections.map((connection) => (
          <div
            key={connection.id}
            className="rounded-lg border border-[var(--color-border-primary)] p-3"
          >
            {editingId === connection.id ? (
              <div className="space-y-3">
                <div className="space-y-2">
                  <label className="block text-xs text-[var(--color-text-secondary)]">Name</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="Connection name"
                    className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
                    autoFocus
                  />
                </div>
                {renderConfigFields(connection.platform, true)}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleUpdate(connection.id)}
                    className="rounded bg-cachi-600 px-2 py-1 text-xs text-white hover:bg-cachi-500"
                  >
                    <Check className="h-3 w-3" />
                  </button>
                  <button
                    onClick={cancelForm}
                    className="rounded bg-[var(--color-hover-bg)] px-2 py-1 text-xs text-[var(--color-text-primary)] hover:bg-[var(--color-active-bg)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-bg-secondary)]">
                    <MessageCircle className="h-5 w-5 text-[var(--color-text-secondary)]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-[var(--color-text-primary)]">{connection.name}</span>
                      <span className="rounded bg-[var(--color-bg-secondary)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]">
                        {getPlatformDisplayName(connection.platform)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className={getStatusColor(connection.status)}>
                        {getStatusText(connection.status)}
                      </span>
                      {connection.strip_markdown && (
                        <span className="rounded bg-[var(--color-hover-bg)] px-1.5 py-0.5 text-[var(--color-text-secondary)]">
                          Plain text
                        </span>
                      )}
                      {connection.message_count > 0 && (
                        <span className="text-[var(--color-text-secondary)]">
                          {connection.message_count} messages
                        </span>
                      )}
                    </div>
                    {connection.error && (
                      <div className="mt-1 text-xs text-red-400">{connection.error}</div>
                    )}
                    {connection.platform === 'custom' && (
                      <div className="mt-1 flex items-center gap-1">
                        <code className="text-xs text-cachi-400 truncate max-w-[280px]">
                          {window.location.origin}/api/webhooks/custom/{connection.id}
                        </code>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleCopy(`${window.location.origin}/api/webhooks/custom/${connection.id}`)
                          }}
                          className="rounded p-0.5 text-[var(--color-text-secondary)] hover:text-cachi-400"
                          title="Copy webhook URL"
                        >
                          {copiedText === `${window.location.origin}/api/webhooks/custom/${connection.id}` ? (
                            <Check className="h-3 w-3 text-green-400" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {actionLoading === connection.id ? (
                    <div className="p-2">
                      <Loader2 className="h-4 w-4 animate-spin text-[var(--color-text-secondary)]" />
                    </div>
                  ) : connection.status === 'connected' ? (
                    <button
                      onClick={() => handleDisconnect(connection.id)}
                      className="rounded p-2 text-green-400 hover:bg-[var(--color-hover-bg)] hover:text-red-400"
                      title="Disconnect"
                    >
                      <Power className="h-4 w-4" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(connection.id)}
                      className="rounded p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-green-400"
                      title="Connect"
                    >
                      <PowerOff className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={() => startEdit(connection)}
                    className="rounded p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(connection.id)}
                    className="rounded p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add form */}
      {isAdding ? (
        <div className="space-y-3 rounded-lg border border-[var(--color-border-secondary)] bg-[var(--card-bg)] p-3">
          <div className="space-y-2">
            <label className="block text-xs text-[var(--color-text-secondary)]">Platform</label>
            <select
              value={formPlatform}
              onChange={(e) => {
                setFormPlatform(e.target.value)
                setFormConfig({})
              }}
              className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
            >
              {platformIds.map((id) => (
                <option key={id} value={id}>
                  {platforms[id].display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="block text-xs text-[var(--color-text-secondary)]">Name</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder={`My ${getPlatformDisplayName(formPlatform)} Bot`}
              className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
            />
          </div>
          {renderConfigFields(formPlatform, false)}
          {/* Custom platform: API Key + API Contract docs */}
          {formPlatform === 'custom' && (
            <>
              <div className="space-y-2">
                <label className="block text-xs text-[var(--color-text-secondary)]">
                  API Key (optional)
                </label>
                <input
                  type="password"
                  value={formConfig['api_key'] || ''}
                  onChange={(e) => setFormConfig({ ...formConfig, api_key: e.target.value })}
                  placeholder="Shared secret for webhook authentication"
                  className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
                />
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  If set, CachiBot will require this key on inbound webhooks and send it on outbound requests.
                </p>
              </div>
              {customSpec && (
                <div className="space-y-3 rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-primary)]/50 p-3">
                  <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-text-primary)]">
                    <ExternalLink className="h-3.5 w-3.5" />
                    API Contract
                  </div>
                  {/* Inbound webhook */}
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-[var(--color-text-secondary)]">Inbound Webhook</div>
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      Your platform POSTs messages to this URL (available after creating the connection):
                    </p>
                    <code className="block rounded bg-[var(--color-bg-secondary)] px-2 py-1 text-xs text-cachi-400">
                      POST {window.location.origin}/api/webhooks/custom/{'<connection_id>'}
                    </code>
                    <div className="mt-1 text-xs text-[var(--color-text-secondary)]">Expected JSON body:</div>
                    <pre className="rounded bg-[var(--color-bg-secondary)] px-2 py-1.5 text-xs text-[var(--color-text-primary)] overflow-x-auto">
{JSON.stringify(customSpec.inbound.example, null, 2)}
                    </pre>
                  </div>
                  {/* Outbound endpoints */}
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-[var(--color-text-secondary)]">Outbound Endpoints</div>
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      CachiBot will POST to these endpoints on your API:
                    </p>
                    <div className="space-y-1">
                      {customSpec.outbound.map((ep) => {
                        const isActive = ep.default
                          ? formConfig[ep.capability] !== 'false'
                          : formConfig[ep.capability] === 'true'
                        return (
                          <div key={ep.capability} className="flex items-center gap-2 text-xs">
                            <span className={isActive ? 'text-green-400' : 'text-[var(--color-text-tertiary)]'}>
                              {isActive ? '\u25CF' : '\u25CB'}
                            </span>
                            <code className="text-[var(--color-text-secondary)]">{ep.endpoint}</code>
                            <span className={isActive ? 'text-green-400' : 'text-[var(--color-text-tertiary)]'}>
                              {isActive ? 'active' : 'inactive'}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={!formName.trim() || !isFormValid()}
              className="rounded bg-cachi-600 px-3 py-1 text-xs text-white hover:bg-cachi-500 disabled:opacity-50"
            >
              Add Connection
            </button>
            <button
              onClick={cancelForm}
              className="rounded bg-[var(--color-hover-bg)] px-3 py-1 text-xs text-[var(--color-text-primary)] hover:bg-[var(--color-active-bg)]"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={startAdd}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-border-secondary)] p-3 text-sm text-[var(--color-text-secondary)] hover:border-[var(--color-border-secondary)] hover:text-[var(--color-text-secondary)]"
        >
          <Plus className="h-4 w-4" />
          Add Connection
        </button>
      )}

      {connections.length === 0 && !isAdding && (
        <p className="text-center text-sm text-[var(--color-text-secondary)]">
          No connections yet. Add a connection to a messaging platform.
        </p>
      )}

      {/* Archived Chats Section */}
      {connections.length > 0 && (
        <div className="mt-6 border-t border-[var(--color-border-primary)] pt-4">
          <button
            onClick={handleToggleArchived}
            className="flex w-full items-center gap-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            {showArchived ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <Archive className="h-4 w-4" />
            <span>Archived Chats</span>
            {archivedChats.length > 0 && (
              <span className="rounded-full bg-[var(--color-hover-bg)] px-2 py-0.5 text-xs">
                {archivedChats.length}
              </span>
            )}
          </button>

          {showArchived && (
            <div className="mt-3 space-y-2">
              {loadingArchived ? (
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading archived chats...
                </div>
              ) : archivedChats.length === 0 ? (
                <p className="text-sm text-[var(--color-text-secondary)]">
                  No archived chats. Use "Archive" from a chat's menu to hide it from the sidebar.
                </p>
              ) : (
                <>
                  <p className="text-xs text-[var(--color-text-secondary)] mb-2">
                    Archived chats are hidden and won't receive new messages. Unarchive to restore them.
                  </p>
                  {archivedChats.map((chat) => (
                    <div
                      key={chat.id}
                      className="flex items-center justify-between rounded-lg border border-[var(--color-border-primary)] bg-[var(--card-bg)] p-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-hover-bg)]">
                          <MessageCircle className="h-4 w-4 text-[var(--color-text-secondary)]" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-[var(--color-text-primary)]">{chat.title}</div>
                          <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
                            <span className="capitalize">{chat.platform}</span>
                            <span>·</span>
                            <span>Archived</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {archiveActionLoading === chat.id ? (
                          <div className="p-2">
                            <Loader2 className="h-4 w-4 animate-spin text-[var(--color-text-secondary)]" />
                          </div>
                        ) : (
                          <>
                            <button
                              onClick={() => handleUnarchive(chat.id)}
                              className="rounded p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-green-400"
                              title="Unarchive (restore chat)"
                            >
                              <ArchiveRestore className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => handlePermanentDelete(chat.id)}
                              className="rounded p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-red-400"
                              title="Delete permanently"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )

  function isFormValid(): boolean {
    const meta = platforms[formPlatform]
    if (!meta) return false
    return meta.required_config.every((key) => formConfig[key]?.trim())
  }
}

/** Format a config key into a human-readable label. */
function formatConfigLabel(key: string): string {
  // token -> Token, app_token -> App Token, bot_token -> Bot Token
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Determine whether a config field should be masked as a password input. */
function isSecretField(key: string): boolean {
  const lower = key.toLowerCase()
  return lower.includes('token') || lower.includes('secret') || lower.includes('key')
}
