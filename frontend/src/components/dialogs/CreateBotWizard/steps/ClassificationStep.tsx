import { useEffect, useRef, useState } from 'react'
import { Bot, Users, Loader2, Sparkles, AlertTriangle, Settings } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { useUIStore } from '../../../../stores/ui'
import { classifyPurpose } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

export function ClassificationStep() {
  const {
    form,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    setCreationPath,
    setAIClassification,
    nextStep,
  } = useCreationStore()

  const [hasClassified, setHasClassified] = useState(false)
  const loadInitiatedRef = useRef(false)

  useEffect(() => {
    // If already classified (e.g. user went back and forward), don't re-classify
    if (form.aiClassification || loadInitiatedRef.current) return
    loadInitiatedRef.current = true
    classifyOnMount()
  }, [])

  const classifyOnMount = async () => {
    setGenerating(true)
    setGenerationError(null)

    try {
      const categoryLabel =
        PURPOSE_CATEGORIES.find((c) => c.id === form.purposeCategory)?.label || 'General'
      const result = await classifyPurpose({
        category: categoryLabel,
        description: form.purposeDescription,
      })
      setAIClassification(result)
      setHasClassified(true)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to classify'
      setGenerationError(msg)
    } finally {
      setGenerating(false)
    }
  }

  const handleSelect = (path: 'single' | 'project') => {
    setCreationPath(path)
    // Auto-advance after a brief delay
    setTimeout(() => nextStep(), 150)
  }

  const isNoModel = generationError?.toLowerCase().includes('no ai model configured')

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
          <p className="text-lg font-medium text-[var(--color-text-primary)]">
            Analyzing your request...
          </p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            Figuring out the best setup for you
          </p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  if (generationError && !hasClassified) {
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
              classifyOnMount()
            }}
            className="text-sm text-cachi-400 hover:text-cachi-300"
          >
            Try again
          </button>
        )}
      </div>
    )
  }

  const aiRecommends = form.aiClassification?.classification ?? null

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Based on your description, choose the setup that works best.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Single Bot Card */}
        <button
          onClick={() => handleSelect('single')}
          className={cn(
            'relative flex flex-col items-center gap-4 rounded-xl border-2 p-6 text-left transition-all hover:shadow-lg',
            form.creationPath === 'single'
              ? 'border-cachi-500 bg-cachi-500/10'
              : aiRecommends === 'single'
                ? 'border-cachi-500/50 bg-[var(--color-bg-secondary)]'
                : 'border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]'
          )}
        >
          {aiRecommends === 'single' && (
            <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-cachi-600 px-3 py-0.5 text-[10px] font-semibold text-white">
              AI recommends
            </span>
          )}
          <div
            className={cn(
              'flex h-16 w-16 items-center justify-center rounded-2xl',
              aiRecommends === 'single' ? 'bg-cachi-500/20' : 'bg-[var(--color-bg-primary)]'
            )}
          >
            <Bot className="h-8 w-8 text-cachi-400" />
          </div>
          <div className="text-center">
            <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
              A single bot helper
            </h3>
            <p className="mt-1.5 text-xs text-[var(--color-text-secondary)]">
              One focused assistant for a specific task or role
            </p>
          </div>
        </button>

        {/* Project / Team Card */}
        <button
          onClick={() => handleSelect('project')}
          className={cn(
            'relative flex flex-col items-center gap-4 rounded-xl border-2 p-6 text-left transition-all hover:shadow-lg',
            form.creationPath === 'project'
              ? 'border-cachi-500 bg-cachi-500/10'
              : aiRecommends === 'project'
                ? 'border-cachi-500/50 bg-[var(--color-bg-secondary)]'
                : 'border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]'
          )}
        >
          {aiRecommends === 'project' && (
            <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-cachi-600 px-3 py-0.5 text-[10px] font-semibold text-white">
              AI recommends
            </span>
          )}
          <div
            className={cn(
              'flex h-16 w-16 items-center justify-center rounded-2xl',
              aiRecommends === 'project' ? 'bg-cachi-500/20' : 'bg-[var(--color-bg-primary)]'
            )}
          >
            <Users className="h-8 w-8 text-cachi-400" />
          </div>
          <div className="text-center">
            <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
              A team of bots working together
            </h3>
            <p className="mt-1.5 text-xs text-[var(--color-text-secondary)]">
              Multiple specialized bots in rooms for complex workflows
            </p>
          </div>
        </button>
      </div>

      {form.aiClassification?.reason && (
        <p className="text-center text-xs text-[var(--color-text-tertiary)] italic">
          {form.aiClassification.reason}
        </p>
      )}
    </div>
  )
}
