import { useState, useEffect } from 'react'
import { Eye, EyeOff, Save, Loader2, Trash2, RefreshCw, ExternalLink, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { useProvidersStore } from '../../../../stores/providers'
import { useModelsStore } from '../../../../stores/models'
import { ModelSelect } from '../../../common/ModelSelect'
import { cn } from '../../../../lib/utils'

const CACHIBOT_PROVIDER = 'cachibot'
const TOP_PROVIDERS = ['claude', 'openai', 'google', 'groq']

const PROVIDER_LABELS: Record<string, string> = {
  cachibot: 'CachiBot API',
  claude: 'Anthropic / Claude',
  openai: 'OpenAI',
  google: 'Google AI',
  groq: 'Groq',
}

export function ProviderStep() {
  const { providers, refresh, update, remove } = useProvidersStore()
  const { defaultModel, updateDefaultModel, refresh: refreshModels } = useModelsStore()
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [replacingKeys, setReplacingKeys] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    refresh()
    refreshModels()
  }, [refresh, refreshModels])

  const cachibotProvider = providers.find((p) => p.name === CACHIBOT_PROVIDER)
  // Sort providers to match TOP_PROVIDERS order
  const topProviders = TOP_PROVIDERS
    .map((name) => providers.find((p) => p.name === name))
    .filter(Boolean) as typeof providers
  const allShown = cachibotProvider ? [cachibotProvider, ...topProviders] : topProviders
  const configuredCount = allShown.filter((p) => p.configured).length

  const handleSave = async (name: string) => {
    const value = editValues[name]
    if (!value?.trim()) return

    setSaving(name)
    try {
      await update(name, value.trim())
      setEditValues((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
      setVisibleKeys((prev) => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
      setReplacingKeys((prev) => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key saved`)
    } catch {
      toast.error(`Failed to save ${PROVIDER_LABELS[name] || name} key`)
    } finally {
      setSaving(null)
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await remove(name)
      setEditValues((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
      setReplacingKeys((prev) => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key removed`)
    } catch {
      toast.error(`Failed to remove ${PROVIDER_LABELS[name] || name} key`)
    }
  }

  const toggleVisibility = (name: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  const enterReplaceMode = (name: string) => {
    setReplacingKeys((prev) => new Set(prev).add(name))
    setEditValues((prev) => ({ ...prev, [name]: '' }))
  }

  const cancelReplaceMode = (name: string) => {
    setReplacingKeys((prev) => {
      const next = new Set(prev)
      next.delete(name)
      return next
    })
    setEditValues((prev) => {
      const next = { ...prev }
      delete next[name]
      return next
    })
  }

  const handleModelChange = async (model: string) => {
    if (model) {
      await updateDefaultModel(model)
    }
  }

  const renderProviderCard = (provider: typeof providers[number], featured = false) => {
    const inputValue = editValues[provider.name] ?? ''
    const isVisible = visibleKeys.has(provider.name)
    const isReplacing = replacingKeys.has(provider.name)
    const isSaving = saving === provider.name
    const label = PROVIDER_LABELS[provider.name] || provider.name

    return (
      <div
        key={provider.name}
        className={cn(
          'provider-card',
          featured && 'provider-card--featured'
        )}
      >
        <div className="provider-card__header">
          <div className="flex items-center gap-2">
            {featured && <Sparkles className="h-4 w-4 text-[var(--accent-500)]" />}
            <h4 className="provider-card__name">{label}</h4>
            <span
              className={cn(
                'provider-card__badge',
                provider.configured
                  ? 'provider-card__badge--active'
                  : 'provider-card__badge--inactive'
              )}
            >
              {provider.configured ? 'Active' : 'Not set'}
            </span>
            {featured && (
              <a
                href={provider.configured ? 'https://cachibot.ai/dashboard' : 'https://cachibot.ai/register'}
                target="_blank"
                rel="noopener noreferrer"
                className="provider-card__cta-link"
              >
                {provider.configured ? 'Dashboard' : 'Sign up for a key'} <ExternalLink className="h-2.5 w-2.5" />
              </a>
            )}
          </div>
          {provider.configured && (
            <button
              onClick={() => handleDelete(provider.name)}
              className="provider-card__delete-btn"
              title="Remove key"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* State 1: Not configured — show input + save */}
        {!provider.configured && !isReplacing && (
          <div className="flex gap-2">
            <input
              type={isVisible ? 'text' : 'password'}
              value={inputValue}
              onChange={(e) =>
                setEditValues((prev) => ({ ...prev, [provider.name]: e.target.value }))
              }
              placeholder="Enter API key..."
              className="provider-card__key-input flex-1"
            />
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="provider-card__visibility-btn-bordered"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={() => handleSave(provider.name)}
              disabled={!inputValue.trim() || isSaving}
              className="provider-card__save-btn"
            >
              {isSaving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              Save
            </button>
          </div>
        )}

        {/* State 2: Configured, viewing — show masked value + eye toggle + replace */}
        {provider.configured && !isReplacing && (
          <div className="flex items-center gap-2">
            <div className="provider-card__masked">
              {isVisible
                ? provider.masked_value
                : provider.masked_value.replace(/./g, '*').slice(0, 16) + '****'}
            </div>
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="provider-card__visibility-btn"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={() => enterReplaceMode(provider.name)}
              className="provider-card__replace-btn"
              title="Replace key"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* State 3: Configured, replacing — show input + save + cancel */}
        {provider.configured && isReplacing && (
          <div className="flex gap-2">
            <input
              type={isVisible ? 'text' : 'password'}
              value={inputValue}
              onChange={(e) =>
                setEditValues((prev) => ({ ...prev, [provider.name]: e.target.value }))
              }
              placeholder="Enter new API key..."
              className="provider-card__key-input flex-1"
            />
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="provider-card__visibility-btn-bordered"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={() => handleSave(provider.name)}
              disabled={!inputValue.trim() || isSaving}
              className="provider-card__save-btn"
            >
              {isSaving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              Save
            </button>
            <button
              onClick={() => cancelReplaceMode(provider.name)}
              className="provider-card__cancel-btn"
              title="Cancel"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {configuredCount > 0 && (
        <p className="text-sm text-[var(--color-success-text)]">
          {configuredCount} provider{configuredCount > 1 ? 's' : ''} configured.
        </p>
      )}

      {/* CachiBot API — featured */}
      {cachibotProvider && renderProviderCard(cachibotProvider, true)}

      {/* Other providers — 2-column grid */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {topProviders.map((provider) => renderProviderCard(provider))}
      </div>

      <p className="text-xs text-[var(--color-text-secondary)]">
        More providers available in Settings &gt; API Keys after setup.
      </p>

      {/* Default model selection */}
      <div className="border-t border-[var(--color-border-primary)] pt-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-[var(--color-text-primary)]">Default Model</label>
          <ModelSelect
            value={defaultModel}
            onChange={handleModelChange}
            placeholder="Select a model..."
            className="w-full"
          />
        </div>

        {defaultModel && (
          <div className="mt-3 rounded-lg border border-[var(--color-success-border)] bg-[var(--color-success-bg)] p-2.5">
            <p className="text-sm text-[var(--color-success-text)]">
              Selected: <span className="font-mono text-xs">{defaultModel}</span>
            </p>
          </div>
        )}

        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
          You can change this anytime in Settings &gt; Models.
        </p>
      </div>
    </div>
  )
}
