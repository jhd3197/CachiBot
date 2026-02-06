import { Check, Wrench, MessageSquare, Sparkles } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES, COMMUNICATION_STYLES } from '../../../../stores/creation'
import { BotIconRenderer } from '../../../common/BotIconRenderer'

export function ConfirmStep() {
  const { form } = useCreationStore()

  const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label
  const styleLabel = COMMUNICATION_STYLES.find(s => s.id === form.communicationStyle)?.label

  return (
    <div className="space-y-6">
      {/* Bot preview card */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <div className="flex items-start gap-4">
          <div
            className="flex h-16 w-16 items-center justify-center rounded-xl"
            style={{ backgroundColor: form.color + '20' }}
          >
            <BotIconRenderer icon={form.icon} size={32} color={form.color} />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold text-zinc-100">{form.name || 'New Bot'}</h2>
            <p className="mt-1 text-sm text-zinc-500">
              {form.description || 'A new AI assistant'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {form.model && (
                <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-400">
                  {form.model}
                </span>
              )}
              {form.tools.length > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-400">
                  <Wrench className="h-3 w-3" />
                  {form.tools.length} tools
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Configuration summary */}
      {form.method === 'ai-assisted' && (
        <div className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <Sparkles className="h-4 w-4 text-cachi-400" />
            AI-Generated Configuration
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {categoryLabel && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3">
                <span className="text-xs text-zinc-500">Purpose</span>
                <p className="mt-0.5 text-sm text-zinc-200">{categoryLabel}</p>
              </div>
            )}
            {styleLabel && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3">
                <span className="text-xs text-zinc-500">Style</span>
                <p className="mt-0.5 text-sm text-zinc-200">{styleLabel}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* System prompt preview */}
      <div className="space-y-2">
        <h3 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <MessageSquare className="h-4 w-4 text-zinc-500" />
          System Prompt
        </h3>
        <div className="max-h-40 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
          <p className="whitespace-pre-wrap text-sm text-zinc-400">
            {form.systemPrompt || '(No system prompt configured)'}
          </p>
        </div>
      </div>

      {/* Tools list */}
      {form.tools.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <Wrench className="h-4 w-4 text-zinc-500" />
            Enabled Tools
          </h3>
          <div className="flex flex-wrap gap-2">
            {form.tools.map((tool) => (
              <span
                key={tool}
                className="flex items-center gap-1.5 rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300"
              >
                <Check className="h-3 w-3 text-cachi-400" />
                {tool.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Ready to create */}
      <div className="flex items-center gap-3 rounded-lg border border-cachi-500/30 bg-cachi-500/10 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cachi-600">
          <Check className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="font-medium text-cachi-400">Ready to create</p>
          <p className="text-xs text-cachi-400/70">
            Click "Create Bot" to add this bot to your collection
          </p>
        </div>
      </div>
    </div>
  )
}
