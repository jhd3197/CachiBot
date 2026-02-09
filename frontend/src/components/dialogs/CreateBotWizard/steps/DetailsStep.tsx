import { useEffect, useRef } from 'react'
import { Loader2, HelpCircle, Sparkles } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { streamFollowUpQuestions } from '../../../../api/client'

export function DetailsStep() {
  const {
    form,
    isGenerating,
    setGenerating,
    setGenerationError,
    updateFollowUpAnswer,
  } = useCreationStore()

  // Guard against StrictMode double-fire
  const loadInitiatedRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (form.followUpQuestions.length === 0 && !isGenerating && !loadInitiatedRef.current) {
      loadInitiatedRef.current = true
      loadQuestions()
    }
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const loadQuestions = async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setGenerating(true)
    setGenerationError(null)

    try {
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label || form.purposeCategory

      await streamFollowUpQuestions(
        {
          category: categoryLabel,
          description: form.purposeDescription,
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

  if (isGenerating && form.followUpQuestions.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-cachi-500/20" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-cachi-500/10">
            <Sparkles className="h-8 w-8 text-cachi-400" />
          </div>
        </div>
        <div className="text-center">
          <p className="text-lg font-medium text-zinc-200">Getting to know you better...</p>
          <p className="mt-1 text-sm text-zinc-500">Creating personalized questions for {form.name}</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-cachi-500/20 bg-cachi-500/5 p-4">
        <div className="flex items-start gap-3">
          <HelpCircle className="mt-0.5 h-5 w-5 shrink-0 text-cachi-400" />
          <div>
            <p className="text-sm font-medium text-zinc-200">
              Help {form.name} understand you better
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              These answers will help create a personalized assistant just for you.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-5">
        {form.followUpQuestions.map((q, index) => (
          <div
            key={q.id}
            className="group animate-in fade-in slide-in-from-bottom-2 duration-300"
            style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}
          >
            <label className="mb-2 flex items-center gap-2 text-sm font-medium text-zinc-300">
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
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-cachi-500"
            />
          </div>
        ))}

        {/* Placeholder while streaming */}
        {isGenerating && form.followUpQuestions.length < 3 && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-zinc-600" />
          </div>
        )}
      </div>

      <p className="text-center text-xs text-zinc-600">
        Don't worry, you can always refine your bot later
      </p>
    </div>
  )
}
