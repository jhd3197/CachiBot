import { Smile, Meh, XCircle } from 'lucide-react'
import { useCreationStore, COMMUNICATION_STYLES, type EmojiPreference } from '../../../../stores/creation'
import { cn } from '../../../../lib/utils'

const EMOJI_OPTIONS: {
  id: EmojiPreference
  label: string
  description: string
  icon: typeof Smile
}[] = [
  {
    id: 'yes',
    label: 'Yes, often',
    description: 'Use emojis freely',
    icon: Smile,
  },
  {
    id: 'sometimes',
    label: 'Sometimes',
    description: 'Use sparingly',
    icon: Meh,
  },
  {
    id: 'no',
    label: 'No emojis',
    description: 'Keep it professional',
    icon: XCircle,
  },
]

export function PersonalityStep() {
  const { form, updateForm } = useCreationStore()

  return (
    <div className="space-y-6">
      {/* Communication Style */}
      <div>
        <label className="mb-3 block text-sm font-medium text-[var(--color-text-primary)]">
          How should your bot communicate?
        </label>
        <div className="grid grid-cols-3 gap-2">
          {COMMUNICATION_STYLES.map((style) => (
            <button
              key={style.id}
              onClick={() => updateForm({ communicationStyle: style.id })}
              className={cn(
                'flex flex-col items-start rounded-lg border p-3 text-left transition-all',
                form.communicationStyle === style.id
                  ? 'border-cachi-500 bg-cachi-500/10'
                  : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)]'
              )}
            >
              <span className="font-medium text-[var(--color-text-primary)]">{style.label}</span>
              <span className="text-xs text-[var(--color-text-secondary)]">{style.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Emoji Preference */}
      <div>
        <label className="mb-3 block text-sm font-medium text-[var(--color-text-primary)]">
          Should your bot use emojis?
        </label>
        <div className="flex gap-3">
          {EMOJI_OPTIONS.map((option) => {
            const Icon = option.icon
            return (
              <button
                key={option.id}
                onClick={() => updateForm({ useEmojis: option.id })}
                className={cn(
                  'flex flex-1 flex-col items-center gap-2 rounded-lg border p-4 transition-all',
                  form.useEmojis === option.id
                    ? 'border-cachi-500 bg-cachi-500/10'
                    : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)]'
                )}
              >
                <Icon
                  className={cn(
                    'h-6 w-6',
                    form.useEmojis === option.id ? 'text-cachi-400' : 'text-[var(--color-text-secondary)]'
                  )}
                />
                <div className="text-center">
                  <span className="block font-medium text-[var(--color-text-primary)]">{option.label}</span>
                  <span className="text-xs text-[var(--color-text-secondary)]">{option.description}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
