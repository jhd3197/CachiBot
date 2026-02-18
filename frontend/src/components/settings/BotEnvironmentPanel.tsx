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
import type { EnvVar, ResolvedEnv } from '../../api/bot-env'
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

  const { user: _user } = useAuthStore()

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
      <div className="bot-env-loading">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Loading environment...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && <div className="bot-env-error">{error}</div>}

      {/* Info banner */}
      <div className="bot-env-info">
        <div className="bot-env-info__body">
          <Shield className="h-5 w-5 bot-env-info__icon" />
          <div>
            <p className="bot-env-info__title">Per-Bot Environment</p>
            <p className="bot-env-info__text">
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
          className="bot-env-section-toggle"
        >
          {providerKeysOpen ? (
            <ChevronDown className="bot-env-section-toggle__chevron" />
          ) : (
            <ChevronRight className="bot-env-section-toggle__chevron" />
          )}
          <Key className="bot-env-section-toggle__icon" />
          Provider Keys
        </button>

        {providerKeysOpen && (
          <div className="mt-3 space-y-2">
            {PROVIDER_KEYS.map((provider) => {
              const status = getKeyStatus(provider.key)
              const isEditing = editingKey === provider.key
              const hasBotOverride = botVars.some((v) => v.key === provider.key)

              return (
                <div key={provider.key} className="bot-env-card">
                  {isEditing ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="bot-env-card__label">{provider.label}</span>
                        <span className="bot-env-card__env-key">{provider.key}</span>
                      </div>
                      <div className="bot-env-edit__input-wrap">
                        <input
                          type={showValue ? 'text' : 'password'}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          placeholder={`Enter ${provider.type === 'endpoint' ? 'endpoint URL' : 'API key'}...`}
                          className="bot-env-edit__input"
                          autoFocus
                        />
                        <button
                          onClick={() => setShowValue(!showValue)}
                          className="bot-env-edit__toggle-vis"
                        >
                          {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                      <div className="bot-env-edit__actions">
                        <button
                          onClick={() => handleSetKey(provider.key, editValue)}
                          disabled={!editValue.trim() || saving}
                          className="bot-env-edit__save-btn"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                          Save
                        </button>
                        <button onClick={cancelEdit} className="bot-env-edit__cancel-btn">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="bot-env-card__row">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="bot-env-card__label">{provider.label}</span>
                          <SourceBadge source={status.source} />
                        </div>
                        <div className="bot-env-card__masked">
                          {status.configured ? status.maskedValue || 'Configured' : 'Not set'}
                        </div>
                      </div>
                      <div className="bot-env-card__actions">
                        {hasBotOverride ? (
                          <>
                            <button
                              onClick={() => startEdit(provider.key)}
                              className="bot-env-icon-btn"
                              title="Edit override"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteKey(provider.key)}
                              className="bot-env-icon-btn bot-env-icon-btn--danger"
                              title="Remove override (fall back to inherited)"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => startEdit(provider.key)}
                            className="bot-env-override-btn"
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
          className="bot-env-section-toggle"
        >
          {customKeysOpen ? (
            <ChevronDown className="bot-env-section-toggle__chevron" />
          ) : (
            <ChevronRight className="bot-env-section-toggle__chevron" />
          )}
          Custom Variables
          {customBotVars.length > 0 && (
            <span className="bot-env-section-toggle__count">{customBotVars.length}</span>
          )}
        </button>

        {customKeysOpen && (
          <div className="mt-3 space-y-2">
            {customBotVars.map((v) => {
              const isEditing = editingKey === v.key

              return (
                <div key={v.key} className="bot-env-card">
                  {isEditing ? (
                    <div className="space-y-2">
                      <span className="bot-env-card__label">{v.key}</span>
                      <div className="bot-env-edit__input-wrap">
                        <input
                          type={showValue ? 'text' : 'password'}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          placeholder="Enter new value..."
                          className="bot-env-edit__input"
                          autoFocus
                        />
                        <button
                          onClick={() => setShowValue(!showValue)}
                          className="bot-env-edit__toggle-vis"
                        >
                          {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                      <div className="bot-env-edit__actions">
                        <button
                          onClick={() => handleSetKey(v.key, editValue)}
                          disabled={!editValue.trim() || saving}
                          className="bot-env-edit__save-btn"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                          Save
                        </button>
                        <button onClick={cancelEdit} className="bot-env-edit__cancel-btn">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="bot-env-card__row">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="bot-env-card__label">{v.key}</span>
                          <SourceBadge source="bot" />
                        </div>
                        <div className="bot-env-card__masked">{v.masked_value}</div>
                      </div>
                      <div className="bot-env-card__actions">
                        <button
                          onClick={() => startEdit(v.key)}
                          className="bot-env-icon-btn"
                          title="Edit"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteKey(v.key)}
                          className="bot-env-icon-btn bot-env-icon-btn--danger"
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
              <div className="bot-env-add-form space-y-2">
                <input
                  type="text"
                  value={customKeyName}
                  onChange={(e) => setCustomKeyName(e.target.value.toUpperCase())}
                  placeholder="VARIABLE_NAME"
                  className="bot-env-add-form__input--mono"
                  autoFocus
                />
                <input
                  type="password"
                  value={customKeyValue}
                  onChange={(e) => setCustomKeyValue(e.target.value)}
                  placeholder="Value..."
                  className="bot-env-add-form__input"
                />
                <div className="bot-env-edit__actions">
                  <button
                    onClick={handleAddCustomKey}
                    disabled={!customKeyName.trim() || !customKeyValue.trim() || saving}
                    className="bot-env-edit__save-btn"
                  >
                    {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                    Add
                  </button>
                  <button
                    onClick={() => { setAddingCustom(false); setCustomKeyName(''); setCustomKeyValue('') }}
                    className="bot-env-edit__cancel-btn"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button onClick={() => setAddingCustom(true)} className="bot-env-add-btn">
                <Plus className="h-4 w-4" />
                Add Custom Variable
              </button>
            )}
          </div>
        )}
      </div>

      {/* Danger Zone */}
      {(botVars.length > 0) && (
        <div className="bot-env-danger">
          <div className="bot-env-danger__panel">
            <h3 className="bot-env-danger__title">Danger Zone</h3>
            <p className="bot-env-danger__text">
              Remove all custom environment overrides for this bot. The bot will revert
              to using inherited global and platform-level settings.
            </p>
            {showResetConfirm ? (
              <div className="mt-3 flex items-center gap-2">
                <span className="bot-env-danger__confirm-text">Are you sure?</span>
                <button
                  onClick={handleResetAll}
                  disabled={resetting}
                  className="bot-env-danger__confirm-btn"
                >
                  {resetting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
                  Confirm Reset
                </button>
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="bot-env-danger__cancel-btn"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowResetConfirm(true)}
                className="bot-env-danger__reset-btn mt-3"
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
  const classMap: Record<string, string> = {
    bot: 'bot-env-badge--bot',
    platform: 'bot-env-badge--platform',
    global: 'bot-env-badge--global',
    none: 'bot-env-badge--none',
  }

  const labelMap: Record<string, string> = {
    bot: 'Custom',
    platform: 'Platform',
    global: 'Global',
    none: 'Not Set',
  }

  return (
    <span className={`bot-env-badge ${classMap[source] || 'bot-env-badge--default'}`}>
      {labelMap[source] || source}
    </span>
  )
}
