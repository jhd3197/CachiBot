import { useState } from 'react'
import {
  Plug,
  Plus,
  Settings,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  ExternalLink,
  Copy,
  Check,
  MessageSquare,
  Bot,
  ChevronRight,
} from 'lucide-react'
import { useConnectionStore, PLATFORMS } from '../../stores/connections'
import { useBotStore } from '../../stores/bots'
import { cn } from '../../lib/utils'
import type { Connection, PlatformInfo } from '../../types'

export function ConnectionsView() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformInfo | null>(null)
  const [editingConnection, setEditingConnection] = useState<Connection | null>(null)

  const { connections, deleteConnection, updateConnection } = useConnectionStore()
  const { bots } = useBotStore()

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this connection?')) {
      deleteConnection(id)
    }
  }

  const handleToggle = (connection: Connection) => {
    const newStatus = connection.status === 'connected' ? 'disconnected' : 'connecting'
    updateConnection(connection.id, { status: newStatus })

    if (newStatus === 'connecting') {
      // Simulate connection
      setTimeout(() => {
        updateConnection(connection.id, { status: 'connected' })
      }, 2000)
    }
  }

  return (
    <div className="flex h-full flex-col bg-zinc-100 dark:bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Connections</h1>
          <p className="text-sm text-zinc-500">
            Connect your bots to messaging platforms
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500"
        >
          <Plus className="h-4 w-4" />
          Add Connection
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Active Connections */}
          {connections.length > 0 && (
            <section>
              <h2 className="mb-4 text-lg font-semibold text-zinc-200">
                Your Connections
              </h2>
              <div className="space-y-3">
                {connections.map((connection) => (
                  <ConnectionCard
                    key={connection.id}
                    connection={connection}
                    bots={bots}
                    onToggle={handleToggle}
                    onEdit={setEditingConnection}
                    onDelete={handleDelete}
                    onAssignBot={(botId) =>
                      updateConnection(connection.id, { botId })
                    }
                  />
                ))}
              </div>
            </section>
          )}

          {/* Available Platforms */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-zinc-200">
              Available Platforms
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {PLATFORMS.map((platform) => {
                const connectedCount = connections.filter(
                  (c) => c.platform === platform.id && c.status === 'connected'
                ).length

                return (
                  <PlatformCard
                    key={platform.id}
                    platform={platform}
                    connectedCount={connectedCount}
                    onSelect={() => setSelectedPlatform(platform)}
                  />
                )
              })}
            </div>
          </section>

          {/* Info Box */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
            <h3 className="font-semibold text-zinc-200">
              Free Libraries for Messaging Platforms
            </h3>
            <p className="mt-2 text-sm text-zinc-400">
              All platforms listed here can be connected using free, open-source
              libraries. No paid API access required.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <InfoItem
                name="WhatsApp"
                library="@whiskeysockets/baileys"
                url="https://github.com/WhiskeySockets/Baileys"
              />
              <InfoItem
                name="Telegram"
                library="telegraf"
                url="https://telegraf.js.org"
              />
              <InfoItem
                name="Discord"
                library="discord.js"
                url="https://discord.js.org"
              />
              <InfoItem
                name="Slack"
                library="@slack/bolt"
                url="https://slack.dev/bolt-js"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Add Connection Modal */}
      {showAddModal && (
        <AddConnectionModal
          onClose={() => setShowAddModal(false)}
          onSelectPlatform={(platform) => {
            setShowAddModal(false)
            setSelectedPlatform(platform)
          }}
        />
      )}

      {/* Platform Setup Modal */}
      {selectedPlatform && (
        <PlatformSetupModal
          platform={selectedPlatform}
          onClose={() => setSelectedPlatform(null)}
        />
      )}

      {/* Edit Connection Modal */}
      {editingConnection && (
        <EditConnectionModal
          connection={editingConnection}
          bots={bots}
          onClose={() => setEditingConnection(null)}
          onSave={(updates) => {
            updateConnection(editingConnection.id, updates)
            setEditingConnection(null)
          }}
        />
      )}
    </div>
  )
}

// =============================================================================
// CONNECTION CARD
// =============================================================================

interface ConnectionCardProps {
  connection: Connection
  bots: { id: string; name: string; icon: string; color: string }[]
  onToggle: (connection: Connection) => void
  onEdit: (connection: Connection) => void
  onDelete: (id: string) => void
  onAssignBot: (botId: string | undefined) => void
}

function ConnectionCard({
  connection,
  bots,
  onToggle,
  onEdit,
  onDelete,
  onAssignBot,
}: ConnectionCardProps) {
  const platform = PLATFORMS.find((p) => p.id === connection.platform)

  const statusStyles = {
    connected: 'bg-green-500/20 text-green-400 border-green-500/30',
    connecting: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    disconnected: 'bg-zinc-800 text-zinc-400 border-zinc-700',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  const StatusIcon = {
    connected: CheckCircle2,
    connecting: Loader2,
    disconnected: AlertCircle,
    error: XCircle,
  }[connection.status]

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <div className="flex items-start gap-4">
        <div
          className={cn(
            'flex h-12 w-12 items-center justify-center rounded-xl',
            connection.status === 'connected'
              ? 'bg-green-500/20 text-green-400'
              : connection.status === 'error'
              ? 'bg-red-500/20 text-red-400'
              : 'bg-zinc-800 text-zinc-400'
          )}
        >
          <PlatformIcon platform={connection.platform} />
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-zinc-100">{connection.name}</h3>
            <span
              className={cn(
                'flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
                statusStyles[connection.status]
              )}
            >
              <StatusIcon
                className={cn(
                  'h-3 w-3',
                  connection.status === 'connecting' && 'animate-spin'
                )}
              />
              {connection.status}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-zinc-500">{platform?.name}</p>

          <div className="mt-3 flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-zinc-600" />
              <select
                value={connection.botId || ''}
                onChange={(e) =>
                  onAssignBot(e.target.value || undefined)
                }
                className="rounded bg-zinc-800 px-2 py-1 text-sm text-zinc-300 outline-none"
              >
                <option value="">No bot assigned</option>
                {bots.map((bot) => (
                  <option key={bot.id} value={bot.id}>
                    {bot.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-1 text-xs text-zinc-500">
              <MessageSquare className="h-3 w-3" />
              {connection.messageCount} messages
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle(connection)}
            className={cn(
              'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              connection.status === 'connected'
                ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30'
                : connection.status === 'connecting'
                ? 'bg-zinc-800 text-zinc-500'
                : 'bg-cachi-600 text-white hover:bg-cachi-500'
            )}
            disabled={connection.status === 'connecting'}
          >
            {connection.status === 'connected'
              ? 'Disconnect'
              : connection.status === 'connecting'
              ? 'Connecting...'
              : 'Connect'}
          </button>
          <button
            onClick={() => onEdit(connection)}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <Settings className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(connection.id)}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-red-400"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {connection.error && (
        <div className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {connection.error}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// PLATFORM CARD
// =============================================================================

interface PlatformCardProps {
  platform: PlatformInfo
  connectedCount: number
  onSelect: () => void
}

function PlatformCard({ platform, connectedCount, onSelect }: PlatformCardProps) {
  return (
    <button
      onClick={onSelect}
      className="group flex items-center gap-4 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 text-left transition-all hover:border-zinc-700 hover:bg-zinc-900"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-800 text-zinc-400 transition-colors group-hover:bg-cachi-600/20 group-hover:text-cachi-400">
        <PlatformIcon platform={platform.id} />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-zinc-100">{platform.name}</h3>
          {platform.free && (
            <span className="rounded bg-green-500/20 px-1.5 py-0.5 text-xs font-medium text-green-400">
              Free
            </span>
          )}
        </div>
        <p className="mt-0.5 text-sm text-zinc-500">{platform.description}</p>
        {connectedCount > 0 && (
          <p className="mt-1 text-xs text-cachi-400">
            {connectedCount} active connection{connectedCount > 1 ? 's' : ''}
          </p>
        )}
      </div>
      <ChevronRight className="h-5 w-5 text-zinc-600 transition-transform group-hover:translate-x-1 group-hover:text-zinc-400" />
    </button>
  )
}

// =============================================================================
// ADD CONNECTION MODAL
// =============================================================================

function AddConnectionModal({
  onClose,
  onSelectPlatform,
}: {
  onClose: () => void
  onSelectPlatform: (platform: PlatformInfo) => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-bold text-zinc-100">Add Connection</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        <p className="mb-6 text-zinc-400">
          Choose a platform to connect your bots to:
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          {PLATFORMS.map((platform) => (
            <button
              key={platform.id}
              onClick={() => onSelectPlatform(platform)}
              className="flex items-center gap-3 rounded-xl border border-zinc-700 bg-zinc-800/50 p-4 text-left transition-all hover:border-cachi-500 hover:bg-zinc-800"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-700 text-zinc-300">
                <PlatformIcon platform={platform.id} />
              </div>
              <div>
                <h3 className="font-medium text-zinc-100">{platform.name}</h3>
                <p className="text-xs text-zinc-500">{platform.library}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// PLATFORM SETUP MODAL
// =============================================================================

function PlatformSetupModal({
  platform,
  onClose,
}: {
  platform: PlatformInfo
  onClose: () => void
}) {
  const [name, setName] = useState(`My ${platform.name}`)
  const [config, setConfig] = useState<Record<string, string>>({})
  const [copied, setCopied] = useState<string | null>(null)
  const { addConnection } = useConnectionStore()

  const handleCreate = () => {
    const newConnection: Connection = {
      id: crypto.randomUUID(),
      botId: '', // Global connections (legacy) - no specific bot assigned
      platform: platform.id,
      name,
      status: 'disconnected',
      config,
      messageCount: 0,
      createdAt: new Date().toISOString(),
    }
    addConnection(newConnection)
    onClose()
  }

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-cachi-600/20 text-cachi-400">
            <PlatformIcon platform={platform.id} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-zinc-100">
              Connect {platform.name}
            </h2>
            <p className="text-sm text-zinc-500">{platform.description}</p>
          </div>
        </div>

        {/* Setup Steps */}
        <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-800/30 p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Setup Steps
          </h3>
          <ol className="space-y-2">
            {platform.setupSteps.map((step, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-cachi-600/20 text-xs font-bold text-cachi-400">
                  {i + 1}
                </span>
                <span className="text-zinc-300">{step}</span>
              </li>
            ))}
          </ol>

          <div className="mt-4 flex items-center gap-2">
            <span className="text-sm text-zinc-500">Install command:</span>
            <code className="flex-1 rounded bg-zinc-900 px-2 py-1 font-mono text-xs text-zinc-300">
              npm install {platform.library}
            </code>
            <button
              onClick={() =>
                copyToClipboard(`npm install ${platform.library}`, 'install')
              }
              className="rounded p-1 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            >
              {copied === 'install' ? (
                <Check className="h-4 w-4 text-green-400" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* Connection Name */}
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium text-zinc-300">
            Connection Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-cachi-500"
          />
        </div>

        {/* Platform-specific config fields */}
        {platform.id === 'telegram' && (
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-zinc-300">
              Bot Token
            </label>
            <input
              type="password"
              placeholder="123456:ABC-DEF1234ghIkl..."
              value={config.token || ''}
              onChange={(e) => setConfig({ ...config, token: e.target.value })}
              className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
            />
          </div>
        )}

        {platform.id === 'discord' && (
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-zinc-300">
              Bot Token
            </label>
            <input
              type="password"
              placeholder="MTIzNDU2Nzg5MDEyMzQ..."
              value={config.token || ''}
              onChange={(e) => setConfig({ ...config, token: e.target.value })}
              className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
            />
          </div>
        )}

        {platform.id === 'slack' && (
          <>
            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium text-zinc-300">
                Bot Token
              </label>
              <input
                type="password"
                placeholder="xoxb-..."
                value={config.token || ''}
                onChange={(e) => setConfig({ ...config, token: e.target.value })}
                className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
              />
            </div>
            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium text-zinc-300">
                App Token
              </label>
              <input
                type="password"
                placeholder="xapp-..."
                value={config.appToken || ''}
                onChange={(e) =>
                  setConfig({ ...config, appToken: e.target.value })
                }
                className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
              />
            </div>
          </>
        )}

        {/* Documentation link */}
        <a
          href={platform.docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mb-6 flex items-center gap-2 text-sm text-cachi-400 hover:text-cachi-300"
        >
          View Documentation
          <ExternalLink className="h-3 w-3" />
        </a>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            className="rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500"
          >
            Create Connection
          </button>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// EDIT CONNECTION MODAL
// =============================================================================

function EditConnectionModal({
  connection,
  bots,
  onClose,
  onSave,
}: {
  connection: Connection
  bots: { id: string; name: string }[]
  onClose: () => void
  onSave: (updates: Partial<Connection>) => void
}) {
  const [name, setName] = useState(connection.name)
  const [botId, setBotId] = useState(connection.botId || '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
        <h2 className="mb-6 text-xl font-bold text-zinc-100">Edit Connection</h2>

        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-cachi-500"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">
              Assigned Bot
            </label>
            <select
              value={botId}
              onChange={(e) => setBotId(e.target.value)}
              className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-cachi-500"
            >
              <option value="">No bot assigned</option>
              {bots.map((bot) => (
                <option key={bot.id} value={bot.id}>
                  {bot.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave({ name, botId: botId || undefined })}
            className="rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// HELPERS
// =============================================================================

function InfoItem({
  name,
  library,
  url,
}: {
  name: string
  library: string
  url: string
}) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2 transition-colors hover:border-zinc-600"
    >
      <div>
        <span className="text-sm font-medium text-zinc-200">{name}</span>
        <p className="font-mono text-xs text-zinc-500">{library}</p>
      </div>
      <ExternalLink className="h-4 w-4 text-zinc-500" />
    </a>
  )
}

function PlatformIcon({ platform }: { platform: string }) {
  const icons: Record<string, React.ReactNode> = {
    whatsapp: (
      <MessageSquare className="h-5 w-5" />
    ),
    telegram: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.03-1.99 1.27-5.62 3.72-.53.36-1.01.54-1.44.53-.47-.01-1.38-.27-2.06-.49-.83-.27-1.49-.42-1.43-.89.03-.24.37-.49 1.02-.74 3.99-1.74 6.65-2.89 7.99-3.45 3.8-1.6 4.59-1.88 5.1-1.89.11 0 .37.03.54.17.14.12.18.28.2.45-.01.06.01.24 0 .38z" />
      </svg>
    ),
    discord: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026c.462-.62.874-1.275 1.226-1.963.021-.04.001-.088-.041-.104a13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z" />
      </svg>
    ),
    slack: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
      </svg>
    ),
    messenger: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.373 0 0 4.974 0 11.111c0 3.498 1.744 6.614 4.469 8.654V24l4.088-2.242c1.092.3 2.246.464 3.443.464 6.627 0 12-4.975 12-11.111S18.627 0 12 0zm1.191 14.963l-3.055-3.26-5.963 3.26L10.732 8l3.131 3.259L19.752 8l-6.561 6.963z" />
      </svg>
    ),
    matrix: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M.632.55v22.9H2.28V24H0V0h2.28v.55zm7.043 7.26v1.157h.033c.309-.443.683-.784 1.117-1.024.433-.245.936-.365 1.5-.365.54 0 1.033.107 1.481.314.448.208.785.582 1.02 1.108.254-.374.6-.706 1.034-.992.434-.287.95-.43 1.546-.43.453 0 .872.056 1.26.167.388.11.716.286.993.53.276.245.489.559.646.951.152.392.23.863.23 1.417v5.728h-2.349V11.52c0-.286-.01-.559-.032-.812a1.755 1.755 0 0 0-.18-.66 1.106 1.106 0 0 0-.438-.448c-.194-.11-.457-.166-.785-.166-.332 0-.6.064-.803.189a1.38 1.38 0 0 0-.48.499 1.946 1.946 0 0 0-.231.696 5.56 5.56 0 0 0-.06.785v4.768h-2.35v-4.8c0-.254-.004-.503-.018-.752a2.074 2.074 0 0 0-.143-.688 1.052 1.052 0 0 0-.415-.503c-.194-.125-.476-.19-.854-.19-.111 0-.259.024-.439.074-.18.051-.36.143-.53.282-.171.138-.319.33-.439.576-.12.245-.18.567-.18.958v5.043H4.833V7.81zm15.693 15.64V.55H21.72V0H24v24h-2.28v-.55z" />
      </svg>
    ),
    email: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
      </svg>
    ),
  }

  return icons[platform] || <Plug className="h-5 w-5" />
}
