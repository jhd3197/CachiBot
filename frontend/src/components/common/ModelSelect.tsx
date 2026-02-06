import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Search, ChevronDown, Check, Pencil } from 'lucide-react'
import { useModelsStore } from '../../stores/models'
import { cn } from '../../lib/utils'

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
}

function formatTokens(n: number | null): string | null {
  if (!n) return null
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`
  return String(n)
}

function providerLabel(key: string): string {
  return PROVIDER_LABELS[key] || key.charAt(0).toUpperCase() + key.slice(1)
}

interface ModelSelectProps {
  value: string
  onChange: (modelId: string) => void
  placeholder?: string
  className?: string
}

export function ModelSelect({
  value,
  onChange,
  placeholder = 'System Default',
  className = '',
}: ModelSelectProps) {
  const { groups, refresh, loading } = useModelsStore()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [manualMode, setManualMode] = useState(false)
  const [manualValue, setManualValue] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const manualRef = useRef<HTMLInputElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })

  // Refresh models on mount
  useEffect(() => {
    refresh()
  }, [refresh])

  const updatePos = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      setPos({ top: rect.bottom + 4, left: rect.left, width: rect.width })
    }
  }, [])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
        setManualMode(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Update position when opening and on scroll/resize
  useEffect(() => {
    if (!open) return
    updatePos()
    window.addEventListener('scroll', updatePos, true)
    window.addEventListener('resize', updatePos)
    return () => {
      window.removeEventListener('scroll', updatePos, true)
      window.removeEventListener('resize', updatePos)
    }
  }, [open, updatePos])

  // Focus search when opened
  useEffect(() => {
    if (open && !manualMode && searchRef.current) {
      searchRef.current.focus()
    }
  }, [open, manualMode])

  // Focus manual input when switching to manual mode
  useEffect(() => {
    if (manualMode && manualRef.current) {
      manualRef.current.focus()
    }
  }, [manualMode])

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    if (!q) return groups
    const result: typeof groups = {}
    for (const [provider, items] of Object.entries(groups)) {
      const matches = items.filter(
        (m) =>
          m.id.toLowerCase().includes(q) ||
          provider.toLowerCase().includes(q)
      )
      if (matches.length > 0) result[provider] = matches
    }
    return result
  }, [groups, search])

  const totalCount = Object.values(filtered).reduce(
    (sum, arr) => sum + arr.length,
    0
  )

  const handleManualSubmit = () => {
    const trimmed = manualValue.trim()
    if (trimmed) {
      onChange(trimmed)
    }
    setOpen(false)
    setManualMode(false)
    setManualValue('')
  }

  return (
    <div className={cn('relative', className)}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          setOpen(!open)
          setSearch('')
          setManualMode(false)
        }}
        className="w-full bg-zinc-900 border border-zinc-700 text-sm rounded-lg py-2 px-3 pr-8 focus:border-cachi-500 focus:outline-none text-left flex items-center justify-between gap-2"
      >
        <span
          className={cn(
            'truncate',
            value ? 'text-zinc-100 font-mono text-xs' : 'text-zinc-500'
          )}
        >
          {value || placeholder}
        </span>
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 h-4 w-4 pointer-events-none" />
      </button>

      {open &&
        createPortal(
          <div
            ref={dropdownRef}
            className="fixed z-[9999] bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl overflow-hidden"
            style={{ top: pos.top, left: pos.left, width: Math.max(pos.width, 300) }}
          >
            {manualMode ? (
              /* Manual input mode */
              <div className="p-2">
                <p className="text-[10px] text-zinc-500 mb-1.5 px-1">
                  Enter model in provider/model format
                </p>
                <div className="flex gap-1.5">
                  <input
                    ref={manualRef}
                    type="text"
                    value={manualValue}
                    onChange={(e) => setManualValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleManualSubmit()
                      if (e.key === 'Escape') {
                        setManualMode(false)
                        setManualValue('')
                      }
                    }}
                    placeholder="openrouter/moonshotai/kimi-k2.5"
                    className="flex-1 bg-zinc-950 border border-zinc-700 text-zinc-100 text-xs font-mono rounded-md py-1.5 px-2 focus:border-cachi-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleManualSubmit}
                    disabled={!manualValue.trim()}
                    className="bg-cachi-600 hover:bg-cachi-500 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors"
                  >
                    Set
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Search input */}
                <div className="p-2 border-b border-zinc-800">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500 h-3.5 w-3.5" />
                    <input
                      ref={searchRef}
                      type="text"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search models..."
                      className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-xs rounded-md py-1.5 pl-8 pr-3 focus:border-cachi-500 focus:outline-none"
                    />
                  </div>
                </div>

                {/* Model list */}
                <div className="max-h-64 overflow-y-auto">
                  {/* Loading state */}
                  {loading && (
                    <div className="px-3 py-6 text-center text-xs text-zinc-500">
                      Discovering models...
                    </div>
                  )}

                  {/* Clear / default option */}
                  {!search && !loading && (
                    <button
                      type="button"
                      onClick={() => {
                        onChange('')
                        setOpen(false)
                      }}
                      className={cn(
                        'w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors flex items-center justify-between',
                        !value ? 'text-cachi-400' : 'text-zinc-400'
                      )}
                    >
                      <span>{placeholder}</span>
                      {!value && <Check className="h-3.5 w-3.5 text-cachi-500" />}
                    </button>
                  )}

                  {!loading &&
                    Object.entries(filtered)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([provider, items]) => (
                        <div key={provider}>
                          <div className="px-3 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider bg-zinc-950/50 sticky top-0">
                            {providerLabel(provider)}
                            <span className="ml-1.5 text-zinc-600">{items.length}</span>
                          </div>
                          {items.map((m) => {
                            const isSelected = value === m.id
                            const ctx = formatTokens(m.context_window)
                            return (
                              <button
                                key={m.id}
                                type="button"
                                onClick={() => {
                                  onChange(m.id)
                                  setOpen(false)
                                }}
                                className={cn(
                                  'w-full text-left px-3 py-1.5 text-sm hover:bg-zinc-800 transition-colors flex items-center justify-between gap-2',
                                  isSelected
                                    ? 'text-cachi-400 bg-cachi-500/5'
                                    : 'text-zinc-300'
                                )}
                              >
                                <span className="truncate font-mono text-xs">
                                  {m.id}
                                </span>
                                <span className="flex items-center gap-2 shrink-0">
                                  {ctx && (
                                    <span className="text-[10px] text-zinc-600">
                                      {ctx}
                                    </span>
                                  )}
                                  {m.supports_vision && (
                                    <span className="text-[9px] bg-zinc-800 text-zinc-400 px-1 rounded">
                                      vision
                                    </span>
                                  )}
                                  {m.is_reasoning && (
                                    <span className="text-[9px] bg-purple-900/40 text-purple-400 px-1 rounded">
                                      reasoning
                                    </span>
                                  )}
                                  {isSelected && (
                                    <Check className="h-3.5 w-3.5 text-cachi-500" />
                                  )}
                                </span>
                              </button>
                            )
                          })}
                        </div>
                      ))}

                  {!loading && totalCount === 0 && (
                    <div className="px-3 py-6 text-center text-xs text-zinc-500">
                      {Object.keys(groups).length === 0
                        ? 'No models available. Configure API keys first.'
                        : 'No models match your search.'}
                    </div>
                  )}
                </div>

                {/* Manual entry option */}
                <div className="border-t border-zinc-800">
                  <button
                    type="button"
                    onClick={() => {
                      setManualValue(value || '')
                      setManualMode(true)
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors flex items-center gap-2"
                  >
                    <Pencil className="h-3 w-3" />
                    Enter manually
                  </button>
                </div>
              </>
            )}
          </div>,
          document.body
        )}
    </div>
  )
}
