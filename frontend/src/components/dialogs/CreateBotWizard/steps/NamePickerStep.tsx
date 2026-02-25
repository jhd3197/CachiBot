import { useEffect, useRef, useState } from 'react'
import { Loader2, RefreshCw, Sparkles, Check, Settings, AlertTriangle } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { useModelsStore } from '../../../../stores/models'
import { useUIStore } from '../../../../stores/ui'
import { streamBotNamesWithMeanings } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

const LOADING_MESSAGES = [
  { title: 'Brainstorming names...', sub: 'Finding names that match your bot\'s personality' },
  { title: 'Exploring cultures & languages...', sub: 'Looking for meaningful names from around the world' },
  { title: 'Getting creative...', sub: 'Mixing real names with purpose-driven ideas' },
  { title: 'Almost there...', sub: 'Polishing the best candidates for you' },
]

export function NamePickerStep() {
  const {
    form,
    updateForm,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    selectName,
    getExcludedNames,
  } = useCreationStore()

  // Guard against StrictMode double-fire
  const loadInitiatedRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (form.nameSuggestions.length === 0 && !isGenerating && !loadInitiatedRef.current) {
      loadInitiatedRef.current = true
      loadNameSuggestions()
    }
    // Don't abort on cleanup — StrictMode remounts would kill the in-flight request.
    // Abort only happens when starting a new request (inside loadNameSuggestions).
  }, [])

  const loadNameSuggestions = async () => {
    // Abort any in-flight request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setGenerating(true)
    setGenerationError(null)

    // Read fresh state — closure values may be stale after refresh
    const freshForm = useCreationStore.getState().form
    let isFirstName = true

    try {
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === freshForm.purposeCategory)?.label || ''
      const purposeParts = [categoryLabel, freshForm.purposeDescription].filter(Boolean)

      await streamBotNamesWithMeanings(
        {
          count: 4,
          exclude: getExcludedNames(),
          purpose: purposeParts.join(': '),
        },
        {
          onName: (nameData) => {
            // Append name incrementally to the store
            useCreationStore.setState((state) => ({
              form: {
                ...state.form,
                nameSuggestions: [...state.form.nameSuggestions, { name: nameData.name, meaning: nameData.meaning }],
              },
            }))

            // Auto-select the first name if none selected
            if (isFirstName && !useCreationStore.getState().form.name) {
              selectName(nameData.name, nameData.meaning)
              isFirstName = false
            }
          },
          onDone: () => {
            setGenerating(false)
          },
          onError: (error) => {
            setGenerationError(error)
            setGenerating(false)
          },
        },
        controller.signal,
      )
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        setGenerationError(error instanceof Error ? error.message : 'Failed to generate names')
        setGenerating(false)
      }
    }
  }

  const handleRefresh = () => {
    // Move current names to excluded before loading new ones
    const currentNames = useCreationStore.getState().form.nameSuggestions
    useCreationStore.setState((state) => ({
      excludedNames: [...new Set([...state.excludedNames, ...currentNames.map(s => s.name)])],
      form: { ...state.form, nameSuggestions: [] },
    }))
    loadNameSuggestions()
  }

  const handleSelectName = (name: string, meaning: string) => {
    selectName(name, meaning)
  }

  // Cycle through loading messages while waiting
  const [msgIndex, setMsgIndex] = useState(0)
  useEffect(() => {
    if (!isGenerating || form.nameSuggestions.length > 0) return
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % LOADING_MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [isGenerating, form.nameSuggestions.length])

  const { defaultUtilityModel } = useModelsStore()
  const hasUtilityModel = !!defaultUtilityModel

  if (isGenerating && form.nameSuggestions.length === 0) {
    const msg = LOADING_MESSAGES[msgIndex]
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-cachi-500/20" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-cachi-500/10">
            <Sparkles className="h-8 w-8 text-cachi-400" />
          </div>
        </div>
        <div className="text-center transition-opacity duration-500">
          <p className="text-lg font-medium text-[var(--color-text-primary)]">{msg.title}</p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{msg.sub}</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
        {!hasUtilityModel && (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-[var(--color-text-tertiary)]">
            <Settings className="h-3 w-3" />
            Tip: Set a fast utility model in Settings to speed up generation
          </p>
        )}
      </div>
    )
  }

  const isNoModel = generationError?.toLowerCase().includes('no ai model configured')

  if (generationError && !isGenerating && form.nameSuggestions.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-8 w-8 text-red-400" />
        </div>
        <div className="text-center">
          <p className="text-lg font-medium text-[var(--color-text-primary)]">
            {isNoModel ? 'No AI Model Configured' : 'Something went wrong'}
          </p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            {isNoModel
              ? 'You need to set a default model before creating a bot.'
              : generationError}
          </p>
        </div>
        {isNoModel ? (
          <button
            onClick={() => {
              useUIStore.getState().setSettingsOpen(true)
            }}
            className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cachi-500"
          >
            <Settings className="h-4 w-4" />
            Open Settings
          </button>
        ) : (
          <button
            onClick={() => {
              setGenerationError(null)
              loadInitiatedRef.current = false
              loadNameSuggestions()
            }}
            className="text-sm text-cachi-400 hover:text-cachi-300"
          >
            Try again
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cachi-400" />
          <span className="text-sm font-medium text-[var(--color-text-primary)]">Pick a name that resonates with you</span>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isGenerating}
          className="flex items-center gap-1.5 text-xs text-cachi-400 hover:text-cachi-300 disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3 w-3', isGenerating && 'animate-spin')} />
          New suggestions
        </button>
      </div>

      {/* Name cards */}
      <div className="grid grid-cols-2 gap-3">
        {form.nameSuggestions.map((suggestion, index) => (
          <button
            key={suggestion.name}
            onClick={() => handleSelectName(suggestion.name, suggestion.meaning)}
            disabled={isGenerating && form.nameSuggestions.length < 4}
            className={cn(
              'group relative rounded-xl border p-4 text-left transition-all',
              'animate-in fade-in slide-in-from-bottom-2 duration-300',
              form.name === suggestion.name
                ? 'border-cachi-500 bg-cachi-500/10 ring-1 ring-cachi-500/50'
                : 'border-[var(--color-border-secondary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]'
            )}
            style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}
          >
            {form.name === suggestion.name && (
              <div className="absolute right-3 top-3">
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-cachi-500">
                  <Check className="h-3 w-3 text-white" />
                </div>
              </div>
            )}
            <h4 className={cn(
              'mb-2 text-xl font-bold',
              form.name === suggestion.name ? 'text-cachi-300' : 'text-[var(--color-text-primary)]'
            )}>
              {suggestion.name}
            </h4>
            <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
              {suggestion.meaning}
            </p>
          </button>
        ))}

        {/* Placeholder cards while streaming */}
        {isGenerating && form.nameSuggestions.length < 4 &&
          Array.from({ length: 4 - form.nameSuggestions.length }).map((_, i) => (
            <div
              key={`placeholder-${i}`}
              className="flex items-center justify-center rounded-xl border border-[var(--color-border-primary)] bg-[var(--card-bg)] p-4"
              style={{ minHeight: '100px' }}
            >
              <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-tertiary)]" />
            </div>
          ))
        }
      </div>

      {/* Custom name input */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[var(--color-border-primary)]" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-[var(--color-bg-primary)] px-3 text-xs text-[var(--color-text-tertiary)]">or use your own</span>
        </div>
      </div>

      <input
        type="text"
        value={form.name}
        onChange={(e) => updateForm({ name: e.target.value, selectedNameMeaning: 'A custom name you chose' })}
        placeholder="Type a custom name..."
        className="h-11 w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 text-center text-lg font-medium text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
      />

      {/* Selected name preview */}
      {form.name && (
        <div className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-4 text-center">
          <p className="text-sm text-[var(--color-text-secondary)]">Your bot will be called</p>
          <p className="mt-1 text-2xl font-bold text-cachi-400">{form.name}</p>
          {form.selectedNameMeaning && (
            <p className="mt-2 text-xs text-[var(--color-text-secondary)] italic">"{form.selectedNameMeaning}"</p>
          )}
        </div>
      )}
    </div>
  )
}
