import { Sun, Moon, Monitor } from 'lucide-react'
import { useUIStore, type Theme, type AccentColor, accentColors } from '../../../../stores/ui'
import { cn } from '../../../../lib/utils'

const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

const colorOptions = Object.entries(accentColors) as [AccentColor, (typeof accentColors)[AccentColor]][]

export function PreferencesStep() {
  const { theme, setTheme, accentColor, setAccentColor, showThinking, setShowThinking, showCost, setShowCost } =
    useUIStore()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">Personalize Your Experience</h3>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
          Customize how CachiBot looks and feels.
        </p>
      </div>

      {/* Theme */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Color Theme</label>
        <div className="flex gap-2">
          {themeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setTheme(option.value)}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-lg border py-3 transition-all',
                theme === option.value
                  ? 'border-accent-500 bg-accent-500/20 text-accent-400'
                  : 'border-zinc-300 bg-zinc-100 text-zinc-700 hover:border-zinc-400 dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-primary)] dark:hover:border-[var(--color-border-secondary)]'
              )}
            >
              <option.icon className="h-4 w-4" />
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Accent Color */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Accent Color</label>
        <div className="grid grid-cols-4 gap-2">
          {colorOptions.map(([value, { name, palette }]) => (
            <button
              key={value}
              onClick={() => setAccentColor(value)}
              className={cn(
                'flex items-center gap-2 rounded-lg border p-3 transition-all',
                accentColor === value
                  ? 'border-2 ring-1 ring-offset-1 ring-offset-white dark:ring-offset-zinc-900'
                  : 'border-zinc-300 hover:border-zinc-400 dark:border-[var(--color-border-secondary)] dark:hover:border-[var(--color-border-secondary)]'
              )}
              style={{
                borderColor: accentColor === value ? palette[500] : undefined,
                // @ts-expect-error - Tailwind CSS variable
                '--tw-ring-color': accentColor === value ? palette[500] : undefined,
              }}
            >
              <div className="h-5 w-5 rounded-full" style={{ backgroundColor: palette[500] }} />
              <span className="text-sm text-zinc-700 dark:text-[var(--color-text-primary)]">{name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Display toggles */}
      <div className="space-y-4">
        <label className="block text-sm font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Display Options</label>
        <ToggleItem
          label="Show Thinking Process"
          description="Display the AI's reasoning and thought process"
          checked={showThinking}
          onChange={setShowThinking}
        />
        <ToggleItem
          label="Show Token Costs"
          description="Display estimated costs for API calls"
          checked={showCost}
          onChange={setShowCost}
        />
      </div>
    </div>
  )
}

function ToggleItem({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
      <div>
        <p className="text-sm font-medium text-zinc-800 dark:text-[var(--color-text-primary)]">{label}</p>
        <p className="text-xs text-[var(--color-text-secondary)]">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-accent-600' : 'bg-zinc-300 dark:bg-[var(--color-hover-bg)]'
        )}
      >
        <span
          className={cn(
            'absolute top-1 h-4 w-4 rounded-full bg-white transition-transform',
            checked ? 'left-6' : 'left-1'
          )}
        />
      </button>
    </div>
  )
}
