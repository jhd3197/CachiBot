import { X } from 'lucide-react'
import { Button } from '../common/Button'
import { ModelSelect } from '../common/ModelSelect'
import { useUIStore } from '../../stores/ui'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { updateConfig } from '../../api/client'
import { cn } from '../../lib/utils'

export function SettingsDialog() {
  const { settingsOpen, setSettingsOpen, showThinking, setShowThinking, showCost, setShowCost } = useUIStore()
  const { config, updateConfig: updateLocalConfig } = useConfigStore()
  const { defaultModel, updateDefaultModel } = useModelsStore()

  if (!settingsOpen) return null

  const handleModelChange = async (model: string) => {
    await updateDefaultModel(model)
    try {
      await updateConfig({ model })
    } catch (error) {
      console.error('Failed to update model:', error)
    }
  }

  const handleToggleChange = async (key: 'showThinking' | 'showCost', value: boolean) => {
    if (key === 'showThinking') {
      setShowThinking(value)
    } else {
      setShowCost(value)
    }

    try {
      await updateConfig({ [key === 'showThinking' ? 'show_thinking' : 'show_cost']: value })
    } catch (error) {
      console.error('Failed to update setting:', error)
    }
  }

  const handleApprovalChange = async (value: boolean) => {
    updateLocalConfig({ approveActions: value })
    try {
      await updateConfig({ approve_actions: value })
    } catch (error) {
      console.error('Failed to update setting:', error)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Settings</h2>
          <Button variant="ghost" size="sm" onClick={() => setSettingsOpen(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="space-y-6">
          {/* Model selection */}
          <div>
            <label className="mb-2 block text-sm font-medium">Default Model</label>
            <ModelSelect
              value={defaultModel}
              onChange={handleModelChange}
              placeholder="Select a model..."
              className="w-full"
            />
          </div>

          {/* Toggles */}
          <div className="space-y-3">
            <Toggle
              label="Show thinking"
              description="Display the agent's reasoning process"
              checked={showThinking}
              onChange={(v) => handleToggleChange('showThinking', v)}
            />

            <Toggle
              label="Show cost"
              description="Display token usage and cost information"
              checked={showCost}
              onChange={(v) => handleToggleChange('showCost', v)}
            />

            <Toggle
              label="Require approval"
              description="Ask for approval before executing risky operations"
              checked={config?.agent.approveActions ?? false}
              onChange={handleApprovalChange}
            />
          </div>

          {/* Workspace path */}
          {config && (
            <div>
              <label className="mb-1 block text-sm font-medium">Workspace</label>
              <p className="truncate text-sm text-zinc-500 dark:text-zinc-400">
                {config.workspacePath}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

interface ToggleProps {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}

function Toggle({ label, description, checked, onChange }: ToggleProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-cachi-600' : 'bg-zinc-200 dark:bg-zinc-700'
        )}
      >
        <span
          className={cn(
            'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
            checked && 'translate-x-5'
          )}
        />
      </button>
    </div>
  )
}
