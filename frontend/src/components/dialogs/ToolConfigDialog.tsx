import { useState, useEffect } from 'react'
import { X, Save, RotateCcw, Plus, Trash2, Eye, EyeOff, FolderOpen, FileText, MapPin, Link, Code, Check } from 'lucide-react'
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

  const [revealedSecrets, setRevealedSecrets] = useState<Set<string>>(new Set())

  const toggleSecretVisibility = (name: string) => {
    setRevealedSecrets((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
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
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {param.displayName || param.name}
              </label>
              <span className="text-sm text-zinc-500 dark:text-zinc-400">{formatValue(numValue, param)}</span>
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
          <div key={param.name} className="flex items-center justify-between rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
            <div>
              <h4 className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
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
                boolValue ? 'bg-cachi-600' : 'bg-zinc-200 dark:bg-zinc-700'
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
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <select
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 outline-none focus:border-cachi-500"
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
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <input
              type="text"
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              placeholder={param.placeholder}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
            />
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'secret': {
        const strValue = String(value ?? param.default ?? '')
        const isRevealed = revealedSecrets.has(param.name)
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <div className="relative">
              <input
                type={isRevealed ? 'text' : 'password'}
                value={strValue}
                onChange={(e) => updateValue(param.name, e.target.value)}
                placeholder={param.placeholder ?? 'Enter secret...'}
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 pr-10 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
              />
              <button
                type="button"
                onClick={() => toggleSecretVisibility(param.name)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300"
              >
                {isRevealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'text': {
        const strValue = String(value ?? param.default ?? '')
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <textarea
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              rows={param.rows ?? 4}
              placeholder={param.placeholder}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500 resize-y"
            />
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'path': {
        const strValue = String(value ?? param.default ?? '')
        const pathIcon = param.pathType === 'directory' ? FolderOpen
          : param.pathType === 'file' ? FileText
          : MapPin
        const PathIcon = pathIcon
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
                <PathIcon className="h-4 w-4" />
              </span>
              <input
                type="text"
                value={strValue}
                onChange={(e) => updateValue(param.name, e.target.value)}
                placeholder={param.placeholder ?? (param.pathType === 'directory' ? '/path/to/directory' : '/path/to/file')}
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 pl-9 pr-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500 font-mono"
              />
            </div>
            {param.pathType && (
              <span className="inline-block rounded bg-zinc-200 dark:bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500 dark:text-zinc-400 border border-zinc-300 dark:border-zinc-700">
                {param.pathType}
              </span>
            )}
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'string[]':
      case 'number[]': {
        const isNumeric = param.type === 'number[]'
        const items = Array.isArray(value) ? (value as (string | number)[]) : (Array.isArray(param.default) ? (param.default as (string | number)[]) : [])
        const canAdd = param.maxItems === undefined || items.length < param.maxItems
        const canRemove = param.minItems === undefined || items.length > param.minItems

        const updateItems = (newItems: (string | number)[]) => {
          updateValue(param.name, newItems)
        }

        return (
          <div key={param.name} className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {param.displayName || param.name}
              </label>
              <span className="text-xs text-zinc-500">
                {items.length}{param.maxItems !== undefined ? ` / ${param.maxItems}` : ''} items
              </span>
            </div>
            <div className="space-y-2">
              {items.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type={isNumeric ? 'number' : 'text'}
                    value={item}
                    onChange={(e) => {
                      const newItems = [...items]
                      newItems[i] = isNumeric ? Number(e.target.value) : e.target.value
                      updateItems(newItems)
                    }}
                    placeholder={param.itemPlaceholder}
                    className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
                  />
                  <button
                    onClick={() => {
                      if (!canRemove) return
                      updateItems(items.filter((_, j) => j !== i))
                    }}
                    disabled={!canRemove}
                    className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => {
                if (!canAdd) return
                updateItems([...items, isNumeric ? 0 : ''])
              }}
              disabled={!canAdd}
              className="flex items-center gap-1.5 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 dark:text-zinc-400 hover:border-cachi-500 hover:text-cachi-400 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Plus className="h-3.5 w-3.5" />
              Add item
            </button>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'map': {
        const entries = Array.isArray(value)
          ? (value as [string, string][])
          : (Array.isArray(param.default) ? (param.default as [string, string][]) : [])
        const canAdd = param.maxItems === undefined || entries.length < param.maxItems

        const updateEntries = (newEntries: [string, string][]) => {
          updateValue(param.name, newEntries)
        }

        return (
          <div key={param.name} className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {param.displayName || param.name}
              </label>
              <span className="text-xs text-zinc-500">
                {entries.length}{param.maxItems !== undefined ? ` / ${param.maxItems}` : ''} entries
              </span>
            </div>
            <div className="space-y-2">
              {entries.map(([k, v], i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={k}
                    onChange={(e) => {
                      const newEntries = [...entries] as [string, string][]
                      newEntries[i] = [e.target.value, v]
                      updateEntries(newEntries)
                    }}
                    placeholder={param.keyPlaceholder ?? 'Key'}
                    className="w-2/5 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
                  />
                  <input
                    type="text"
                    value={v}
                    onChange={(e) => {
                      const newEntries = [...entries] as [string, string][]
                      newEntries[i] = [k, e.target.value]
                      updateEntries(newEntries)
                    }}
                    placeholder={param.valuePlaceholder ?? 'Value'}
                    className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
                  />
                  <button
                    onClick={() => updateEntries(entries.filter((_, j) => j !== i))}
                    className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-red-400"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => {
                if (!canAdd) return
                updateEntries([...entries, ['', '']])
              }}
              disabled={!canAdd}
              className="flex items-center gap-1.5 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 dark:text-zinc-400 hover:border-cachi-500 hover:text-cachi-400 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Plus className="h-3.5 w-3.5" />
              Add entry
            </button>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'multiselect': {
        const selected = Array.isArray(value) ? (value as string[]) : (Array.isArray(param.default) ? (param.default as string[]) : [])
        const options = param.options || []

        const toggleOption = (opt: string) => {
          const next = selected.includes(opt)
            ? selected.filter((s) => s !== opt)
            : [...selected, opt]
          updateValue(param.name, next)
        }

        return (
          <div key={param.name} className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {param.displayName || param.name}
              </label>
              <span className="text-xs text-zinc-500">
                {selected.length} / {options.length} selected
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {options.map((opt) => {
                const isSelected = selected.includes(opt)
                return (
                  <button
                    key={opt}
                    onClick={() => toggleOption(opt)}
                    className={cn(
                      'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors',
                      isSelected
                        ? 'border-cachi-500 bg-cachi-500/15 text-cachi-300'
                        : 'border-zinc-300 dark:border-zinc-700 bg-zinc-200 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-600 hover:text-zinc-600 dark:hover:text-zinc-300'
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                    {opt}
                  </button>
                )
              })}
            </div>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'url': {
        const strValue = String(value ?? param.default ?? '')
        return (
          <div key={param.name} className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {param.displayName || param.name}
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
                <Link className="h-4 w-4" />
              </span>
              <input
                type="url"
                value={strValue}
                onChange={(e) => updateValue(param.name, e.target.value)}
                placeholder={param.placeholder ?? 'https://...'}
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 pl-9 pr-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
              />
            </div>
            {param.description && (
              <p className="text-xs text-zinc-500">{param.description}</p>
            )}
          </div>
        )
      }

      case 'code': {
        const strValue = String(value ?? param.default ?? '')
        return (
          <div key={param.name} className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {param.displayName || param.name}
              </label>
              {param.language && (
                <span className="flex items-center gap-1 rounded bg-zinc-200 dark:bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500 dark:text-zinc-400 border border-zinc-300 dark:border-zinc-700">
                  <Code className="h-3 w-3" />
                  {param.language}
                </span>
              )}
            </div>
            <textarea
              value={strValue}
              onChange={(e) => updateValue(param.name, e.target.value)}
              rows={param.rows ?? 6}
              placeholder={param.placeholder}
              spellCheck={false}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-950 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500 resize-y font-mono leading-relaxed"
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
      <div className="w-full max-w-md rounded-xl bg-white dark:bg-zinc-900 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 p-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Configure {tool.name}</h2>
            <p className="text-sm text-zinc-500">{tool.description}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto p-4">
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
        <div className="flex justify-between border-t border-zinc-200 dark:border-zinc-800 p-4">
          <button
            onClick={handleReset}
            disabled={!hasConfig}
            className="flex items-center gap-2 rounded-lg border border-zinc-300 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Defaults
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800"
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
