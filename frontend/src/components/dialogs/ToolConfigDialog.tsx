import { useState, useEffect } from 'react'
import { X, Save, RotateCcw } from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import type { Tool, ToolConfigs, ConfigParam } from '../../types'
import { cn } from '../../lib/utils'

interface ToolConfigDialogProps {
  tool: Tool
  botId: string
  currentConfigs?: ToolConfigs
  isOpen: boolean
  onClose: () => void
}

function formatValue(value: unknown, param: ConfigParam): string {
  if (param.type === 'number' && typeof value === 'number') {
    if (param.unit === 'chars' && value >= 1000) {
      return `${(value / 1000).toFixed(0)}k ${param.unit}`
    }
    return param.unit ? `${value} ${param.unit}` : String(value)
  }
  return String(value)
}

export function ToolConfigDialog({ tool, botId, currentConfigs, isOpen, onClose }: ToolConfigDialogProps) {
  const { updateBot } = useBotStore()
  const configParams = tool.configParams || []
  const hasConfig = configParams.length > 0

  // Dynamic state: param name -> current value
  const [values, setValues] = useState<Record<string, unknown>>({})

  // Initialize values from current configs or defaults
  useEffect(() => {
    if (!isOpen) return

    const params = tool.configParams || []
    const initial: Record<string, unknown> = {}
    const toolConfig = currentConfigs?.[tool.id]

    for (const param of params) {
      const saved = toolConfig?.[param.name]
      initial[param.name] = saved !== undefined ? saved : param.default
    }

    setValues(initial)
  }, [isOpen, tool.id, tool.configParams, currentConfigs])

  const handleSave = () => {
    const newConfigs: ToolConfigs = { ...currentConfigs }
    newConfigs[tool.id] = { ...values }
    updateBot(botId, { toolConfigs: newConfigs })
    onClose()
  }

  const handleReset = () => {
    const defaults: Record<string, unknown> = {}
    for (const param of configParams) {
      defaults[param.name] = param.default
    }
    setValues(defaults)
  }

  const updateValue = (name: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  if (!isOpen) return null

  const renderParam = (param: ConfigParam) => {
    const value = values[param.name]

    switch (param.type) {
      case 'number': {
        const numValue = typeof value === 'number' ? value : (param.default as number) ?? 0
        return (
          <div key={param.name} className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {param.displayName || param.name}
              </label>
              <span className="text-sm text-zinc-400">{formatValue(numValue, param)}</span>
            </div>
            <input
              type="range"
              min={param.min ?? 0}
              max={param.max ?? 100}
              step={param.step ?? 1}
              value={numValue}
              onChange={(e) => updateValue(param.name, Number(e.target.value))}
              className="w-full accent-cachi-500"
            />
            <div className="flex justify-between text-xs text-zinc-500">
              <span>{formatValue(param.min ?? 0, param)}</span>
              <span>{formatValue(param.max ?? 100, param)}</span>
            </div>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'boolean': {
        const boolValue = typeof value === 'boolean' ? value : Boolean(param.default)
        return (
          <div key={param.name} className="flex items-center justify-between rounded-lg border border-zinc-800 p-4">
            <div>
              <h4 className="text-sm font-medium text-zinc-200">
                {param.displayName || param.name}
              </h4>
              {param.description && (
                <p className="text-xs text-zinc-500">{param.description}</p>
              )}
            </div>
            <button
              onClick={() => updateValue(param.name, !boolValue)}
              className={cn(
                'relative h-6 w-11 rounded-full transition-colors',
                boolValue ? 'bg-cachi-600' : 'bg-zinc-700'
              )}
            >
              <span
                className={cn(
                  'absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
                  boolValue ? 'left-[22px]' : 'left-0.5'
                )}
              />
            </button>
          </div>
        )
      }

      case 'select': {
        const strValue = String(value ?? param.default ?? '')
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              {param.displayName || param.name}
            </label>
            <select
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-cachi-500"
            >
              {(param.options || []).map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'string': {
        const strValue = String(value ?? param.default ?? '')
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              {param.displayName || param.name}
            </label>
            <input
              type="text"
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-cachi-500"
            />
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      default:
        return null
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Configure {tool.name}</h2>
            <p className="text-sm text-zinc-500">{tool.description}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {hasConfig ? (
            <div className="space-y-6">
              {configParams.map(renderParam)}
            </div>
          ) : (
            <div className="py-8 text-center text-zinc-500">
              No configuration options available for this tool.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between border-t border-zinc-800 p-4">
          <button
            onClick={handleReset}
            disabled={!hasConfig}
            className="flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Defaults
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasConfig}
              className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
