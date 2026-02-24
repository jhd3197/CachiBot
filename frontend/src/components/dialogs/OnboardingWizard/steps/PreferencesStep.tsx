import { Sun, Moon, Monitor, Plus } from 'lucide-react'
import { useUIStore, type Theme, type PresetColor, accentColors, generatePalette } from '../../../../stores/ui'
import { cn } from '../../../../lib/utils'

const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

const colorOptions = Object.entries(accentColors) as [PresetColor, (typeof accentColors)[PresetColor]][]

export function PreferencesStep() {
  const { theme, setTheme, accentColor, setAccentColor, customHex, setCustomHex, showThinking, setShowThinking, showCost, setShowCost } =
    useUIStore()
  const customPalette = generatePalette(customHex)

  return (
    <div className="space-y-6">
      {/* Theme */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-[var(--color-text-primary)]">Color Theme</label>
        <div className="flex gap-2">
          {themeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setTheme(option.value)}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-lg border py-3 transition-all',
                theme === option.value
                  ? 'border-accent-500 bg-accent-500/20 text-accent-600 dark:text-accent-400'
                  : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] hover:border-[var(--color-border-focus)]'
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
        <label className="block text-sm font-medium text-[var(--color-text-primary)]">Accent Color</label>
        <div className="settings-color-grid">
          {colorOptions.map(([value, { palette }]) => (
            <button
              key={value}
              onClick={() => setAccentColor(value)}
              className={cn(
                'settings-color-circle',
                accentColor === value && 'settings-color-circle--active'
              )}
              style={{
                backgroundColor: palette[500],
                boxShadow: accentColor === value ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${palette[500]}` : undefined,
              }}
              title={value.charAt(0).toUpperCase() + value.slice(1)}
            />
          ))}
          <label
            className={cn(
              'settings-color-circle settings-color-circle--custom',
              accentColor === 'custom' && 'settings-color-circle--active'
            )}
            style={{
              backgroundColor: customPalette[500],
              boxShadow: accentColor === 'custom' ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${customPalette[500]}` : undefined,
            }}
            title="Custom"
          >
            <Plus className="settings-color-circle__icon" />
            <input
              type="color"
              value={customHex}
              onChange={(e) => setCustomHex(e.target.value)}
              className="settings-color-circle__input"
            />
          </label>
        </div>
      </div>

      {/* Display toggles */}
      <div className="space-y-4">
        <label className="block text-sm font-medium text-[var(--color-text-primary)]">Display Options</label>
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
    <div className="flex items-center justify-between rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-primary)] p-3">
      <div>
        <p className="text-sm font-medium text-[var(--color-text-primary)]">{label}</p>
        <p className="text-xs text-[var(--color-text-secondary)]">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-accent-600' : 'bg-zinc-300 dark:bg-zinc-700'
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
