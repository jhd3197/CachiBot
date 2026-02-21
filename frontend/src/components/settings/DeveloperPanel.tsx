/**
 * DeveloperPanel Component
 *
 * Per-bot developer settings: API keys, API documentation, and webhooks.
 */

import { useState, useEffect } from 'react'
import {
  Plus,
  Trash2,
  Copy,
  Check,
  Key,
  Send,
  Loader2,
  AlertTriangle,
  X,
  Eye,
  EyeOff,
} from 'lucide-react'
import { toast } from 'sonner'
import * as devApi from '../../api/developer'
import { useBotStore } from '../../stores/bots'
import type { BotApiKey, BotApiKeyCreated, BotWebhook, WebhookEvent } from '../../types'

const ALL_EVENTS: { value: WebhookEvent; label: string }[] = [
  { value: 'message.created', label: 'Message Created' },
  { value: 'task.completed', label: 'Task Completed' },
  { value: 'work.completed', label: 'Work Completed' },
  { value: 'work.failed', label: 'Work Failed' },
  { value: 'schedule.triggered', label: 'Schedule Triggered' },
  { value: 'api.request', label: 'API Request' },
]

interface DeveloperPanelProps {
  botId: string
}

type DeveloperTab = 'api-keys' | 'api-docs' | 'webhooks'

export function DeveloperPanel({ botId }: DeveloperPanelProps) {
  const [activeTab, setActiveTab] = useState<DeveloperTab>('api-keys')

  return (
    <div className="space-y-6">
      {/* Tab navigation */}
      <div className="flex gap-1 rounded-lg bg-[var(--color-bg-secondary)] p-1">
        {([
          { id: 'api-keys', label: 'API Keys' },
          { id: 'api-docs', label: 'API Docs' },
          { id: 'webhooks', label: 'Webhooks' },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] shadow-sm'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'api-keys' && <ApiKeysPanel botId={botId} />}
      {activeTab === 'api-docs' && <ApiDocsPanel botId={botId} />}
      {activeTab === 'webhooks' && <WebhooksPanel botId={botId} />}
    </div>
  )
}

// =============================================================================
// API KEYS PANEL
// =============================================================================

function ApiKeysPanel({ botId }: { botId: string }) {
  const [keys, setKeys] = useState<BotApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newKey, setNewKey] = useState<BotApiKeyCreated | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const loadKeys = async () => {
    try {
      const data = await devApi.getApiKeys(botId)
      setKeys(data)
    } catch {
      toast.error('Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadKeys()
  }, [botId])

  const handleRevoke = async (keyId: string) => {
    try {
      await devApi.revokeApiKey(botId, keyId)
      toast.success('API key revoked')
      loadKeys()
    } catch {
      toast.error('Failed to revoke key')
    }
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* New key display */}
      {newKey && (
        <div className="rounded-lg border border-cachi-500/30 bg-cachi-500/5 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-cachi-600">
            <Key className="h-4 w-4" />
            API Key Created - Copy it now, it won't be shown again
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono">
              {newKey.key}
            </code>
            <button
              onClick={() => { copyToClipboard(newKey.key, 'new-key'); toast.success('Copied!') }}
              className="btn btn--secondary"
            >
              {copiedId === 'new-key' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-2 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--color-text-secondary)]">
          API keys allow external tools to access this bot programmatically.
        </p>
        <button onClick={() => setShowCreate(true)} className="btn btn--primary">
          <Plus className="h-4 w-4" />
          Create Key
        </button>
      </div>

      {/* Keys table */}
      {keys.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center">
          <Key className="mx-auto mb-2 h-8 w-8 text-[var(--color-text-secondary)]" />
          <p className="text-sm text-[var(--color-text-secondary)]">No API keys yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((key) => (
            <div
              key={key.id}
              className={`flex items-center gap-4 rounded-lg border border-[var(--color-border)] p-3 ${
                key.is_revoked ? 'opacity-50' : ''
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {key.name}
                  </span>
                  {key.is_revoked && (
                    <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-xs text-red-500">
                      Revoked
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-[var(--color-text-secondary)]">
                  <code>{key.key_prefix}...</code>
                  <span>Used {key.usage_count} times</span>
                  {key.last_used_at && (
                    <span>Last used {new Date(key.last_used_at).toLocaleDateString()}</span>
                  )}
                  {key.expires_at && (
                    <span>Expires {new Date(key.expires_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
              {!key.is_revoked && (
                <button
                  onClick={() => handleRevoke(key.id)}
                  className="btn btn--danger-outline btn--sm"
                  title="Revoke"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <CreateApiKeyDialog
          botId={botId}
          onCreated={(key) => {
            setNewKey(key)
            setShowCreate(false)
            loadKeys()
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}

function CreateApiKeyDialog({
  botId,
  onCreated,
  onClose,
}: {
  botId: string
  onCreated: (key: BotApiKeyCreated) => void
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>()
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) return
    setCreating(true)
    try {
      const key = await devApi.createApiKey(botId, name.trim(), expiresInDays)
      onCreated(key)
    } catch {
      toast.error('Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="dialog__backdrop" onClick={onClose}>
      <div className="dialog__panel dialog__panel--sm" onClick={(e) => e.stopPropagation()}>
        <div className="dialog__header">
          <h2 style={{ fontSize: 'var(--text-base)', fontWeight: 600 }}>Create API Key</h2>
          <button onClick={onClose} className="nav-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="dialog__body-base space-y-4">
          <div>
            <label className="settings-label">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Cursor, VS Code, My App"
              className="settings-input"
              autoFocus
            />
          </div>
          <div>
            <label className="settings-label">Expires in (days, optional)</label>
            <input
              type="number"
              value={expiresInDays ?? ''}
              onChange={(e) => setExpiresInDays(e.target.value ? parseInt(e.target.value) : undefined)}
              placeholder="Never"
              className="settings-input"
              min={1}
            />
          </div>
        </div>
        <div className="dialog__footer">
          <button onClick={onClose} className="btn btn--secondary">Cancel</button>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || creating}
            className="btn btn--primary"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Key className="h-4 w-4" />}
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// API DOCS PANEL
// =============================================================================

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ApiDocsPanel({ botId }: { botId: string }) {
  const { getActiveBot } = useBotStore()
  const bot = getActiveBot()
  const baseUrl = `${window.location.origin}/v1`
  const modelName = bot?.models?.default || bot?.model || 'unknown'
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    toast.success('Copied!')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const curlExample = `curl ${baseUrl}/chat/completions \\
  -H "Authorization: Bearer cb-YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${modelName}",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'`

  const pythonExample = `from openai import OpenAI

client = OpenAI(
    api_key="cb-YOUR_API_KEY",
    base_url="${baseUrl}"
)

response = client.chat.completions.create(
    model="${modelName}",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)`

  const tsExample = `import OpenAI from 'openai';

const client = new OpenAI({
  apiKey: 'cb-YOUR_API_KEY',
  baseURL: '${baseUrl}',
});

const response = await client.chat.completions.create({
  model: '${modelName}',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message.content);`

  const cursorConfig = `{
  "models": [{
    "title": "${bot?.name || 'CachiBot'}",
    "provider": "openai",
    "model": "${modelName}",
    "apiKey": "cb-YOUR_API_KEY",
    "baseUrl": "${baseUrl}"
  }]
}`

  const examples = [
    { id: 'curl', label: 'cURL', code: curlExample },
    { id: 'python', label: 'Python (OpenAI SDK)', code: pythonExample },
    { id: 'typescript', label: 'TypeScript (OpenAI SDK)', code: tsExample },
    { id: 'cursor', label: 'Cursor / VS Code', code: cursorConfig },
  ]

  return (
    <div className="space-y-6">
      {/* Base URL */}
      <div>
        <label className="settings-label">Base URL</label>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--color-text-primary)]">
            {baseUrl}
          </code>
          <button
            onClick={() => copyToClipboard(baseUrl, 'base-url')}
            className="btn btn--secondary btn--sm"
          >
            {copiedId === 'base-url' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Endpoints */}
      <div>
        <label className="settings-label">Endpoints</label>
        <div className="space-y-1.5 text-sm">
          <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
            <span className="rounded bg-cachi-500/10 px-1.5 py-0.5 text-xs font-mono text-cachi-600">POST</span>
            <code>/v1/chat/completions</code>
          </div>
          <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
            <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs font-mono text-blue-600">GET</span>
            <code>/v1/models</code>
          </div>
        </div>
      </div>

      {/* Model */}
      <div>
        <label className="settings-label">Model</label>
        <code className="block rounded bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--color-text-primary)]">
          {modelName}
        </code>
      </div>

      {/* Code Examples */}
      <div className="space-y-4">
        <label className="settings-label">Code Examples</label>
        {examples.map((ex) => (
          <div key={ex.id} className="rounded-lg border border-[var(--color-border)] overflow-hidden">
            <div className="flex items-center justify-between bg-[var(--color-bg-secondary)] px-3 py-1.5">
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{ex.label}</span>
              <button
                onClick={() => copyToClipboard(ex.code, ex.id)}
                className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              >
                {copiedId === ex.id ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                Copy
              </button>
            </div>
            <pre className="overflow-x-auto p-3 text-xs leading-relaxed font-mono text-[var(--color-text-primary)]">
              {ex.code}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// WEBHOOKS PANEL
// =============================================================================

function WebhooksPanel({ botId }: { botId: string }) {
  const [webhooks, setWebhooks] = useState<BotWebhook[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const loadWebhooks = async () => {
    try {
      const data = await devApi.getWebhooks(botId)
      setWebhooks(data)
    } catch {
      toast.error('Failed to load webhooks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWebhooks()
  }, [botId])

  const handleDelete = async (webhookId: string) => {
    try {
      await devApi.deleteWebhook(botId, webhookId)
      toast.success('Webhook deleted')
      loadWebhooks()
    } catch {
      toast.error('Failed to delete webhook')
    }
  }

  const handleToggle = async (webhook: BotWebhook) => {
    try {
      await devApi.updateWebhook(botId, webhook.id, { is_active: !webhook.is_active })
      loadWebhooks()
    } catch {
      toast.error('Failed to update webhook')
    }
  }

  const handleTest = async (webhookId: string) => {
    setTestingId(webhookId)
    try {
      const result = await devApi.testWebhook(botId, webhookId)
      if (result.status === 'delivered') {
        toast.success(`Test delivered (HTTP ${result.response_status})`)
      } else {
        toast.error(`Test failed: ${result.error}`)
      }
    } catch {
      toast.error('Failed to send test')
    } finally {
      setTestingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Webhooks send event notifications to external URLs when things happen in this bot.
        </p>
        <button onClick={() => setShowCreate(true)} className="btn btn--primary">
          <Plus className="h-4 w-4" />
          Add Webhook
        </button>
      </div>

      {/* Webhooks list */}
      {webhooks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center">
          <Send className="mx-auto mb-2 h-8 w-8 text-[var(--color-text-secondary)]" />
          <p className="text-sm text-[var(--color-text-secondary)]">No webhooks configured</p>
        </div>
      ) : (
        <div className="space-y-2">
          {webhooks.map((wh) => (
            <div
              key={wh.id}
              className={`rounded-lg border border-[var(--color-border)] p-3 ${
                !wh.is_active ? 'opacity-50' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[var(--color-text-primary)]">
                      {wh.name}
                    </span>
                    <button
                      onClick={() => handleToggle(wh)}
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        wh.is_active
                          ? 'bg-green-500/10 text-green-600'
                          : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]'
                      }`}
                    >
                      {wh.is_active ? 'Active' : 'Inactive'}
                    </button>
                    {wh.failure_count > 0 && (
                      <span className="flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-xs text-red-500">
                        <AlertTriangle className="h-3 w-3" />
                        {wh.failure_count} failures
                      </span>
                    )}
                  </div>
                  <code className="mt-0.5 block text-xs text-[var(--color-text-secondary)] truncate">
                    {wh.url}
                  </code>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {wh.events.map((event) => (
                      <span
                        key={event}
                        className="rounded bg-[var(--color-bg-secondary)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]"
                      >
                        {event}
                      </span>
                    ))}
                  </div>
                  {wh.last_triggered_at && (
                    <span className="mt-1 block text-xs text-[var(--color-text-secondary)]">
                      Last triggered {new Date(wh.last_triggered_at).toLocaleString()}
                    </span>
                  )}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => handleTest(wh.id)}
                    disabled={testingId === wh.id}
                    className="btn btn--secondary btn--sm"
                    title="Send test"
                  >
                    {testingId === wh.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Send className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(wh.id)}
                    className="btn btn--danger-outline btn--sm"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <CreateWebhookDialog
          botId={botId}
          onCreated={() => {
            setShowCreate(false)
            loadWebhooks()
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}

function CreateWebhookDialog({
  botId,
  onCreated,
  onClose,
}: {
  botId: string
  onCreated: () => void
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const [selectedEvents, setSelectedEvents] = useState<WebhookEvent[]>([])
  const [creating, setCreating] = useState(false)

  const toggleEvent = (event: WebhookEvent) => {
    setSelectedEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    )
  }

  const handleCreate = async () => {
    if (!name.trim() || !url.trim() || selectedEvents.length === 0) return
    setCreating(true)
    try {
      await devApi.createWebhook(botId, {
        name: name.trim(),
        url: url.trim(),
        events: selectedEvents,
        secret: secret.trim() || undefined,
      })
      toast.success('Webhook created')
      onCreated()
    } catch {
      toast.error('Failed to create webhook')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="dialog__backdrop" onClick={onClose}>
      <div className="dialog__panel dialog__panel--sm" onClick={(e) => e.stopPropagation()}>
        <div className="dialog__header">
          <h2 style={{ fontSize: 'var(--text-base)', fontWeight: 600 }}>Add Webhook</h2>
          <button onClick={onClose} className="nav-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="dialog__body-base space-y-4">
          <div>
            <label className="settings-label">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Slack notifications"
              className="settings-input"
              autoFocus
            />
          </div>
          <div>
            <label className="settings-label">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/webhook"
              className="settings-input"
            />
          </div>
          <div>
            <label className="settings-label">Signing Secret (optional)</label>
            <div className="relative">
              <input
                type={showSecret ? 'text' : 'password'}
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder="HMAC signing key"
                className="settings-input pr-10"
              />
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              >
                {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="settings-label">Events</label>
            <div className="space-y-1.5">
              {ALL_EVENTS.map((event) => (
                <label
                  key={event.value}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-[var(--color-hover-bg)]"
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(event.value)}
                    onChange={() => toggleEvent(event.value)}
                    className="accent-cachi-500"
                  />
                  <span className="text-sm text-[var(--color-text-primary)]">{event.label}</span>
                  <code className="ml-auto text-xs text-[var(--color-text-secondary)]">
                    {event.value}
                  </code>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="dialog__footer">
          <button onClick={onClose} className="btn btn--secondary">Cancel</button>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || !url.trim() || selectedEvents.length === 0 || creating}
            className="btn btn--primary"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create
          </button>
        </div>
      </div>
    </div>
  )
}
