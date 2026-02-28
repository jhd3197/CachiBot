import { useEffect, useRef, useState } from 'react'
import { Loader2, HelpCircle, Sparkles, Settings, AlertTriangle } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { useModelsStore } from '../../../../stores/models'
import { useUIStore } from '../../../../stores/ui'
import { streamProjectFollowUpQuestions } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

const LOADING_MESSAGES = [
  { title: 'Analyzing your project...', sub: 'Understanding what your team needs' },
  { title: 'Designing your workflow...', sub: 'Thinking about roles and collaboration' },
  { title: 'Almost ready...', sub: 'Preparing project-specific questions' },
]

function parseSuggestions(placeholder: string): string[] {
  const egMatch = placeholder.match(/(?:e\.g\.?|like|such as)\s+(.+)/i)
  const source = egMatch ? egMatch[1] : placeholder
  const parts = source
    .split(/[,;]|\bor\b/)
    .map((s) => s.replace(/[.!?]+$/, '').trim())
    .filter((s) => s.length > 2 && s.length < 60)
  return parts.slice(0, 3)
}

export function ProjectDetailsStep() {
  const {
    form,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    updateProjectFollowUpAnswer,
  } = useCreationStore()

  const [chipUsed, setChipUsed] = useState<Set<string>>(new Set())
  const loadInitiatedRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (form.projectFollowUpQuestions.length === 0 && !isGenerating && !loadInitiatedRef.current) {
      loadInitiatedRef.current = true
      loadQuestions()
    }
  }, [])

  const loadQuestions = async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setGenerating(true)
    setGenerationError(null)

    try {
      const freshForm = useCreationStore.getState().form
      const categoryLabel =
        PURPOSE_CATEGORIES.find((c) => c.id === freshForm.purposeCategory)?.label || 'General'

      await streamProjectFollowUpQuestions(
        {
          category: categoryLabel,
          description: freshForm.purposeDescription,
        },
        {
          onQuestion: (question) => {
            useCreationStore.setState((state) => ({
              form: {
                ...state.form,
                projectFollowUpQuestions: [
                  ...state.form.projectFollowUpQuestions,
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
        setGenerationError(
          error instanceof Error ? error.message : 'Failed to generate questions',
        )
        setGenerating(false)
      }
    }
  }

  const handleChipClick = (questionId: string, suggestion: string) => {
    updateProjectFollowUpAnswer(questionId, suggestion)
    setChipUsed((prev) => new Set(prev).add(questionId))
  }

  const [msgIndex, setMsgIndex] = useState(0)
  useEffect(() => {
    if (!isGenerating || form.projectFollowUpQuestions.length > 0) return
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % LOADING_MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [isGenerating, form.projectFollowUpQuestions.length])

  const { defaultUtilityModel } = useModelsStore()
  const hasUtilityModel = !!defaultUtilityModel

  if (isGenerating && form.projectFollowUpQuestions.length === 0) {
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

  if (generationError && !isGenerating && form.projectFollowUpQuestions.length === 0) {
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
            onClick={() => useUIStore.getState().setSettingsOpen(true)}
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
              Tell us about your project
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              These answers help us design the right team of bots and rooms for you.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-5">
        {form.projectFollowUpQuestions.map((q, index) => {
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
                onChange={(e) => updateProjectFollowUpAnswer(q.id, e.target.value)}
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
                        'transition-all hover:border-cachi-500 hover:text-cachi-400',
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

        {isGenerating && form.projectFollowUpQuestions.length < 3 && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        )}
      </div>

      <p className="text-center text-xs text-[var(--color-text-tertiary)]">
        The more detail you provide, the better your team will be designed
      </p>
    </div>
  )
}
