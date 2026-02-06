import { useEffect } from 'react'
import { Loader2, RefreshCw, Sparkles, Check } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { generateBotNamesWithMeanings } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

export function NamePickerStep() {
  const {
    form,
    updateForm,
    isGenerating,
    setGenerating,
    setGenerationError,
    setNameSuggestions,
    selectName,
  } = useCreationStore()

  // Load name suggestions when entering step
  useEffect(() => {
    if (form.nameSuggestions.length === 0 && !isGenerating) {
      loadNameSuggestions()
    }
  }, [])

  const loadNameSuggestions = async () => {
    setGenerating(true)
    setGenerationError(null)

    try {
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label || form.purposeCategory

      const names = await generateBotNamesWithMeanings({
        count: 4,
        purpose: `${categoryLabel}: ${form.purposeDescription}`,
      })
      setNameSuggestions(names)

      // Auto-select the first name if no name selected yet
      if (!form.name && names.length > 0) {
        selectName(names[0].name, names[0].meaning)
      }
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Failed to generate names')
    } finally {
      setGenerating(false)
    }
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
          onClick={loadNameSuggestions}
          disabled={isGenerating}
          className="flex items-center gap-1.5 text-xs text-cachi-400 hover:text-cachi-300 disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3 w-3', isGenerating && 'animate-spin')} />
          New suggestions
        </button>
      </div>

      {/* Name cards */}
      <div className="grid grid-cols-2 gap-3">
        {form.nameSuggestions.map((suggestion) => (
          <button
            key={suggestion.name}
            onClick={() => handleSelectName(suggestion.name, suggestion.meaning)}
            disabled={isGenerating}
            className={cn(
              'group relative rounded-xl border p-4 text-left transition-all',
              form.name === suggestion.name
                ? 'border-cachi-500 bg-cachi-500/10 ring-1 ring-cachi-500/50'
                : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600 hover:bg-zinc-800'
            )}
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
