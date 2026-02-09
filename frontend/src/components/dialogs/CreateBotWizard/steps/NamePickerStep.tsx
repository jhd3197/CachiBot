import { useEffect, useRef } from 'react'
import { Loader2, RefreshCw, Sparkles, Check } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { streamBotNamesWithMeanings } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

export function NamePickerStep() {
  const {
    form,
    updateForm,
    isGenerating,
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
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const loadNameSuggestions = async () => {
    // Abort any in-flight request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setGenerating(true)
    setGenerationError(null)

    // Clear existing suggestions for a fresh batch
    const store = useCreationStore.getState()
    // Track names added during this batch for auto-select
    const newNames: Array<{ name: string; meaning: string }> = []
    let isFirstName = true

    try {
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label || form.purposeCategory

      await streamBotNamesWithMeanings(
        {
          count: 4,
          exclude: getExcludedNames(),
          purpose: `${categoryLabel}: ${form.purposeDescription}`,
        },
        {
          onName: (nameData) => {
            newNames.push(nameData)
            // Append name incrementally to the store
            useCreationStore.setState((state) => ({
              form: {
                ...state.form,
                nameSuggestions: [...state.form.nameSuggestions, { name: nameData.name, meaning: nameData.meaning }],
              },
            }))

            // Auto-select the first name if none selected
            if (isFirstName && !store.form.name) {
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

  if (isGenerating && form.nameSuggestions.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-cachi-500/20" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-cachi-500/10">
            <Sparkles className="h-8 w-8 text-cachi-400" />
          </div>
        </div>
        <div className="text-center">
          <p className="text-lg font-medium text-zinc-200">Finding the perfect name...</p>
          <p className="mt-1 text-sm text-zinc-500">Each name has a special meaning</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cachi-400" />
          <span className="text-sm font-medium text-zinc-300">Pick a name that resonates with you</span>
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
                : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600 hover:bg-zinc-800'
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
              form.name === suggestion.name ? 'text-cachi-300' : 'text-zinc-100'
            )}>
              {suggestion.name}
            </h4>
            <p className="text-xs leading-relaxed text-zinc-400">
              {suggestion.meaning}
            </p>
          </button>
        ))}

        {/* Placeholder cards while streaming */}
        {isGenerating && form.nameSuggestions.length < 4 &&
          Array.from({ length: 4 - form.nameSuggestions.length }).map((_, i) => (
            <div
              key={`placeholder-${i}`}
              className="flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-800/30 p-4"
              style={{ minHeight: '100px' }}
            >
              <Loader2 className="h-5 w-5 animate-spin text-zinc-600" />
            </div>
          ))
        }
      </div>

      {/* Custom name input */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-zinc-800" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-zinc-900 px-3 text-xs text-zinc-600">or use your own</span>
        </div>
      </div>

      <input
        type="text"
        value={form.name}
        onChange={(e) => updateForm({ name: e.target.value, selectedNameMeaning: 'A custom name you chose' })}
        placeholder="Type a custom name..."
        className="h-11 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-center text-lg font-medium text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
      />

      {/* Selected name preview */}
      {form.name && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-center">
          <p className="text-sm text-zinc-500">Your bot will be called</p>
          <p className="mt-1 text-2xl font-bold text-cachi-400">{form.name}</p>
          {form.selectedNameMeaning && (
            <p className="mt-2 text-xs text-zinc-500 italic">"{form.selectedNameMeaning}"</p>
          )}
        </div>
      )}
    </div>
  )
}
