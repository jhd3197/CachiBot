import { useState, useEffect } from 'react'
import {
  Brain,
  Eye,
  Wrench,
  ListOrdered,
  Search,
  Star,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { useModelsStore } from '../../stores/models'
import { cn } from '../../lib/utils'
import type { ModelInfo } from '../../api/models'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  groq: 'Groq',
  grok: 'xAI Grok',
  openrouter: 'OpenRouter',
  moonshot: 'Moonshot AI',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  azure: 'Azure OpenAI',
  zai: 'Z.ai (Zhipu)',
  modelscope: 'ModelScope',
  local_http: 'Local HTTP',
}

function formatNumber(n: number | null): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toString()
}

function formatPrice(rate: number | null): string {
  if (rate == null) return '—'
  if (rate === 0) return 'free'
  if (rate >= 1) return `$${rate.toFixed(2)}`
  return `$${rate.toFixed(4)}`.replace(/0+$/, '')
}

function CapBadge({
  icon: Icon,
  label,
  active,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  active: boolean
}) {
  if (!active) return null
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
      <Icon className="h-3 w-3" />
      {label}
    </span>
  )
}

export function ModelsView() {
  const { groups, defaultModel, loading, refresh, updateDefaultModel } = useModelsStore()
  const [search, setSearch] = useState('')
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  // Refresh models when page mounts
  useEffect(() => {
    refresh()
  }, [refresh])

  // Filter models by search
  const filteredGroups: Record<string, ModelInfo[]> = {}
  for (const [provider, modelList] of Object.entries(groups)) {
    const filtered = modelList.filter((m) =>
      m.id.toLowerCase().includes(search.toLowerCase())
    )
    if (filtered.length > 0) {
      filteredGroups[provider] = filtered
    }
  }

  const totalModels = Object.values(groups).reduce((s, g) => s + g.length, 0)
  const filteredTotal = Object.values(filteredGroups).reduce(
    (s, g) => s + g.length,
    0
  )
  const providerCount = Object.keys(groups).length

  const toggleCollapse = (provider: string) =>
    setCollapsed((prev) => ({ ...prev, [provider]: !prev[provider] }))

  const handleSetDefault = async (modelId: string) => {
    await updateDefaultModel(modelId)
  }

  return (
    <div className="flex h-full flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-300 px-6 py-4 dark:border-zinc-800">
        <div>
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">Models</h1>
          <p className="text-sm text-zinc-500">
            All available models from configured providers
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          {/* Stats + Search */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-3 bg-white border border-zinc-300 rounded-xl px-4 py-3 dark:bg-zinc-900 dark:border-zinc-800">
              <div className="w-9 h-9 rounded-lg bg-cachi-500/10 flex items-center justify-center">
                <Brain className="h-5 w-5 text-cachi-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {totalModels} model{totalModels !== 1 ? 's' : ''}
                </p>
                <p className="text-[11px] text-zinc-500">
                  {providerCount} provider{providerCount !== 1 ? 's' : ''} active
                </p>
              </div>
            </div>

            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 h-4 w-4" />
              <input
                type="text"
                placeholder="Search models..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-white border border-zinc-300 text-zinc-900 text-sm rounded-lg py-2 pl-9 pr-3 focus:border-cachi-500 focus:outline-none dark:bg-zinc-900 dark:border-zinc-800 dark:text-zinc-100"
              />
            </div>

            {search && (
              <span className="text-xs text-zinc-500">
                {filteredTotal} result{filteredTotal !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {/* Loading */}
          {loading && (
            <div className="text-sm text-zinc-500 py-12 text-center flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Discovering models...
            </div>
          )}

          {/* Empty state */}
          {!loading && totalModels === 0 && (
            <div className="text-center py-16 space-y-3">
              <Brain className="h-10 w-10 text-zinc-400 dark:text-zinc-700 mx-auto" />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">No models available</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-600">
                Configure at least one provider API key to discover models.
              </p>
            </div>
          )}

          {/* Provider groups */}
          {!loading &&
            Object.entries(filteredGroups)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([provider, modelList]) => {
                const isCollapsed = collapsed[provider]
                const label =
                  PROVIDER_LABELS[provider] ||
                  provider.charAt(0).toUpperCase() + provider.slice(1)

                return (
                  <div
                    key={provider}
                    className="bg-white border border-zinc-300 rounded-xl overflow-hidden dark:bg-zinc-900 dark:border-zinc-800"
                  >
                    {/* Provider header */}
                    <button
                      onClick={() => toggleCollapse(provider)}
                      className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-zinc-100/50 transition-colors dark:hover:bg-zinc-800/50"
                    >
                      <div className="flex items-center gap-3">
                        {isCollapsed ? (
                          <ChevronRight className="h-4 w-4 text-zinc-500" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-zinc-500" />
                        )}
                        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {label}
                        </span>
                        <span className="text-[11px] text-zinc-500">
                          {modelList.length} model{modelList.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </button>

                    {/* Model list */}
                    {!isCollapsed && (
                      <div className="border-t border-zinc-300 dark:border-zinc-800">
                        {modelList.map((m) => {
                          const isDefault = m.id === defaultModel
                          return (
                            <div
                              key={m.id}
                              className={cn(
                                'flex items-center gap-4 px-5 py-3 border-b border-zinc-200/50 last:border-b-0 hover:bg-zinc-100/30 transition-colors dark:border-zinc-800/50 dark:hover:bg-zinc-800/30',
                                isDefault && 'bg-cachi-500/5'
                              )}
                            >
                              {/* Model name */}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-sm text-zinc-900 font-mono truncate dark:text-zinc-100">
                                    {m.id}
                                  </span>
                                  {isDefault && (
                                    <span className="text-[10px] text-cachi-600 bg-cachi-500/10 border border-cachi-500/20 px-1.5 py-0.5 rounded shrink-0 dark:text-cachi-400">
                                      Default
                                    </span>
                                  )}
                                  {m.is_reasoning && (
                                    <span className="text-[10px] text-purple-600 bg-purple-500/10 border border-purple-500/20 px-1.5 py-0.5 rounded shrink-0 dark:text-purple-400">
                                      Reasoning
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Capabilities */}
                              <div className="hidden md:flex items-center gap-1.5 shrink-0">
                                <CapBadge
                                  icon={Eye}
                                  label="Vision"
                                  active={m.supports_vision}
                                />
                                <CapBadge
                                  icon={Wrench}
                                  label="Tools"
                                  active={m.supports_tool_use}
                                />
                                <CapBadge
                                  icon={ListOrdered}
                                  label="Structured"
                                  active={m.supports_structured_output}
                                />
                              </div>

                              {/* Context window */}
                              <div className="hidden lg:block text-right shrink-0 w-20">
                                <p className="text-[10px] text-zinc-500 dark:text-zinc-600">Context</p>
                                <p className="text-xs text-zinc-600 font-mono dark:text-zinc-400">
                                  {formatNumber(m.context_window)}
                                </p>
                              </div>

                              {/* Max output */}
                              <div className="hidden lg:block text-right shrink-0 w-20">
                                <p className="text-[10px] text-zinc-500 dark:text-zinc-600">Output</p>
                                <p className="text-xs text-zinc-600 font-mono dark:text-zinc-400">
                                  {formatNumber(m.max_output_tokens)}
                                </p>
                              </div>

                              {/* Pricing per 1M tokens */}
                              <div className="hidden xl:block text-right shrink-0 w-28">
                                <p className="text-[10px] text-zinc-500 dark:text-zinc-600">
                                  Price / 1M tok
                                </p>
                                {m.pricing ? (
                                  <p className="text-xs text-zinc-600 font-mono dark:text-zinc-400">
                                    <span className="text-emerald-600 dark:text-emerald-400">
                                      {formatPrice(m.pricing.input)}
                                    </span>
                                    <span className="text-zinc-400 mx-0.5 dark:text-zinc-600">/</span>
                                    <span className="text-amber-600 dark:text-amber-400">
                                      {formatPrice(m.pricing.output)}
                                    </span>
                                  </p>
                                ) : (
                                  <p className="text-xs text-zinc-500 dark:text-zinc-600">—</p>
                                )}
                              </div>

                              {/* Set as default */}
                              {!isDefault && (
                                <button
                                  onClick={() => handleSetDefault(m.id)}
                                  className="text-[10px] text-zinc-500 hover:text-cachi-600 hover:bg-cachi-500/10 px-2 py-1 rounded transition-colors shrink-0 dark:hover:text-cachi-400"
                                  title="Set as default model"
                                >
                                  <Star className="h-4 w-4" />
                                </button>
                              )}
                              {isDefault && <div className="w-[30px] shrink-0" />}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
        </div>
      </div>
    </div>
  )
}
