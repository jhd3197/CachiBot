import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Search,
  Loader2,
  AlertCircle,
  ToggleLeft,
  ToggleRight,
  ExternalLink,
  Package,
  Shield,
  Eye,
  Wrench,
  Save,
  RotateCcw,
  Upload,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { usePluginsStore } from '../../stores/plugins'
import { ToolIconRenderer } from '../common/ToolIconRenderer'
import { cn } from '../../lib/utils'
import type { ExternalPluginInfo, ToolConfigs } from '../../types'

export function PluginsView() {
  const { getActiveBot, updateBot } = useBotStore()
  const { plugins, loading, error, fetchPlugins, togglePlugin, reloadPlugins, installPlugin, uninstallPlugin } = usePluginsStore()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [search, setSearch] = useState('')
  const [selectedPlugin, setSelectedPlugin] = useState<ExternalPluginInfo | null>(null)
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({})
  const [configDirty, setConfigDirty] = useState(false)
  const activeBot = getActiveBot()

  useEffect(() => {
    fetchPlugins()
  }, [fetchPlugins])

  // Initialize config values when a plugin is selected
  const initConfigValues = useCallback((plugin: ExternalPluginInfo | null) => {
    if (!plugin || !activeBot) {
      setConfigValues({})
      setConfigDirty(false)
      return
    }
    const toolConfig = activeBot.toolConfigs?.[`ext_${plugin.name}`] ?? {}
    const initial: Record<string, unknown> = {}
    for (const param of plugin.config) {
      const saved = toolConfig[param.name]
      initial[param.name] = saved !== undefined ? saved : param.default
    }
    setConfigValues(initial)
    setConfigDirty(false)
  }, [activeBot])

  useEffect(() => {
    initConfigValues(selectedPlugin)
  }, [selectedPlugin, initConfigValues])

  const handleConfigChange = (paramName: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [paramName]: value }))
    setConfigDirty(true)
  }

  const handleConfigSave = () => {
    if (!activeBot || !selectedPlugin) return
    const newConfigs: ToolConfigs = { ...activeBot.toolConfigs }
    newConfigs[`ext_${selectedPlugin.name}`] = { ...configValues }
    updateBot(activeBot.id, { toolConfigs: newConfigs })
    setConfigDirty(false)
    toast.success('Plugin configuration saved')
  }

  const handleConfigReset = () => {
    if (!selectedPlugin) return
    const defaults: Record<string, unknown> = {}
    for (const param of selectedPlugin.config) {
      defaults[param.name] = param.default
    }
    setConfigValues(defaults)
    setConfigDirty(true)
  }

  if (!activeBot) return null

  const capabilities: Record<string, boolean> = (activeBot.capabilities ?? {}) as Record<string, boolean>

  const filtered = plugins.filter((p) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      p.name.toLowerCase().includes(q) ||
      p.displayName.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      p.group.toLowerCase().includes(q)
    )
  })

  // Group by category
  const groups: Record<string, ExternalPluginInfo[]> = {}
  for (const p of filtered) {
    const g = p.group || 'Other'
    if (!groups[g]) groups[g] = []
    groups[g].push(p)
  }

  const isEnabled = (plugin: ExternalPluginInfo) => {
    return capabilities[plugin.capabilityKey] === true
  }

  const handleToggle = async (plugin: ExternalPluginInfo) => {
    const enabling = !isEnabled(plugin)
    const result = await togglePlugin(plugin.name, enabling)
    if (result) {
      const newCaps = { ...capabilities, [result.capabilityKey]: result.enabled }
      updateBot(activeBot.id, { capabilities: newCaps as typeof activeBot.capabilities })
      toast.success(`${plugin.displayName} ${enabling ? 'enabled' : 'disabled'}`)
    }
  }

  const handleReload = async () => {
    const result = await reloadPlugins()
    if (result) {
      const errorCount = Object.keys(result.errors).length
      toast.success(
        `Reloaded ${result.loaded}/${result.total} plugin(s)` +
          (errorCount > 0 ? ` (${errorCount} error${errorCount > 1 ? 's' : ''})` : '')
      )
      setSelectedPlugin(null)
    }
  }

  const handleInstall = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const ok = await installPlugin(file)
    if (ok) {
      toast.success(`Plugin installed from ${file.name}`)
      setSelectedPlugin(null)
    } else {
      toast.error('Failed to install plugin')
    }
    // Reset input so the same file can be re-selected
    e.target.value = ''
  }

  const handleUninstall = async (plugin: ExternalPluginInfo) => {
    const ok = await uninstallPlugin(plugin.name)
    if (ok) {
      // Remove capability from bot if it was enabled
      if (isEnabled(plugin)) {
        const newCaps = { ...capabilities }
        delete newCaps[plugin.capabilityKey]
        updateBot(activeBot.id, { capabilities: newCaps as typeof activeBot.capabilities })
      }
      toast.success(`${plugin.displayName} uninstalled`)
      setSelectedPlugin(null)
    } else {
      toast.error(`Failed to uninstall ${plugin.displayName}`)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      {/* Main plugin list */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-700/50">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Plugins</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Manage external plugins for {activeBot.name}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search plugins..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input input--sm pl-9"
                style={{ width: 240 }}
              />
            </div>
            <button
              onClick={handleReload}
              disabled={loading}
              className="btn btn--ghost btn--sm"
              title="Reload all plugins"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="btn btn--primary btn--sm"
              title="Install plugin from archive"
            >
              <Upload className="h-4 w-4" />
              <span className="ml-1.5">Install</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip,.tar.gz,.tgz"
              onChange={handleInstall}
              className="hidden"
            />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {plugins.length === 0 && !error ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-100 dark:bg-zinc-800">
                <Package className="h-8 w-8 text-zinc-400" />
              </div>
              <h3 className="mb-2 text-base font-medium text-zinc-900 dark:text-zinc-100">
                No external plugins installed
              </h3>
              <p className="mb-4 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">
                Install plugins from an archive or drop directories into <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">~/.cachibot/plugins/</code>
              </p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="btn btn--primary btn--sm"
              >
                <Upload className="mr-1.5 h-4 w-4" />
                Install Plugin
              </button>
            </div>
          ) : (
            Object.entries(groups).map(([group, groupPlugins]) => (
              <div key={group} className="mb-6">
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  {group}
                </h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {groupPlugins.map((plugin) => {
                    const enabled = isEnabled(plugin)
                    return (
                      <button
                        key={plugin.name}
                        onClick={() => setSelectedPlugin(plugin)}
                        className={cn(
                          'group relative flex flex-col rounded-xl border p-4 text-left transition-all',
                          'hover:shadow-md',
                          enabled
                            ? 'border-accent-500/30 bg-accent-50/50 dark:border-accent-500/20 dark:bg-accent-900/10'
                            : 'border-zinc-200 bg-white dark:border-zinc-700/50 dark:bg-zinc-800/50',
                          selectedPlugin?.name === plugin.name && 'ring-2 ring-accent-500/40'
                        )}
                      >
                        <div className="mb-3 flex items-start justify-between">
                          <div className="flex items-center gap-2.5">
                            <div
                              className="flex h-9 w-9 items-center justify-center rounded-lg"
                              style={{ backgroundColor: plugin.color + '20' }}
                            >
                              <ToolIconRenderer name={plugin.icon} className="h-5 w-5" style={{ color: plugin.color }} />
                            </div>
                            <div>
                              <div className="font-medium text-zinc-900 dark:text-zinc-100">
                                {plugin.displayName}
                              </div>
                              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                v{plugin.version}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
                              plugin.type === 'view'
                                ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                            )}>
                              {plugin.type === 'view' ? <Eye className="h-3 w-3" /> : <Wrench className="h-3 w-3" />}
                              {plugin.type}
                            </span>
                          </div>
                        </div>

                        <p className="mb-3 line-clamp-2 text-sm text-zinc-600 dark:text-zinc-300">
                          {plugin.description}
                        </p>

                        {!plugin.loaded && plugin.error && (
                          <div className="mb-2 flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                            <AlertCircle className="h-3 w-3" />
                            {plugin.error}
                          </div>
                        )}

                        <div className="mt-auto flex items-center justify-between">
                          {plugin.author && (
                            <span className="text-xs text-zinc-400">{plugin.author}</span>
                          )}
                          <div
                            onClick={(e) => {
                              e.stopPropagation()
                              if (plugin.loaded) handleToggle(plugin)
                            }}
                            className={cn(
                              'ml-auto cursor-pointer',
                              !plugin.loaded && 'pointer-events-none opacity-40'
                            )}
                          >
                            {enabled ? (
                              <ToggleRight className="h-6 w-6 text-accent-500" />
                            ) : (
                              <ToggleLeft className="h-6 w-6 text-zinc-400" />
                            )}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedPlugin && (
        <div className="w-80 flex-shrink-0 overflow-y-auto border-l border-zinc-200 bg-zinc-50 p-5 dark:border-zinc-700/50 dark:bg-zinc-900/50">
          <div className="mb-4 flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ backgroundColor: selectedPlugin.color + '20' }}
            >
              <ToolIconRenderer
                name={selectedPlugin.icon}
                className="h-5 w-5"
                style={{ color: selectedPlugin.color }}
              />
            </div>
            <div>
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                {selectedPlugin.displayName}
              </h3>
              <span className="text-xs text-zinc-500">v{selectedPlugin.version}</span>
            </div>
          </div>

          <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-300">
            {selectedPlugin.description}
          </p>

          {/* Status */}
          <div className="mb-4 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Status</h4>
            <div className="flex items-center gap-2 text-sm">
              <div className={cn(
                'h-2 w-2 rounded-full',
                selectedPlugin.loaded ? 'bg-green-500' : 'bg-amber-500'
              )} />
              <span className="text-zinc-700 dark:text-zinc-300">
                {selectedPlugin.loaded ? 'Loaded' : 'Not loaded'}
              </span>
            </div>
            {selectedPlugin.error && (
              <p className="text-xs text-amber-600 dark:text-amber-400">{selectedPlugin.error}</p>
            )}
          </div>

          {/* Requirements */}
          <div className="mb-4 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Requirements</h4>
            <div className="space-y-1 text-sm text-zinc-600 dark:text-zinc-300">
              {selectedPlugin.requires.filesystem && (
                <div className="flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5 text-zinc-400" /> Filesystem access
                </div>
              )}
              {selectedPlugin.requires.network && (
                <div className="flex items-center gap-1.5">
                  <ExternalLink className="h-3.5 w-3.5 text-zinc-400" /> Network access
                </div>
              )}
              {selectedPlugin.requires.imports.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <Package className="h-3.5 w-3.5 text-zinc-400" />
                  {selectedPlugin.requires.imports.join(', ')}
                </div>
              )}
            </div>
          </div>

          {/* Permissions */}
          {(selectedPlugin.permissions.allowEnvVars.length > 0 ||
            selectedPlugin.permissions.allowPaths.length > 0) && (
            <div className="mb-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Permissions
              </h4>
              <div className="space-y-1 text-sm text-zinc-600 dark:text-zinc-300">
                {selectedPlugin.permissions.allowEnvVars.map((v) => (
                  <div key={v} className="flex items-center gap-1.5">
                    <code className="rounded bg-zinc-100 px-1 text-xs dark:bg-zinc-800">{v}</code>
                  </div>
                ))}
                {selectedPlugin.permissions.allowPaths.map((p) => (
                  <div key={p} className="flex items-center gap-1.5">
                    <code className="rounded bg-zinc-100 px-1 text-xs dark:bg-zinc-800">{p}</code>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Config params */}
          {selectedPlugin.config.length > 0 && (
            <div className="mb-4 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                  Configuration
                </h4>
                {configDirty && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={handleConfigReset}
                      className="btn btn--ghost btn--xs"
                      title="Reset to defaults"
                    >
                      <RotateCcw className="h-3 w-3" />
                    </button>
                    <button
                      onClick={handleConfigSave}
                      className="btn btn--primary btn--xs"
                      title="Save"
                    >
                      <Save className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
              <div className="space-y-3">
                {selectedPlugin.config.map((param) => {
                  const value = configValues[param.name]
                  return (
                    <div key={param.name}>
                      <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                        {param.displayName || param.name}
                      </label>
                      {param.description && (
                        <div className="mb-1 text-xs text-zinc-500">{param.description}</div>
                      )}
                      {param.type === 'number' ? (
                        <input
                          type="number"
                          value={typeof value === 'number' ? value : (Number(value) || 0)}
                          onChange={(e) => handleConfigChange(param.name, Number(e.target.value))}
                          className="input input--sm w-full"
                        />
                      ) : param.type === 'boolean' ? (
                        <button
                          type="button"
                          onClick={() => handleConfigChange(param.name, !value)}
                          className="flex items-center gap-2"
                        >
                          {value ? (
                            <ToggleRight className="h-5 w-5 text-accent-500" />
                          ) : (
                            <ToggleLeft className="h-5 w-5 text-zinc-400" />
                          )}
                          <span className="text-sm text-zinc-600 dark:text-zinc-300">
                            {value ? 'Enabled' : 'Disabled'}
                          </span>
                        </button>
                      ) : (
                        <input
                          type="text"
                          value={typeof value === 'string' ? value : String(value ?? '')}
                          onChange={(e) => handleConfigChange(param.name, e.target.value)}
                          placeholder={String(param.default ?? '')}
                          className="input input--sm w-full"
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Contexts */}
          <div className="mb-4 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Contexts</h4>
            <div className="flex flex-wrap gap-1.5">
              {selectedPlugin.contexts.map((ctx) => (
                <span
                  key={ctx}
                  className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                >
                  {ctx}
                </span>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-2">
            <button
              onClick={() => handleToggle(selectedPlugin)}
              disabled={!selectedPlugin.loaded}
              className={cn(
                'btn w-full',
                isEnabled(selectedPlugin) ? 'btn--outline' : 'btn--primary'
              )}
            >
              {isEnabled(selectedPlugin) ? 'Disable Plugin' : 'Enable Plugin'}
            </button>
            <button
              onClick={() => handleUninstall(selectedPlugin)}
              className="btn btn--ghost w-full text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-900/20 dark:hover:text-red-300"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              Uninstall
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
