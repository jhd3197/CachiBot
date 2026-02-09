import { useState, useEffect } from 'react'
import { Eye, EyeOff, Save, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useProvidersStore } from '../../../../stores/providers'
import { useModelsStore } from '../../../../stores/models'
import { cn } from '../../../../lib/utils'

const TOP_PROVIDERS = ['openai', 'claude', 'google', 'groq']

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  claude: 'Anthropic / Claude',
  google: 'Google AI',
  groq: 'Groq',
}

export function ApiKeyStep() {
  const { providers, refresh, update, remove } = useProvidersStore()
  const { refresh: refreshModels } = useModelsStore()
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    refresh()
  }, [refresh])

  const topProviders = providers.filter((p) => TOP_PROVIDERS.includes(p.name))
  const configuredCount = topProviders.filter((p) => p.configured).length

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

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-zinc-100">Connect an AI Provider</h3>
        <p className="mt-1 text-sm text-zinc-400">
          You need at least one API key to use CachiBot.
          {configuredCount > 0 && (
            <span className="ml-1 text-green-400">
              {configuredCount} provider{configuredCount > 1 ? 's' : ''} configured.
            </span>
          )}
        </p>
      </div>

      <div className="space-y-3">
        {topProviders.map((provider) => {
          const inputValue = editValues[provider.name] ?? ''
          const isVisible = visibleKeys.has(provider.name)
          const isSaving = saving === provider.name
          const label = PROVIDER_LABELS[provider.name] || provider.name

          return (
            <div
              key={provider.name}
              className="rounded-lg border border-zinc-800 bg-zinc-800/50 p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-zinc-200">{label}</h4>
                  <span
                    className={cn(
                      'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
                      provider.configured
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-zinc-700 text-zinc-400'
                    )}
                  >
                    {provider.configured ? 'Active' : 'Not set'}
                  </span>
                </div>
                {provider.configured && (
                  <button
                    onClick={() => handleDelete(provider.name)}
                    className="rounded p-1 text-zinc-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
                    title="Remove key"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              {provider.configured && !(provider.name in editValues) && (
                <div className="flex items-center gap-2">
                  <div className="flex-1 rounded-lg border border-zinc-700 bg-zinc-700/50 px-3 py-2 font-mono text-sm text-zinc-400">
                    {isVisible
                      ? provider.masked_value
                      : provider.masked_value.replace(/./g, '*').slice(0, 20) + '****'}
                  </div>
                  <button
                    onClick={() => toggleVisibility(provider.name)}
                    className="rounded p-2 text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-300"
                  >
                    {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              )}

              <div className="flex gap-2">
                <input
                  type={isVisible ? 'text' : 'password'}
                  value={inputValue}
                  onChange={(e) =>
                    setEditValues((prev) => ({ ...prev, [provider.name]: e.target.value }))
                  }
                  placeholder={provider.configured ? 'Update API key...' : 'Enter API key...'}
                  className="h-10 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 font-mono text-sm text-zinc-100 outline-none transition-colors focus:border-accent-500"
                />
                <button
                  onClick={() => toggleVisibility(provider.name)}
                  className="rounded-lg border border-zinc-700 px-3 text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-300"
                >
                  {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => handleSave(provider.name)}
                  disabled={!inputValue.trim() || isSaving}
                  className="flex items-center gap-1.5 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors hover:bg-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSaving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Save
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-zinc-500">
        More providers available in Settings &gt; API Keys after setup.
      </p>
    </div>
  )
}
