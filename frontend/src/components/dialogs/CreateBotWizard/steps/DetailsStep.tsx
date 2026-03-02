import { useEffect, useRef, useState } from 'react'
import { Loader2, HelpCircle, Sparkles, Settings, AlertTriangle } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { useModelsStore } from '../../../../stores/models'
import { useUIStore } from '../../../../stores/ui'
import { streamFollowUpQuestions } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

const LOADING_MESSAGES = [
  { title: 'Thinking about what to ask...', sub: 'Tailoring questions to your use case' },
  { title: 'Personalizing your experience...', sub: 'Making sure we ask the right things' },
  { title: 'Almost ready...', sub: 'Putting together thoughtful questions' },
]

/**
 * Parse a placeholder string into 2-3 short suggestion chips.
 * Looks for comma/semicolon separated phrases, or "e.g." / "like" patterns.
 */
function parseSuggestions(placeholder: string): string[] {
  // Try "e.g. X, Y, Z" or "like X, Y, Z"
  const egMatch = placeholder.match(/(?:e\.g\.?|like|such as)\s+(.+)/i)
  const source = egMatch ? egMatch[1] : placeholder

  // Split on commas, semicolons, or " or "
  const parts = source
    .split(/[,;]|\bor\b/)
    .map((s) => s.replace(/[.!?]+$/, '').trim())
    .filter((s) => s.length > 2 && s.length < 60)

  return parts.slice(0, 3)
}

export function DetailsStep() {
  const {
    form,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    updateFollowUpAnswer,
  } = useCreationStore()

  // Track which questions had a chip clicked (to hide chips)
  const [chipUsed, setChipUsed] = useState<Set<string>>(new Set())

  // Guard against StrictMode double-fire
  const loadInitiatedRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (form.followUpQuestions.length === 0 && !isGenerating && !loadInitiatedRef.current) {
      loadInitiatedRef.current = true
      loadQuestions()
    }
    // Don't abort on cleanup — StrictMode remounts would kill the in-flight request.
  }, [])

  const loadQuestions = async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setGenerating(true)
    setGenerationError(null)

    try {
      // Read fresh state — closure values may be stale
      const freshForm = useCreationStore.getState().form
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === freshForm.purposeCategory)?.label || 'General'

      const mode = freshForm.creationPath === 'single' ? 'task-focused' : 'user-focused'

      await streamFollowUpQuestions(
        {
          category: categoryLabel,
          description: freshForm.purposeDescription,
          mode,
        },
        {
          onQuestion: (question) => {
            // Append each question incrementally
            useCreationStore.setState((state) => ({
              form: {
                ...state.form,
                followUpQuestions: [
                  ...state.form.followUpQuestions,
                  { ...question, answer: '' },
                ],
              },
            }))
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
        setGenerationError(error instanceof Error ? error.message : 'Failed to generate questions')
        setGenerating(false)
      }
    }
  }

  const handleChipClick = (questionId: string, suggestion: string) => {
    updateFollowUpAnswer(questionId, suggestion)
    setChipUsed((prev) => new Set(prev).add(questionId))
  }

  // Cycle through loading messages while waiting
  const [msgIndex, setMsgIndex] = useState(0)
  useEffect(() => {
    if (!isGenerating || form.followUpQuestions.length > 0) return
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % LOADING_MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [isGenerating, form.followUpQuestions.length])

  const { defaultUtilityModel } = useModelsStore()
  const hasUtilityModel = !!defaultUtilityModel

  if (isGenerating && form.followUpQuestions.length === 0) {
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

  if (generationError && !isGenerating && form.followUpQuestions.length === 0) {
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
              loadQuestions()
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
      <div className="rounded-lg border border-cachi-500/20 bg-cachi-500/5 p-4">
        <div className="flex items-start gap-3">
          <HelpCircle className="mt-0.5 h-5 w-5 shrink-0 text-cachi-400" />
          <div>
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              {form.creationPath === 'single'
                ? `Help us refine what ${form.name || 'your bot'} should do`
                : `Help ${form.name} understand you better`}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              {form.creationPath === 'single'
                ? 'These answers help tailor the bot to your specific needs.'
                : 'These answers will help create a personalized assistant just for you.'}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-5">
        {form.followUpQuestions.map((q, index) => {
          const suggestions = parseSuggestions(q.placeholder)
          const showChips = q.answer === '' && !chipUsed.has(q.id) && suggestions.length > 0

          return (
            <div
              key={q.id}
              className="group animate-in fade-in slide-in-from-bottom-2 duration-300"
              style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}
            >
              <label className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--color-text-primary)]">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cachi-600/20 text-xs text-cachi-400">
                  {index + 1}
                </span>
                {q.question}
              </label>
              <textarea
                value={q.answer}
                onChange={(e) => updateFollowUpAnswer(q.id, e.target.value)}
                placeholder={q.placeholder}
                rows={2}
                className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none transition-colors focus:border-[var(--color-border-focus)]"
              />
              {showChips && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => handleChipClick(q.id, s)}
                      className={cn(
                        'rounded-full border border-[var(--color-border-primary)] bg-[var(--card-bg)] px-3 py-1 text-xs text-[var(--color-text-secondary)]',
                        'transition-all hover:border-cachi-500 hover:text-cachi-400'
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {/* Placeholder while streaming */}
        {isGenerating && form.followUpQuestions.length < 3 && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        )}
      </div>

      <p className="text-center text-xs text-[var(--color-text-tertiary)]">
        Don't worry, you can always refine your bot later
      </p>
    </div>
  )
}
