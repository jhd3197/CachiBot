/**
 * DeveloperPanel Component
 *
 * Per-bot developer settings: API keys, API documentation, and webhooks.
 */

import { useState, useEffect } from 'react'
import { copyToClipboard } from '../../lib/utils'
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
  ChevronRight,
  ChevronDown,
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
      <div className="inline-flex gap-0.5 rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)] p-[3px]">
        {([
          { id: 'api-keys', label: 'API Keys' },
          { id: 'api-docs', label: 'API Docs' },
          { id: 'webhooks', label: 'Webhooks' },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-[var(--accent-600)] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15)] hover:bg-[var(--accent-500)]'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-hover-bg)]'
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

  const handleCopy = (text: string, id: string) => {
    copyToClipboard(text)
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
              onClick={() => { handleCopy(newKey.key, 'new-key'); toast.success('Copied!') }}
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

interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  path: string
  description: string
}

interface ApiCategory {
  id: string
  label: string
  endpoints: ApiEndpoint[]
}

const API_CATEGORIES: ApiCategory[] = [
  {
    id: 'chats',
    label: 'Chats',
    endpoints: [
      { method: 'GET', path: '/chats', description: 'List chats' },
      { method: 'GET', path: '/chats/{chat_id}', description: 'Get chat' },
      { method: 'GET', path: '/chats/{chat_id}/messages', description: 'Get messages' },
      { method: 'DELETE', path: '/chats/{chat_id}', description: 'Delete chat' },
      { method: 'POST', path: '/chats/{chat_id}/_archive', description: 'Archive chat' },
      { method: 'POST', path: '/chats/{chat_id}/_unarchive', description: 'Unarchive chat' },
    ],
  },
  {
    id: 'work',
    label: 'Work',
    endpoints: [
      { method: 'GET', path: '/work', description: 'List work items' },
      { method: 'GET', path: '/work/active', description: 'Get active work' },
      { method: 'POST', path: '/work', description: 'Create work' },
      { method: 'GET', path: '/work/{work_id}', description: 'Get work' },
      { method: 'PATCH', path: '/work/{work_id}', description: 'Update work' },
      { method: 'POST', path: '/work/{work_id}/start', description: 'Start work' },
      { method: 'POST', path: '/work/{work_id}/complete', description: 'Complete work' },
      { method: 'POST', path: '/work/{work_id}/fail', description: 'Fail work' },
      { method: 'POST', path: '/work/{work_id}/cancel', description: 'Cancel work' },
      { method: 'DELETE', path: '/work/{work_id}', description: 'Delete work' },
    ],
  },
  {
    id: 'tasks',
    label: 'Tasks',
    endpoints: [
      { method: 'GET', path: '/work/{work_id}/tasks', description: 'List tasks' },
      { method: 'GET', path: '/work/{work_id}/tasks/ready', description: 'Get ready tasks' },
      { method: 'POST', path: '/work/{work_id}/tasks', description: 'Create task' },
      { method: 'GET', path: '/tasks/{task_id}', description: 'Get task' },
      { method: 'PATCH', path: '/tasks/{task_id}', description: 'Update task' },
      { method: 'POST', path: '/tasks/{task_id}/start', description: 'Start task' },
      { method: 'POST', path: '/tasks/{task_id}/complete', description: 'Complete task' },
      { method: 'POST', path: '/tasks/{task_id}/fail', description: 'Fail task' },
      { method: 'DELETE', path: '/tasks/{task_id}', description: 'Delete task' },
    ],
  },
  {
    id: 'todos',
    label: 'Todos',
    endpoints: [
      { method: 'GET', path: '/todos', description: 'List todos' },
      { method: 'GET', path: '/todos/open', description: 'Get open todos' },
      { method: 'POST', path: '/todos', description: 'Create todo' },
      { method: 'GET', path: '/todos/{todo_id}', description: 'Get todo' },
      { method: 'PATCH', path: '/todos/{todo_id}', description: 'Update todo' },
      { method: 'POST', path: '/todos/{todo_id}/done', description: 'Mark done' },
      { method: 'POST', path: '/todos/{todo_id}/dismiss', description: 'Dismiss' },
      { method: 'POST', path: '/todos/{todo_id}/convert', description: 'Convert to work' },
      { method: 'DELETE', path: '/todos/{todo_id}', description: 'Delete todo' },
    ],
  },
  {
    id: 'functions',
    label: 'Functions',
    endpoints: [
      { method: 'GET', path: '/functions', description: 'List functions' },
      { method: 'POST', path: '/functions', description: 'Create function' },
      { method: 'GET', path: '/functions/{function_id}', description: 'Get function' },
      { method: 'PATCH', path: '/functions/{function_id}', description: 'Update function' },
      { method: 'DELETE', path: '/functions/{function_id}', description: 'Delete function' },
      { method: 'POST', path: '/functions/{function_id}/run', description: 'Run function' },
    ],
  },
  {
    id: 'schedules',
    label: 'Schedules',
    endpoints: [
      { method: 'GET', path: '/schedules', description: 'List schedules' },
      { method: 'POST', path: '/schedules', description: 'Create schedule' },
      { method: 'GET', path: '/schedules/{schedule_id}', description: 'Get schedule' },
      { method: 'PATCH', path: '/schedules/{schedule_id}', description: 'Update schedule' },
      { method: 'POST', path: '/schedules/{schedule_id}/toggle', description: 'Toggle on/off' },
      { method: 'DELETE', path: '/schedules/{schedule_id}', description: 'Delete schedule' },
    ],
  },
  {
    id: 'contacts',
    label: 'Contacts',
    endpoints: [
      { method: 'GET', path: '/contacts', description: 'List contacts' },
      { method: 'POST', path: '/contacts', description: 'Create contact' },
      { method: 'GET', path: '/contacts/{contact_id}', description: 'Get contact' },
      { method: 'PUT', path: '/contacts/{contact_id}', description: 'Update contact' },
      { method: 'DELETE', path: '/contacts/{contact_id}', description: 'Delete contact' },
    ],
  },
  {
    id: 'knowledge',
    label: 'Knowledge',
    endpoints: [
      { method: 'GET', path: '/knowledge/notes', description: 'List notes' },
      { method: 'POST', path: '/knowledge/notes', description: 'Create note' },
      { method: 'GET', path: '/knowledge/notes/{note_id}', description: 'Get note' },
      { method: 'PUT', path: '/knowledge/notes/{note_id}', description: 'Update note' },
      { method: 'DELETE', path: '/knowledge/notes/{note_id}', description: 'Delete note' },
      { method: 'POST', path: '/knowledge/search', description: 'Search knowledge' },
      { method: 'GET', path: '/knowledge/stats', description: 'Get stats' },
    ],
  },
  {
    id: 'scripts',
    label: 'Scripts',
    endpoints: [
      { method: 'GET', path: '/scripts', description: 'List scripts' },
      { method: 'POST', path: '/scripts', description: 'Create script' },
      { method: 'GET', path: '/scripts/{script_id}', description: 'Get script' },
      { method: 'PATCH', path: '/scripts/{script_id}', description: 'Update script' },
      { method: 'DELETE', path: '/scripts/{script_id}', description: 'Delete script' },
      { method: 'POST', path: '/scripts/{script_id}/run', description: 'Run script' },
      { method: 'POST', path: '/scripts/{script_id}/activate', description: 'Activate' },
      { method: 'POST', path: '/scripts/{script_id}/disable', description: 'Disable' },
    ],
  },
  {
    id: 'executions',
    label: 'Executions',
    endpoints: [
      { method: 'GET', path: '/executions', description: 'List executions' },
      { method: 'GET', path: '/executions/running', description: 'Running executions' },
      { method: 'GET', path: '/executions/stats', description: 'Execution stats' },
      { method: 'GET', path: '/executions/{exec_id}', description: 'Get execution' },
      { method: 'POST', path: '/executions/{exec_id}/cancel', description: 'Cancel execution' },
    ],
  },
]

function methodBadgeClasses(method: ApiEndpoint['method']): string {
  switch (method) {
    case 'GET':
      return 'bg-blue-500/10 text-blue-600'
    case 'POST':
      return 'bg-cachi-500/10 text-cachi-600'
    case 'PUT':
    case 'PATCH':
      return 'bg-amber-500/10 text-amber-600'
    case 'DELETE':
      return 'bg-red-500/10 text-red-600'
  }
}

function CollapsibleCategory({ category }: { category: ApiCategory }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-[var(--color-border)] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-[var(--color-hover-bg)] transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-[var(--color-text-secondary)]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--color-text-secondary)]" />
        )}
        <span className="flex-1 text-sm font-medium text-[var(--color-text-primary)]">
          {category.label}
        </span>
        <span className="text-xs text-[var(--color-text-secondary)]">
          {category.endpoints.length} endpoints
        </span>
      </button>
      {expanded && (
        <div className="border-t border-[var(--color-border)] px-3 py-2 space-y-1.5">
          {category.endpoints.map((ep, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-[var(--color-text-secondary)]"
            >
              <span
                className={`inline-block w-14 rounded px-1.5 py-0.5 text-center text-xs font-mono ${methodBadgeClasses(ep.method)}`}
              >
                {ep.method}
              </span>
              <code className="text-xs">{ep.path}</code>
              <span className="ml-auto text-xs opacity-60 hidden sm:inline">{ep.description}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ApiDocsPanel({ botId }: { botId: string }) {
  const { getActiveBot } = useBotStore()
  const bot = getActiveBot()
  const apiOrigin = import.meta.env.DEV ? 'http://127.0.0.1:5870' : window.location.origin
  const baseUrl = `${apiOrigin}/v1`
  const botApiBase = `${apiOrigin}/api/bots/${botId}`
  const modelName = bot?.models?.default || bot?.model || 'unknown'
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [openaiExpanded, setOpenaiExpanded] = useState(false)

  const handleCopy = (text: string, id: string) => {
    copyToClipboard(text)
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
            onClick={() => handleCopy(baseUrl, 'base-url')}
            className="btn btn--secondary btn--sm"
          >
            {copiedId === 'base-url' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Bot API Base */}
      <div>
        <label className="settings-label">Bot API Base</label>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--color-text-primary)]">
            {botApiBase}
          </code>
          <button
            onClick={() => handleCopy(botApiBase, 'bot-api-base')}
            className="btn btn--secondary btn--sm"
          >
            {copiedId === 'bot-api-base' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Model */}
      <div>
        <label className="settings-label">Model</label>
        <code className="block rounded bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--color-text-primary)]">
          {modelName}
        </code>
      </div>

      {/* API Endpoints */}
      <div className="space-y-2">
        <label className="settings-label">Endpoints</label>

        {/* OpenAI Compatible */}
        <div className="rounded-lg border border-[var(--color-border)] overflow-hidden">
          <button
            onClick={() => setOpenaiExpanded(!openaiExpanded)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-[var(--color-hover-bg)] transition-colors"
          >
            {openaiExpanded ? (
              <ChevronDown className="h-4 w-4 text-[var(--color-text-secondary)]" />
            ) : (
              <ChevronRight className="h-4 w-4 text-[var(--color-text-secondary)]" />
            )}
            <span className="flex-1 text-sm font-medium text-[var(--color-text-primary)]">
              OpenAI Compatible
            </span>
            <span className="text-xs text-[var(--color-text-secondary)]">2 endpoints</span>
          </button>
          {openaiExpanded && (
            <div className="border-t border-[var(--color-border)] px-3 py-2 space-y-1.5">
              <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
                <span className={`inline-block w-14 rounded px-1.5 py-0.5 text-center text-xs font-mono ${methodBadgeClasses('POST')}`}>
                  POST
                </span>
                <code className="text-xs">/v1/chat/completions</code>
                <span className="ml-auto text-xs opacity-60 hidden sm:inline">Chat completions</span>
              </div>
              <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
                <span className={`inline-block w-14 rounded px-1.5 py-0.5 text-center text-xs font-mono ${methodBadgeClasses('GET')}`}>
                  GET
                </span>
                <code className="text-xs">/v1/models</code>
                <span className="ml-auto text-xs opacity-60 hidden sm:inline">List models</span>
              </div>
            </div>
          )}
        </div>

        {/* Bot API categories */}
        {API_CATEGORIES.map((cat) => (
          <CollapsibleCategory key={cat.id} category={cat} />
        ))}
      </div>

      {/* Code Examples */}
      <div className="space-y-4">
        <label className="settings-label">Code Examples</label>
        {examples.map((ex) => (
          <div key={ex.id} className="rounded-lg border border-[var(--color-border)] overflow-hidden">
            <div className="flex items-center justify-between bg-[var(--color-bg-secondary)] px-3 py-1.5">
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{ex.label}</span>
              <button
                onClick={() => handleCopy(ex.code, ex.id)}
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
        <button onClick={() => setShowCreate(true)} className="btn btn--primary btn--sm">
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
