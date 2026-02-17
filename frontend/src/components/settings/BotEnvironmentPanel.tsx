/**
 * BotEnvironmentPanel Component
 *
 * Manages per-bot environment variables, showing provider keys with
 * inheritance badges, model/behavior overrides, and skill configurations.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Key,
  Pencil,
  Trash2,
  Plus,
  Check,
  X,
  Loader2,
  Eye,
  EyeOff,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Shield,
} from 'lucide-react'
import * as botEnvApi from '../../api/bot-env'
import type { EnvVar, ResolvedVar, ResolvedEnv } from '../../api/bot-env'
import { useAuthStore } from '../../stores/auth'

// Well-known provider env key names (matches backend PROVIDERS dict)
const PROVIDER_KEYS = [
  { key: 'OPENAI_API_KEY', label: 'OpenAI', type: 'api_key' },
  { key: 'CLAUDE_API_KEY', label: 'Claude', type: 'api_key' },
  { key: 'GOOGLE_API_KEY', label: 'Google', type: 'api_key' },
  { key: 'GROQ_API_KEY', label: 'Groq', type: 'api_key' },
  { key: 'GROK_API_KEY', label: 'Grok', type: 'api_key' },
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter', type: 'api_key' },
  { key: 'MOONSHOT_API_KEY', label: 'Moonshot', type: 'api_key' },
  { key: 'ZHIPU_API_KEY', label: 'ZAI (Zhipu)', type: 'api_key' },
  { key: 'MODELSCOPE_API_KEY', label: 'ModelScope', type: 'api_key' },
  { key: 'STABILITY_API_KEY', label: 'Stability AI', type: 'api_key' },
  { key: 'ELEVENLABS_API_KEY', label: 'ElevenLabs', type: 'api_key' },
  { key: 'AZURE_API_KEY', label: 'Azure', type: 'api_key' },
  { key: 'OLLAMA_ENDPOINT', label: 'Ollama', type: 'endpoint' },
  { key: 'LMSTUDIO_ENDPOINT', label: 'LM Studio', type: 'endpoint' },
  { key: 'LOCAL_HTTP_ENDPOINT', label: 'Local HTTP', type: 'endpoint' },
]

interface BotEnvironmentPanelProps {
  botId: string
}

export function BotEnvironmentPanel({ botId }: BotEnvironmentPanelProps) {
  const [resolved, setResolved] = useState<ResolvedEnv | null>(null)
  const [botVars, setBotVars] = useState<EnvVar[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Form state for adding/editing a key
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [showValue, setShowValue] = useState(false)
  const [saving, setSaving] = useState(false)

  // Custom key addition
  const [addingCustom, setAddingCustom] = useState(false)
  const [customKeyName, setCustomKeyName] = useState('')
  const [customKeyValue, setCustomKeyValue] = useState('')

  // Danger zone
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [resetting, setResetting] = useState(false)

  // Sections collapsed state
  const [providerKeysOpen, setProviderKeysOpen] = useState(true)
  const [customKeysOpen, setCustomKeysOpen] = useState(true)

  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [resolvedData, varsData] = await Promise.all([
        botEnvApi.getResolvedEnv(botId),
        botEnvApi.getBotEnvVars(botId),
      ])
      setResolved(resolvedData)
      setBotVars(varsData)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load environment')
    } finally {
      setLoading(false)
    }
  }, [botId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSetKey = async (key: string, value: string) => {
    setSaving(true)
    setError(null)
    try {
      await botEnvApi.setBotEnvVar(botId, key, value)
      setEditingKey(null)
      setEditValue('')
      setShowValue(false)
      await loadData()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteKey = async (key: string) => {
    setError(null)
    try {
      await botEnvApi.deleteBotEnvVar(botId, key)
      await loadData()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    }
  }

  const handleAddCustomKey = async () => {
    if (!customKeyName.trim() || !customKeyValue.trim()) return
    setSaving(true)
    setError(null)
    try {
      await botEnvApi.setBotEnvVar(botId, customKeyName.trim(), customKeyValue.trim())
      setAddingCustom(false)
      setCustomKeyName('')
      setCustomKeyValue('')
      await loadData()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add')
    } finally {
      setSaving(false)
    }
  }

  const handleResetAll = async () => {
    setResetting(true)
    setError(null)
    try {
      await botEnvApi.resetBotEnv(botId)
      setShowResetConfirm(false)
      await loadData()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reset')
    } finally {
      setResetting(false)
    }
  }

  const startEdit = (key: string) => {
    setEditingKey(key)
    setEditValue('')
    setShowValue(false)
  }

  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
    setShowValue(false)
  }

  // Determine status for a provider key
  const getKeyStatus = (envKey: string): { source: string; maskedValue: string | null; configured: boolean } => {
    if (!resolved) return { source: 'none', maskedValue: null, configured: false }

    const r = resolved.resolved[envKey]
    if (!r) return { source: 'none', maskedValue: null, configured: false }

    return {
      source: r.source,
      maskedValue: r.masked_value || (r.value != null ? String(r.value) : null),
      configured: true,
    }
  }

  // Custom bot-only keys (not in PROVIDER_KEYS)
  const providerKeyNames = new Set(PROVIDER_KEYS.map((p) => p.key))
  const customBotVars = botVars.filter((v) => !providerKeyNames.has(v.key))

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
        <span className="ml-2 text-sm text-zinc-500">Loading environment...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Info banner */}
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
        <div className="flex items-start gap-3">
          <Shield className="mt-0.5 h-5 w-5 flex-shrink-0 text-cachi-500" />
          <div>
            <p className="text-sm font-medium text-zinc-200">Per-Bot Environment</p>
            <p className="mt-1 text-xs text-zinc-500">
              Override API keys and settings for this bot. Custom keys take priority over
              global settings. Keys are encrypted at rest and never returned in plain text.
            </p>
          </div>
        </div>
      </div>

      {/* Provider Keys Section */}
      <div>
        <button
          onClick={() => setProviderKeysOpen(!providerKeysOpen)}
          className="flex w-full items-center gap-2 text-sm font-medium text-zinc-200"
        >
          {providerKeysOpen ? (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-zinc-500" />
          )}
          <Key className="h-4 w-4 text-zinc-400" />
          Provider Keys
        </button>

        {providerKeysOpen && (
          <div className="mt-3 space-y-2">
            {PROVIDER_KEYS.map((provider) => {
              const status = getKeyStatus(provider.key)
              const isEditing = editingKey === provider.key
              const hasBotOverride = botVars.some((v) => v.key === provider.key)

              return (
                <div
                  key={provider.key}
                  className="rounded-lg border border-zinc-800 p-3"
                >
                  {isEditing ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200">
                          {provider.label}
                        </span>
                        <span className="text-xs text-zinc-600">{provider.key}</span>
                      </div>
                      <div className="relative">
                        <input
                          type={showValue ? 'text' : 'password'}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          placeholder={`Enter ${provider.type === 'endpoint' ? 'endpoint URL' : 'API key'}...`}
                          className="w-full rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 pr-10 text-sm text-zinc-100 placeholder:text-zinc-600"
                          autoFocus
                        />
                        <button
                          onClick={() => setShowValue(!showValue)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                        >
                          {showValue ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSetKey(provider.key, editValue)}
                          disabled={!editValue.trim() || saving}
                          className="flex items-center gap-1 rounded bg-cachi-600 px-2 py-1 text-xs text-white hover:bg-cachi-500 disabled:opacity-50"
                        >
                          {saving ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Check className="h-3 w-3" />
                          )}
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="rounded bg-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-600"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-zinc-200">
                              {provider.label}
                            </span>
                            <SourceBadge source={status.source} />
                          </div>
                          <div className="mt-0.5 text-xs text-zinc-500">
                            {status.configured
                              ? status.maskedValue || 'Configured'
                              : 'Not set'}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {hasBotOverride ? (
                          <>
                            <button
                              onClick={() => startEdit(provider.key)}
                              className="rounded p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                              title="Edit override"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteKey(provider.key)}
                              className="rounded p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-red-400"
                              title="Remove override (fall back to inherited)"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => startEdit(provider.key)}
                            className="rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                          >
                            Override
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Custom Keys Section */}
      <div>
        <button
          onClick={() => setCustomKeysOpen(!customKeysOpen)}
          className="flex w-full items-center gap-2 text-sm font-medium text-zinc-200"
        >
          {customKeysOpen ? (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-zinc-500" />
          )}
          Custom Variables
          {customBotVars.length > 0 && (
            <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
              {customBotVars.length}
            </span>
          )}
        </button>

        {customKeysOpen && (
          <div className="mt-3 space-y-2">
            {customBotVars.map((v) => {
              const isEditing = editingKey === v.key

              return (
                <div
                  key={v.key}
                  className="rounded-lg border border-zinc-800 p-3"
                >
                  {isEditing ? (
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-zinc-200">{v.key}</span>
                      <div className="relative">
                        <input
                          type={showValue ? 'text' : 'password'}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          placeholder="Enter new value..."
                          className="w-full rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 pr-10 text-sm text-zinc-100"
                          autoFocus
                        />
                        <button
                          onClick={() => setShowValue(!showValue)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                        >
                          {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSetKey(v.key, editValue)}
                          disabled={!editValue.trim() || saving}
                          className="flex items-center gap-1 rounded bg-cachi-600 px-2 py-1 text-xs text-white hover:bg-cachi-500 disabled:opacity-50"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                          Save
                        </button>
                        <button onClick={cancelEdit} className="rounded bg-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-600">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-zinc-200">{v.key}</span>
                          <SourceBadge source="bot" />
                        </div>
                        <div className="mt-0.5 text-xs text-zinc-500">{v.masked_value}</div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => startEdit(v.key)}
                          className="rounded p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                          title="Edit"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteKey(v.key)}
                          className="rounded p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-red-400"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}

            {/* Add custom key form */}
            {addingCustom ? (
              <div className="space-y-2 rounded-lg border border-zinc-700 bg-zinc-800/50 p-3">
                <input
                  type="text"
                  value={customKeyName}
                  onChange={(e) => setCustomKeyName(e.target.value.toUpperCase())}
                  placeholder="VARIABLE_NAME"
                  className="w-full rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 font-mono placeholder:text-zinc-600"
                  autoFocus
                />
                <input
                  type="password"
                  value={customKeyValue}
                  onChange={(e) => setCustomKeyValue(e.target.value)}
                  placeholder="Value..."
                  className="w-full rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleAddCustomKey}
                    disabled={!customKeyName.trim() || !customKeyValue.trim() || saving}
                    className="flex items-center gap-1 rounded bg-cachi-600 px-3 py-1 text-xs text-white hover:bg-cachi-500 disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                    Add
                  </button>
                  <button
                    onClick={() => { setAddingCustom(false); setCustomKeyName(''); setCustomKeyValue('') }}
                    className="rounded bg-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:bg-zinc-600"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setAddingCustom(true)}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-700 p-2.5 text-sm text-zinc-500 hover:border-zinc-600 hover:text-zinc-400"
              >
                <Plus className="h-4 w-4" />
                Add Custom Variable
              </button>
            )}
          </div>
        )}
      </div>

      {/* Danger Zone */}
      {(botVars.length > 0) && (
        <div className="border-t border-zinc-800 pt-6">
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
            <h3 className="text-sm font-semibold text-red-400">Danger Zone</h3>
            <p className="mt-1 text-xs text-zinc-500">
              Remove all custom environment overrides for this bot. The bot will revert
              to using inherited global and platform-level settings.
            </p>
            {showResetConfirm ? (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-xs text-red-400">Are you sure?</span>
                <button
                  onClick={handleResetAll}
                  disabled={resetting}
                  className="flex items-center gap-1 rounded bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-500 disabled:opacity-50"
                >
                  {resetting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
                  Confirm Reset
                </button>
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="rounded px-3 py-1 text-xs text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowResetConfirm(true)}
                className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/50 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reset All to Defaults
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SourceBadge({ source }: { source: string }) {
  switch (source) {
    case 'bot':
      return (
        <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-medium text-green-400">
          Custom
        </span>
      )
    case 'platform':
      return (
        <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-medium text-blue-400">
          Platform
        </span>
      )
    case 'global':
      return (
        <span className="rounded-full bg-zinc-600/30 px-2 py-0.5 text-[10px] font-medium text-zinc-400">
          Global
        </span>
      )
    case 'none':
      return (
        <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-600">
          Not Set
        </span>
      )
    default:
      return (
        <span className="rounded-full bg-zinc-700/50 px-2 py-0.5 text-[10px] font-medium text-zinc-500">
          {source}
        </span>
      )
  }
}
