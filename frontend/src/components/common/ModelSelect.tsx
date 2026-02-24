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
  cachibot: 'CachiBot',
}

/** Providers that should appear at the top of the list. */
const FEATURED_PROVIDERS = new Set(['cachibot'])

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
  filter?: (model: import('../../api/models').ModelInfo) => boolean
  /** Override model groups instead of using the default store groups */
  groups?: import('../../api/models').ModelsGrouped
}

export function ModelSelect({
  value,
  onChange,
  placeholder = 'System Default',
  className = '',
  filter: filterFn,
  groups: groupsOverride,
}: ModelSelectProps) {
  const store = useModelsStore()
  const { refresh, loading } = store
  const groups = groupsOverride ?? store.groups
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
    const result: typeof groups = {}
    for (const [provider, items] of Object.entries(groups)) {
      let matches = items
      // Apply external filter if provided
      if (filterFn) {
        matches = matches.filter(filterFn)
      }
      // Apply search filter
      if (q) {
        matches = matches.filter(
          (m) =>
            m.id.toLowerCase().includes(q) ||
            provider.toLowerCase().includes(q)
        )
      }
      if (matches.length > 0) result[provider] = matches
    }
    return result
  }, [groups, search, filterFn])

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
    <div className={cn('model-select', className)}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          setOpen(!open)
          setSearch('')
          setManualMode(false)
        }}
        className="model-select__trigger"
      >
        <span
          className={cn(
            'model-select__trigger-text',
            value && 'model-select__trigger-text--value'
          )}
        >
          {value || placeholder}
        </span>
        <ChevronDown className="model-select__trigger-chevron h-4 w-4" />
      </button>

      {open &&
        createPortal(
          <div
            ref={dropdownRef}
            className="model-select__dropdown"
            style={{ top: pos.top, left: pos.left, width: Math.max(pos.width, 300) }}
          >
            {manualMode ? (
              /* Manual input mode */
              <div className="model-select__manual">
                <p className="model-select__manual-hint">
                  Enter model in provider/model format
                </p>
                <div className="model-select__manual-form">
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
                    className="model-select__manual-input"
                  />
                  <button
                    type="button"
                    onClick={handleManualSubmit}
                    disabled={!manualValue.trim()}
                    className="model-select__manual-submit"
                  >
                    Set
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Search input */}
                <div className="model-select__search">
                  <div className="model-select__search-wrap">
                    <Search className="model-select__search-icon h-3.5 w-3.5" />
                    <input
                      ref={searchRef}
                      type="text"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search models..."
                      className="model-select__search-input"
                    />
                  </div>
                </div>

                {/* Model list */}
                <div className="model-select__list">
                  {/* Loading state */}
                  {loading && (
                    <div className="model-select__loading">
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
                        'model-select__item model-select__item--default',
                        !value && 'model-select__item--selected'
                      )}
                    >
                      <span>{placeholder}</span>
                      {!value && <Check className="model-select__check h-3.5 w-3.5" />}
                    </button>
                  )}

                  {!loading &&
                    Object.entries(filtered)
                      .sort(([a], [b]) => {
                        const aFeatured = FEATURED_PROVIDERS.has(a)
                        const bFeatured = FEATURED_PROVIDERS.has(b)
                        if (aFeatured !== bFeatured) return aFeatured ? -1 : 1
                        return a.localeCompare(b)
                      })
                      .map(([provider, items]) => {
                        const isFeatured = FEATURED_PROVIDERS.has(provider)
                        return (
                        <div key={provider} className={cn(
                          'model-select__group',
                          isFeatured && 'model-select__group--featured'
                        )}>
                          <div className="model-select__group-header">
                            {providerLabel(provider)}
                            <span className="model-select__group-count">{items.length}</span>
                          </div>
                          {items.map((m) => {
                            const isSelected = value === m.id
                            const ctx = formatTokens(m.context_window)
                            const modIn = m.modalities_input ?? []
                            const modOut = m.modalities_output ?? []
                            const hasVision = modIn.includes('image') || m.supports_vision
                            const hasAudioIn = modIn.includes('audio')
                            const hasVideoIn = modIn.includes('video')
                            const hasImgGen = modOut.includes('image') || m.supports_image_generation
                            const hasAudioOut = modOut.includes('audio') || m.supports_audio
                            return (
                              <button
                                key={m.id}
                                type="button"
                                onClick={() => {
                                  onChange(m.id)
                                  setOpen(false)
                                }}
                                className={cn(
                                  'model-select__item',
                                  isSelected && 'model-select__item--selected'
                                )}
                              >
                                <span className="model-select__item-id">
                                  {m.id}
                                </span>
                                <span className="model-select__item-meta">
                                  {ctx && (
                                    <span className="model-select__item-ctx">
                                      {ctx}
                                    </span>
                                  )}
                                  {hasVision && (
                                    <span className="model-select__badge model-select__badge--vision">
                                      vision
                                    </span>
                                  )}
                                  {hasAudioIn && (
                                    <span className="model-select__badge model-select__badge--audio-in">
                                      audio
                                    </span>
                                  )}
                                  {hasVideoIn && (
                                    <span className="model-select__badge model-select__badge--video">
                                      video
                                    </span>
                                  )}
                                  {hasImgGen && (
                                    <span className="model-select__badge model-select__badge--img-gen">
                                      img gen
                                    </span>
                                  )}
                                  {hasAudioOut && (
                                    <span className="model-select__badge model-select__badge--audio-out">
                                      tts
                                    </span>
                                  )}
                                  {m.supports_tool_use && (
                                    <span className="model-select__badge model-select__badge--tools">
                                      tools
                                    </span>
                                  )}
                                  {m.is_reasoning && (
                                    <span className="model-select__badge model-select__badge--reasoning">
                                      reasoning
                                    </span>
                                  )}
                                  {isSelected && (
                                    <Check className="model-select__check h-3.5 w-3.5" />
                                  )}
                                </span>
                              </button>
                            )
                          })}
                        </div>
                        )
                      })}

                  {!loading && totalCount === 0 && (
                    <div className="model-select__empty">
                      {Object.keys(groups).length === 0
                        ? 'No models available. Configure API keys first.'
                        : 'No models match your search.'}
                    </div>
                  )}
                </div>

                {/* Manual entry option */}
                <div className="model-select__footer">
                  <button
                    type="button"
                    onClick={() => {
                      setManualValue(value || '')
                      setManualMode(true)
                    }}
                    className="model-select__footer-btn"
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
