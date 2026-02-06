import { useEffect, useState } from 'react'
import { Wand2, RefreshCw, Loader2, AlertCircle, Sparkles } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES, COMMUNICATION_STYLES } from '../../../../stores/creation'
import { generateFullPrompt, refinePrompt } from '../../../../api/client'

export function PromptReviewStep() {
  const {
    form,
    updateForm,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    setGeneratedContent,
  } = useCreationStore()

  const [refineInput, setRefineInput] = useState('')
  const [isRefining, setIsRefining] = useState(false)

  // Generate prompt when entering this step if not already generated
  useEffect(() => {
    if (!form.generatedPrompt && !isGenerating) {
      generatePrompt()
    }
  }, [])

  const generatePrompt = async () => {
    setGenerating(true)
    setGenerationError(null)

    try {
      const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label || form.purposeCategory
      const styleLabel = COMMUNICATION_STYLES.find(s => s.id === form.communicationStyle)?.label || form.communicationStyle

      // Use the full prompt generation with all context
      const result = await generateFullPrompt({
        name: form.name,
        name_meaning: form.selectedNameMeaning,
        purpose_category: categoryLabel,
        purpose_description: form.purposeDescription,
        follow_up_answers: form.followUpQuestions
          .filter(q => q.answer.trim())
          .map(q => ({ question: q.question, answer: q.answer })),
        communication_style: styleLabel,
        use_emojis: form.useEmojis,
      })

      setGeneratedContent(
        result.system_prompt,
        result.suggested_name,
        result.suggested_description
      )
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Failed to generate prompt')
    } finally {
      setGenerating(false)
    }
  }

  const handleRefine = async () => {
    if (!refineInput.trim()) return

    setIsRefining(true)
    setGenerationError(null)

    try {
      const result = await refinePrompt({
        current_prompt: form.systemPrompt,
        feedback: refineInput,
      })

      updateForm({ systemPrompt: result.system_prompt })
      setRefineInput('')
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Failed to refine prompt')
    } finally {
      setIsRefining(false)
    }
  }

  if (isGenerating) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-cachi-500/20" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-cachi-500/10">
            <Sparkles className="h-8 w-8 text-cachi-400" />
          </div>
        </div>
        <div className="text-center">
          <p className="text-lg font-medium text-zinc-200">Creating {form.name}'s personality...</p>
          <p className="mt-1 text-sm text-zinc-500">Crafting a unique system prompt just for you</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {generationError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <span className="text-sm text-red-400">{generationError}</span>
          <button
            onClick={generatePrompt}
            className="ml-auto text-sm text-red-400 underline hover:text-red-300"
          >
            Try again
          </button>
        </div>
      )}

      {/* Bot identity header */}
      <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3">
        <div>
          <p className="text-sm text-zinc-500">Personality for</p>
          <p className="text-lg font-bold text-cachi-400">{form.name}</p>
        </div>
        <button
          onClick={generatePrompt}
          className="flex items-center gap-1.5 text-xs text-cachi-400 hover:text-cachi-300"
        >
          <RefreshCw className="h-3 w-3" />
          Regenerate
        </button>
      </div>

      {/* System prompt editor */}
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">
          System Prompt
        </label>
        <textarea
          value={form.systemPrompt}
          onChange={(e) => updateForm({ systemPrompt: e.target.value })}
          rows={8}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 font-mono text-xs leading-relaxed text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
        />
      </div>

      {/* Refine with AI */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="mb-3 flex items-center gap-2">
          <Wand2 className="h-4 w-4 text-cachi-400" />
          <span className="text-sm font-medium text-zinc-300">Refine with AI</span>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={refineInput}
            onChange={(e) => setRefineInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
            placeholder="e.g., 'make it more motivating' or 'add more personality'"
            className="h-9 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
          />
          <button
            onClick={handleRefine}
            disabled={isRefining || !refineInput.trim()}
            className="flex h-9 items-center gap-1.5 rounded-lg bg-cachi-600 px-4 text-sm font-medium text-white hover:bg-cachi-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRefining ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Refine
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
