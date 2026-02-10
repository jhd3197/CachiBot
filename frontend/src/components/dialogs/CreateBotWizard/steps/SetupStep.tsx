import { useEffect, useRef } from 'react'
import {
  Loader2,
  Sparkles,
  UserCircle,
  ListChecks,
  CalendarClock,
  Check,
} from 'lucide-react'
import { useCreationStore } from '../../../../stores/creation'
import type { SuggestedTodoItem, SuggestedScheduleItem } from '../../../../stores/creation'
import { analyzeCreationContext } from '../../../../api/client'

export function SetupStep() {
  const {
    form,
    isGenerating,
    setGenerating,
    setGenerationError,
    updateForm,
  } = useCreationStore()

  const loadInitiatedRef = useRef(false)

  useEffect(() => {
    // Only run analysis once, when entering the step with no existing data
    if (!loadInitiatedRef.current && !form.userContext && !isGenerating) {
      loadInitiatedRef.current = true
      runAnalysis()
    }
  }, [])

  const runAnalysis = async () => {
    setGenerating(true)
    setGenerationError(null)

    try {
      const result = await analyzeCreationContext({
        purpose_category: form.purposeCategory,
        purpose_description: form.purposeDescription,
        follow_up_answers: form.followUpQuestions
          .filter((q) => q.answer.trim())
          .map((q) => ({ question: q.question, answer: q.answer })),
        system_prompt: form.systemPrompt,
        bot_name: form.name,
      })

      updateForm({
        userContext: result.user_context,
        suggestedTodos: result.suggested_todos.map((t) => ({
          ...t,
          enabled: true,
        })),
        suggestedSchedules: result.suggested_schedules.map((s) => ({
          ...s,
          enabled: true,
        })),
      })
    } catch (error) {
      setGenerationError(
        error instanceof Error ? error.message : 'Failed to analyze context'
      )
    } finally {
      setGenerating(false)
    }
  }

  const toggleTodo = (index: number) => {
    const updated = form.suggestedTodos.map((t: SuggestedTodoItem, i: number) =>
      i === index ? { ...t, enabled: !t.enabled } : t
    )
    updateForm({ suggestedTodos: updated })
  }

  const toggleSchedule = (index: number) => {
    const updated = form.suggestedSchedules.map((s: SuggestedScheduleItem, i: number) =>
      i === index ? { ...s, enabled: !s.enabled } : s
    )
    updateForm({ suggestedSchedules: updated })
  }

  // Loading state
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
          <p className="text-lg font-medium text-zinc-200">
            Analyzing your answers...
          </p>
          <p className="mt-1 text-sm text-zinc-500">
            Extracting what {form.name} should know about you
          </p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* User Context Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
          <UserCircle className="h-4 w-4 text-cachi-400" />
          What {form.name} knows about you
        </div>
        <textarea
          value={form.userContext}
          onChange={(e) => updateForm({ userContext: e.target.value })}
          rows={5}
          placeholder="Information about you that the bot should always remember..."
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-cachi-500"
        />
        <p className="text-xs text-zinc-600">
          This will be saved as Custom Instructions — your bot will always have
          this context.
        </p>
      </div>

      {/* Suggested Todos */}
      {form.suggestedTodos.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
            <ListChecks className="h-4 w-4 text-cachi-400" />
            Suggested todos
          </div>
          <div className="space-y-2">
            {form.suggestedTodos.map((todo: SuggestedTodoItem, index: number) => (
              <button
                key={index}
                type="button"
                onClick={() => toggleTodo(index)}
                className="flex w-full items-start gap-3 rounded-lg border border-zinc-700 bg-zinc-800/50 p-3 text-left transition-colors hover:border-zinc-600"
              >
                <div
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors ${
                    todo.enabled
                      ? 'border-cachi-500 bg-cachi-500 text-white'
                      : 'border-zinc-600 bg-zinc-800'
                  }`}
                >
                  {todo.enabled && <Check className="h-3 w-3" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-medium ${
                      todo.enabled ? 'text-zinc-200' : 'text-zinc-500 line-through'
                    }`}
                  >
                    {todo.title}
                  </p>
                  {todo.notes && (
                    <p className="mt-0.5 text-xs text-zinc-500">{todo.notes}</p>
                  )}
                </div>
              </button>
            ))}
          </div>
          <p className="text-xs text-zinc-600">
            Checked items will be created as todos for your bot.
          </p>
        </div>
      )}

      {/* Suggested Schedules */}
      {form.suggestedSchedules.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
            <CalendarClock className="h-4 w-4 text-cachi-400" />
            Suggested recurring tasks
          </div>
          <div className="space-y-2">
            {form.suggestedSchedules.map(
              (schedule: SuggestedScheduleItem, index: number) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => toggleSchedule(index)}
                  className="flex w-full items-start gap-3 rounded-lg border border-zinc-700 bg-zinc-800/50 p-3 text-left transition-colors hover:border-zinc-600"
                >
                  <div
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors ${
                      schedule.enabled
                        ? 'border-cachi-500 bg-cachi-500 text-white'
                        : 'border-zinc-600 bg-zinc-800'
                    }`}
                  >
                    {schedule.enabled && <Check className="h-3 w-3" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm font-medium ${
                        schedule.enabled
                          ? 'text-zinc-200'
                          : 'text-zinc-500 line-through'
                      }`}
                    >
                      {schedule.name}
                    </p>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-500">
                      <span className="rounded bg-zinc-700/50 px-1.5 py-0.5">
                        {schedule.frequency}
                      </span>
                      {schedule.description && (
                        <span>{schedule.description}</span>
                      )}
                    </div>
                  </div>
                </button>
              )
            )}
          </div>
          <p className="text-xs text-zinc-600">
            Checked items will be created as scheduled tasks.
          </p>
        </div>
      )}

      {/* Empty state if nothing was found */}
      {!form.userContext &&
        form.suggestedTodos.length === 0 &&
        form.suggestedSchedules.length === 0 && (
          <div className="rounded-lg border border-zinc-700/50 bg-zinc-800/30 p-6 text-center">
            <p className="text-sm text-zinc-400">
              No additional context was extracted. You can add custom
              instructions manually after creating the bot.
            </p>
          </div>
        )}
    </div>
  )
}
