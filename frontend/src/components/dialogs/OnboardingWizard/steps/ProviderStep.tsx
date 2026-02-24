import { useState, useEffect } from 'react'
import { Eye, EyeOff, Save, Loader2, Trash2, ExternalLink, Sparkles } from 'lucide-react'
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

  const handleModelChange = async (model: string) => {
    if (model) {
      await updateDefaultModel(model)
    }
  }

  const renderProviderCard = (provider: typeof providers[number], featured = false) => {
    const inputValue = editValues[provider.name] ?? ''
    const isVisible = visibleKeys.has(provider.name)
    const isSaving = saving === provider.name
    const label = PROVIDER_LABELS[provider.name] || provider.name

    return (
      <div
        key={provider.name}
        className={cn(
          'rounded-lg border p-3 space-y-2',
          featured
            ? 'border-accent-500/40 bg-accent-500/5'
            : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-primary)]'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {featured && <Sparkles className="h-4 w-4 text-accent-600 dark:text-accent-400" />}
            <h4 className="text-sm font-medium text-[var(--color-text-primary)]">{label}</h4>
            <span
              className={cn(
                'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium',
                provider.configured
                  ? 'bg-[var(--color-success-bg)] text-[var(--color-success-text)]'
                  : 'bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)]'
              )}
            >
              {provider.configured ? 'Active' : 'Not set'}
            </span>
            {featured && (
              <a
                href={provider.configured ? 'https://cachibot.ai/dashboard' : 'https://cachibot.ai/register'}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-accent-600 bg-accent-500/10 hover:bg-accent-500/20 transition-colors dark:text-accent-400"
              >
                {provider.configured ? 'Dashboard' : 'Sign up for a key'} <ExternalLink className="h-2.5 w-2.5" />
              </a>
            )}
          </div>
          {provider.configured && (
            <button
              onClick={() => handleDelete(provider.name)}
              className="rounded p-1 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-danger-bg)] hover:text-[var(--color-danger-text)]"
              title="Remove key"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {provider.configured && !(provider.name in editValues) && (
          <div className="flex items-center gap-1.5">
            <div className="flex-1 truncate rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-inset)] px-2 py-1 font-mono text-xs text-[var(--color-text-secondary)]">
              {isVisible
                ? provider.masked_value
                : provider.masked_value.replace(/./g, '*').slice(0, 16) + '****'}
            </div>
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="rounded p-1 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover-bg)]"
            >
              {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          </div>
        )}

        <div className="flex gap-1.5">
          <input
            type={isVisible ? 'text' : 'password'}
            value={inputValue}
            onChange={(e) =>
              setEditValues((prev) => ({ ...prev, [provider.name]: e.target.value }))
            }
            placeholder={provider.configured ? 'Update key...' : 'Enter API key...'}
            className="h-8 flex-1 rounded border border-[var(--input-border)] bg-[var(--input-bg)] px-2 font-mono text-xs text-[var(--input-text)] outline-none transition-colors placeholder:text-[var(--input-placeholder)] focus:border-accent-500"
          />
          <button
            onClick={() => toggleVisibility(provider.name)}
            className="rounded border border-[var(--color-border-secondary)] px-2 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover-bg)]"
          >
            {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={() => handleSave(provider.name)}
            disabled={!inputValue.trim() || isSaving}
            className="flex items-center gap-1 rounded bg-accent-600 px-3 text-xs font-medium text-white transition-colors hover:bg-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save
          </button>
        </div>
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
