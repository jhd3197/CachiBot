import { useEffect } from 'react'
import { useCreationStore } from '../../../../stores/creation'
import { useModelsStore } from '../../../../stores/models'
import { BotIconRenderer, BOT_ICON_OPTIONS } from '../../../common/BotIconRenderer'
import { ModelSelect } from '../../../common/ModelSelect'
import { cn } from '../../../../lib/utils'
import type { BotIcon } from '../../../../types'

const COLOR_OPTIONS = [
  '#22c55e', // green
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#f59e0b', // amber
  '#ef4444', // red
  '#06b6d4', // cyan
  '#84cc16', // lime
]

export function AppearanceStep() {
  const { form, updateForm } = useCreationStore()
  const { defaultModel } = useModelsStore()

  // Pre-fill model from system default when empty
  useEffect(() => {
    if (!form.model && defaultModel) {
      updateForm({ model: defaultModel })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultModel])

  return (
    <div className="space-y-6">
      {/* Name and Description */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            Bot Name
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => updateForm({ name: e.target.value })}
            placeholder="My Awesome Bot"
            className="h-10 w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            Description
          </label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => updateForm({ description: e.target.value })}
            placeholder="What does this bot do?"
            className="h-10 w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
          />
        </div>
      </div>

      {/* Icon and Color */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            Icon
          </label>
          <div className="flex flex-wrap gap-2">
            {BOT_ICON_OPTIONS.map((option) => (
              <button
                key={option.id}
                onClick={() => updateForm({ icon: option.id as BotIcon })}
                title={option.label}
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-lg border transition-all',
                  form.icon === option.id
                    ? 'border-cachi-500 bg-cachi-500/20'
                    : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]'
                )}
              >
                <BotIconRenderer icon={option.id} size={20} />
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            Color
          </label>
          <div className="flex flex-wrap gap-2">
            {COLOR_OPTIONS.map((color) => (
              <button
                key={color}
                onClick={() => updateForm({ color })}
                className={cn(
                  'h-10 w-10 rounded-lg border-2 transition-all',
                  form.color === color
                    ? 'border-white scale-110'
                    : 'border-transparent hover:scale-105'
                )}
                style={{ backgroundColor: color }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Model Selection */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            AI Model
          </label>
          <ModelSelect
            value={form.model}
            onChange={(model) => updateForm({ model })}
            placeholder="Select AI Model"
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            Utility Model (optional)
          </label>
          <ModelSelect
            value={form.utilityModel}
            onChange={(model) => updateForm({ utilityModel: model })}
            placeholder="Use system default"
            filter={(m) => !m.supports_image_generation && !m.supports_audio}
          />
          <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
            Cheap/fast model for background tasks
          </p>
        </div>
      </div>

      {/* System Prompt (for blank/import methods or quick edit) */}
      {(form.method === 'blank' || !form.generatedPrompt) && (
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
            System Prompt
          </label>
          <textarea
            value={form.systemPrompt}
            onChange={(e) => updateForm({ systemPrompt: e.target.value })}
            placeholder="Define the bot's personality and behavior..."
            rows={4}
            className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
          />
        </div>
      )}

      {/* Preview */}
      <div className="flex items-center gap-4 rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-4">
        <div
          className="flex h-14 w-14 items-center justify-center rounded-xl"
          style={{ backgroundColor: form.color + '20' }}
        >
          <BotIconRenderer icon={form.icon} size={28} color={form.color} />
        </div>
        <div>
          <h3 className="font-semibold text-[var(--color-text-primary)]">
            {form.name || 'Bot Name'}
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            {form.description || 'Bot description'}
          </p>
        </div>
      </div>
    </div>
  )
}
