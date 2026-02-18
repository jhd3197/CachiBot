import { useState, useEffect } from 'react'
import {
  Search,
  Shield,
  ShieldAlert,
  ShieldOff,
  ShieldBan,
  FileText,
  Code,
  Globe,
  Terminal,
  Database,
  Puzzle,
  ToggleLeft,
  ToggleRight,
  Info,
  Settings,
  Play,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { usePlatformToolsStore } from '../../stores/platform-tools'
import { ToolIconRenderer, resolveIconName } from '../common/ToolIconRenderer'
import { ToolConfigDialog } from '../dialogs/ToolConfigDialog'
import { cn } from '../../lib/utils'
import { getPlugins } from '../../api/plugins'
import type { Tool, ToolCategory, PluginInfo, PluginSkillInfo } from '../../types'

// Map backend skill categories to frontend ToolCategory (kept for filter chips)
const categoryMap: Record<string, ToolCategory> = {
  file: 'filesystem',
  code: 'code',
  task: 'system',
  platform: 'web',
  work: 'data',
  git: 'system',
  shell: 'system',
  web: 'web',
  http: 'web',
  sql: 'data',
  compression: 'filesystem',
  general: 'custom',
}

const categoryConfig: Record<
  ToolCategory,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  filesystem: { label: 'Filesystem', icon: FileText },
  code: { label: 'Code', icon: Code },
  web: { label: 'Connections', icon: Globe },
  system: { label: 'System', icon: Terminal },
  data: { label: 'Work', icon: Database },
  custom: { label: 'Custom', icon: Puzzle },
}

function humanizeName(id: string): string {
  return id
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function skillToTool(skill: PluginSkillInfo | string): Tool {
  // Handle both formats: string (just skill name) or full metadata object
  if (typeof skill === 'string') {
    return {
      id: skill,
      name: humanizeName(skill),
      description: '',
      category: 'custom',
      icon: skill,
      enabled: true,
      riskLevel: 'safe',
    }
  }
  return {
    id: skill.name,
    name: skill.displayName || humanizeName(skill.name),
    description: skill.description,
    category: categoryMap[skill.category] || 'custom',
    icon: skill.icon || skill.name,
    enabled: true,
    riskLevel: (skill.riskLevel as Tool['riskLevel']) || 'safe',
    configParams: skill.configParams,
  }
}

export function ToolsView() {
  const { getActiveBot, updateBot } = useBotStore()
  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<ToolCategory | 'all'>('all')
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [configTool, setConfigTool] = useState<Tool | null>(null)
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const activeBot = getActiveBot()
  const { config: platformConfig, fetchConfig: fetchPlatformConfig } = usePlatformToolsStore()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    // Fetch plugins and platform tool config in parallel
    Promise.all([getPlugins(), fetchPlatformConfig()])
      .then(([data]) => {
        if (!cancelled) setPlugins(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load plugins')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!activeBot) return null

  // Filter out plugins whose capability is globally disabled, then group
  const disabledCaps = new Set(platformConfig?.disabledCapabilities ?? [])
  const visiblePlugins = plugins.filter(
    (p) => !p.capability || !disabledCaps.has(p.capability)
  )
  const pluginGroups = visiblePlugins.map((plugin) => {
    const tools = plugin.skills.map(skillToTool)
    return { plugin, tools }
  })

  // Apply search and category filters
  const filteredGroups = pluginGroups
    .map(({ plugin, tools }) => ({
      plugin,
      tools: tools.filter((tool) => {
        if (search && !tool.name.toLowerCase().includes(search.toLowerCase())) return false
        if (selectedCategory !== 'all' && tool.category !== selectedCategory) return false
        return true
      }),
    }))
    .filter(({ tools }) => tools.length > 0)

  // Count all enabled tools
  const allToolIds = pluginGroups.flatMap(({ tools }) => tools.map((t) => t.id))
  const enabledCount = activeBot.tools.filter((id) => allToolIds.includes(id)).length

  const handleToggleTool = (toolId: string) => {
    const currentTools = activeBot.tools
    const newTools = currentTools.includes(toolId)
      ? currentTools.filter((id) => id !== toolId)
      : [...currentTools, toolId]
    updateBot(activeBot.id, { tools: newTools })
  }

  const isToolEnabled = (toolId: string) => activeBot.tools.includes(toolId)

  // Bulk enable/disable by risk level
  const riskLevels = ['safe', 'moderate', 'dangerous', 'critical'] as const
  const riskLevelConfig = {
    safe: { icon: Shield, color: 'text-green-500', bg: 'bg-green-500/10', border: 'border-green-500/30' },
    moderate: { icon: ShieldAlert, color: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
    dangerous: { icon: ShieldOff, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30' },
    critical: { icon: ShieldBan, color: 'text-red-600', bg: 'bg-red-600/10', border: 'border-red-600/30' },
  }

  const getToolsByRisk = (level: string) =>
    pluginGroups.flatMap(({ tools }) => tools.filter((t) => t.riskLevel === level))

  const handleToggleRiskLevel = (level: string) => {
    const toolsAtLevel = getToolsByRisk(level)
    if (toolsAtLevel.length === 0) return
    const allEnabled = toolsAtLevel.every((t) => activeBot.tools.includes(t.id))
    let newTools: string[]
    if (allEnabled) {
      // Disable all of this risk level
      const idsToRemove = new Set(toolsAtLevel.map((t) => t.id))
      newTools = activeBot.tools.filter((id) => !idsToRemove.has(id))
    } else {
      // Enable all of this risk level
      const idsToAdd = toolsAtLevel.map((t) => t.id).filter((id) => !activeBot.tools.includes(id))
      newTools = [...activeBot.tools, ...idsToAdd]
    }
    updateBot(activeBot.id, { tools: newTools })
  }

  const handleEnableAll = () => {
    const allIds = pluginGroups.flatMap(({ tools }) => tools.map((t) => t.id))
    updateBot(activeBot.id, { tools: [...new Set([...activeBot.tools, ...allIds])] })
  }

  const handleDisableAll = () => {
    const allIds = new Set(pluginGroups.flatMap(({ tools }) => tools.map((t) => t.id)))
    updateBot(activeBot.id, { tools: activeBot.tools.filter((id) => !allIds.has(id)) })
  }

  // Collect active categories for filter chips
  const activeCategories = new Set<ToolCategory>()
  for (const { tools } of pluginGroups) {
    for (const tool of tools) {
      activeCategories.add(tool.category)
    }
  }

  return (
    <div className="flex h-full bg-white dark:bg-[var(--color-bg-app)]">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="border-b border-zinc-200 dark:border-[var(--color-border-primary)] px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-zinc-900 dark:text-[var(--color-text-primary)]">Tools</h1>
              <p className="text-sm text-[var(--color-text-secondary)]">
                {enabledCount} tools enabled for {activeBot.name}
              </p>
            </div>

            {/* Risk level quick toggles */}
            <div className="flex items-center gap-2">
              {riskLevels.map((level) => {
                const cfg = riskLevelConfig[level]
                const RiskIcon = cfg.icon
                const toolsAtLevel = getToolsByRisk(level)
                const enabledAtLevel = toolsAtLevel.filter((t) => activeBot.tools.includes(t.id)).length
                const totalAtLevel = toolsAtLevel.length
                if (totalAtLevel === 0) return null
                const allEnabled = enabledAtLevel === totalAtLevel
                return (
                  <button
                    key={level}
                    onClick={() => handleToggleRiskLevel(level)}
                    title={allEnabled ? `Disable all ${level} tools` : `Enable all ${level} tools`}
                    className={cn(
                      'flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
                      allEnabled
                        ? `${cfg.bg} ${cfg.border} ${cfg.color}`
                        : 'border-zinc-300 dark:border-[var(--color-border-secondary)] bg-zinc-100 dark:bg-[var(--card-bg)] text-[var(--color-text-secondary)] hover:border-zinc-400 dark:hover:border-[var(--color-border-secondary)] hover:text-[var(--color-text-tertiary)] dark:hover:text-[var(--color-text-secondary)]'
                    )}
                  >
                    <RiskIcon className="h-3.5 w-3.5" />
                    <span className="capitalize">{level}</span>
                    <span className={cn(
                      'rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none',
                      allEnabled ? 'bg-white/10' : 'bg-zinc-300 dark:bg-[var(--color-hover-bg)]'
                    )}>
                      {enabledAtLevel}/{totalAtLevel}
                    </span>
                  </button>
                )
              })}
              <div className="mx-1 h-5 w-px bg-zinc-300 dark:bg-[var(--color-hover-bg)]" />
              <button
                onClick={handleEnableAll}
                className="rounded-lg px-2 py-1.5 text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:bg-zinc-100 dark:hover:bg-[var(--color-hover-bg)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]"
              >
                All on
              </button>
              <button
                onClick={handleDisableAll}
                className="rounded-lg px-2 py-1.5 text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:bg-zinc-100 dark:hover:bg-[var(--color-hover-bg)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]"
              >
                All off
              </button>
            </div>
          </div>

          {/* Search and filters */}
          <div className="mt-4 flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
              <input
                type="text"
                placeholder="Search tools..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] bg-zinc-100 dark:bg-[var(--card-bg)] pl-10 pr-4 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
              />
            </div>

            <div className="flex items-center gap-1 rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] bg-zinc-100 dark:bg-[var(--card-bg)] p-1">
              <button
                onClick={() => setSelectedCategory('all')}
                className={cn(
                  'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                  selectedCategory === 'all'
                    ? 'bg-zinc-200 dark:bg-[var(--color-hover-bg)] text-zinc-900 dark:text-[var(--color-text-primary)]'
                    : 'text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]'
                )}
              >
                All
              </button>
              {Object.entries(categoryConfig)
                .filter(([key]) => activeCategories.has(key as ToolCategory))
                .map(([key, config]) => (
                  <button
                    key={key}
                    onClick={() => setSelectedCategory(key as ToolCategory)}
                    className={cn(
                      'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                      selectedCategory === key
                        ? 'bg-zinc-200 dark:bg-[var(--color-hover-bg)] text-zinc-900 dark:text-[var(--color-text-primary)]'
                        : 'text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]'
                    )}
                  >
                    {config.label}
                  </button>
                ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading && (
            <div className="flex items-center justify-center py-12 text-[var(--color-text-secondary)]">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading plugins...
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center gap-2 py-12 text-red-400">
              <AlertCircle className="h-5 w-5" />
              {error}
            </div>
          )}

          {!loading && !error && filteredGroups.length === 0 && (
            <div className="py-12 text-center text-[var(--color-text-secondary)]">No tools match your search</div>
          )}

          {!loading &&
            !error &&
            filteredGroups.map(({ plugin, tools }) => {
              // Use API-driven display name and icon
              const pluginDisplayName = plugin.displayName || humanizeName(plugin.name)
              const PluginIcon = resolveIconName(plugin.icon)
              return (
                <div key={plugin.name} className="mb-8">
                  <div className="mb-3 flex items-center gap-2">
                    <PluginIcon className="h-5 w-5 text-[var(--color-text-secondary)]" />
                    <h2 className="text-sm font-semibold text-zinc-700 dark:text-[var(--color-text-primary)]">{pluginDisplayName}</h2>
                    <span className="rounded-full bg-zinc-200 dark:bg-[var(--color-bg-secondary)] px-2 py-0.5 text-xs text-[var(--color-text-secondary)]">
                      {tools.length}
                    </span>
                    {plugin.capability && (
                      <span className="rounded-full bg-zinc-100 dark:bg-[var(--card-bg)] px-2 py-0.5 text-xs text-[var(--color-text-tertiary)]">
                        {plugin.capability}
                      </span>
                    )}
                    {plugin.alwaysEnabled && (
                      <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-xs text-green-500">
                        always on
                      </span>
                    )}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {tools.map((tool) => (
                      <ToolCard
                        key={tool.id}
                        tool={tool}
                        enabled={isToolEnabled(tool.id)}
                        onToggle={() => handleToggleTool(tool.id)}
                        onSelect={() => setSelectedTool(tool)}
                        onConfigure={() => setConfigTool(tool)}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
        </div>
      </div>

      {/* Tool details panel */}
      {selectedTool && (
        <ToolDetailsPanel
          tool={selectedTool}
          enabled={isToolEnabled(selectedTool.id)}
          onToggle={() => handleToggleTool(selectedTool.id)}
          onClose={() => setSelectedTool(null)}
        />
      )}

      {/* Tool config dialog */}
      {configTool && (
        <ToolConfigDialog
          tool={configTool}
          botId={activeBot.id}
          currentConfigs={activeBot.toolConfigs}
          isOpen={!!configTool}
          onClose={() => setConfigTool(null)}
        />
      )}
    </div>
  )
}

// =============================================================================
// TOOL CARD
// =============================================================================

interface ToolCardProps {
  tool: Tool
  enabled: boolean
  onToggle: () => void
  onSelect: () => void
  onConfigure: () => void
}

function ToolCard({ tool, enabled, onToggle, onSelect, onConfigure }: ToolCardProps) {
  const riskConfig = {
    safe: { icon: Shield, color: 'text-green-500', bg: 'bg-green-500/10' },
    moderate: { icon: ShieldAlert, color: 'text-yellow-500', bg: 'bg-yellow-500/10' },
    dangerous: { icon: ShieldOff, color: 'text-red-500', bg: 'bg-red-500/10' },
    critical: { icon: ShieldBan, color: 'text-red-600', bg: 'bg-red-600/10' },
  }

  const config = riskConfig[tool.riskLevel] || riskConfig.safe
  const RiskIcon = config.icon

  return (
    <div
      className={cn(
        'group relative rounded-xl border p-4 transition-all',
        enabled
          ? 'border-cachi-500/50 bg-cachi-500/5'
          : 'border-zinc-200 dark:border-[var(--color-border-primary)] bg-zinc-50 dark:bg-[var(--color-bg-primary)]/30 hover:border-zinc-300 dark:hover:border-[var(--color-border-secondary)]'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-200 dark:bg-[var(--color-bg-secondary)]">
            <ToolIconRenderer toolId={tool.id} icon={tool.icon} className="h-5 w-5 text-zinc-700 dark:text-[var(--color-text-primary)]" />
          </div>
          <div>
            <h3 className="font-medium text-zinc-800 dark:text-[var(--color-text-primary)]">{tool.name}</h3>
            <div className={cn('flex items-center gap-1 text-xs', config.color)}>
              <RiskIcon className="h-3 w-3" />
              {tool.riskLevel}
            </div>
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
          className={cn('transition-colors', enabled ? 'text-cachi-500' : 'text-[var(--color-text-tertiary)]')}
        >
          {enabled ? <ToggleRight className="h-6 w-6" /> : <ToggleLeft className="h-6 w-6" />}
        </button>
      </div>

      {/* Description */}
      <p className="mt-3 text-sm text-[var(--color-text-secondary)] line-clamp-2">{tool.description}</p>

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={onSelect}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:bg-zinc-100 dark:hover:bg-[var(--color-hover-bg)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]"
        >
          <Info className="h-3 w-3" />
          Details
        </button>
        {tool.configParams && tool.configParams.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onConfigure()
            }}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:bg-zinc-100 dark:hover:bg-[var(--color-hover-bg)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]"
          >
            <Settings className="h-3 w-3" />
            Configure
          </button>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// TOOL DETAILS PANEL
// =============================================================================

interface ToolDetailsPanelProps {
  tool: Tool
  enabled: boolean
  onToggle: () => void
  onClose: () => void
}

function ToolDetailsPanel({ tool, enabled, onToggle, onClose }: ToolDetailsPanelProps) {
  const riskConfig = {
    safe: {
      icon: Shield,
      color: 'text-green-500',
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
    },
    moderate: {
      icon: ShieldAlert,
      color: 'text-yellow-500',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
    },
    dangerous: {
      icon: ShieldOff,
      color: 'text-red-500',
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
    },
    critical: {
      icon: ShieldBan,
      color: 'text-red-600',
      bg: 'bg-red-600/10',
      border: 'border-red-600/30',
    },
  }

  const config = riskConfig[tool.riskLevel] || riskConfig.safe
  const RiskIcon = config.icon

  return (
    <div className="w-96 flex-shrink-0 border-l border-zinc-200 dark:border-[var(--color-border-primary)] bg-zinc-50 dark:bg-[var(--color-bg-primary)]/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-[var(--color-border-primary)] px-4 py-3">
        <h2 className="font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">Tool Details</h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:bg-zinc-100 dark:hover:bg-[var(--color-hover-bg)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]"
        >
          x
        </button>
      </div>

      <div className="p-4">
        {/* Tool info */}
        <div className="mb-6 flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-zinc-200 dark:bg-[var(--color-bg-secondary)]">
            <ToolIconRenderer toolId={tool.id} icon={tool.icon} className="h-7 w-7 text-zinc-700 dark:text-[var(--color-text-primary)]" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-zinc-900 dark:text-[var(--color-text-primary)]">{tool.name}</h3>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {categoryConfig[tool.category]?.label || tool.category}
            </p>
          </div>
        </div>

        {/* Risk level */}
        <div className={cn('mb-6 rounded-lg border p-4', config.bg, config.border)}>
          <div className={cn('flex items-center gap-2', config.color)}>
            <RiskIcon className="h-5 w-5" />
            <span className="font-medium capitalize">{tool.riskLevel} Risk</span>
          </div>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
            {tool.riskLevel === 'safe' &&
              'This tool is safe to use and cannot modify system resources.'}
            {tool.riskLevel === 'moderate' &&
              'This tool can modify files or execute code. Actions may require approval.'}
            {tool.riskLevel === 'dangerous' &&
              'This tool can perform system-level operations. Use with caution.'}
            {tool.riskLevel === 'critical' &&
              'This tool performs critical operations with significant risk. Requires explicit approval.'}
          </p>
        </div>

        {/* Description */}
        <div className="mb-6">
          <h4 className="mb-2 text-sm font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Description</h4>
          <p className="text-sm text-[var(--color-text-secondary)]">{tool.description}</p>
        </div>

        {/* Parameters */}
        {tool.parameters && tool.parameters.length > 0 && (
          <div className="mb-6">
            <h4 className="mb-2 text-sm font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Parameters</h4>
            <div className="space-y-2">
              {tool.parameters.map((param) => (
                <div key={param.name} className="rounded-lg border border-zinc-200 dark:border-[var(--color-border-primary)] bg-white dark:bg-[var(--color-bg-primary)] p-3">
                  <div className="flex items-center gap-2">
                    <code className="font-mono text-sm text-cachi-400">{param.name}</code>
                    <span className="rounded bg-zinc-200 dark:bg-[var(--color-bg-secondary)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]">
                      {param.type}
                    </span>
                    {param.required && (
                      <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
                        required
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{param.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={onToggle}
            className={cn(
              'flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors',
              enabled
                ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30'
                : 'bg-cachi-600 text-white hover:bg-cachi-500'
            )}
          >
            {enabled ? (
              <>
                <ToggleLeft className="h-4 w-4" />
                Disable
              </>
            ) : (
              <>
                <ToggleRight className="h-4 w-4" />
                Enable
              </>
            )}
          </button>
          <button className="flex items-center justify-center gap-2 rounded-lg bg-zinc-200 dark:bg-[var(--color-bg-secondary)] px-4 py-2 text-sm text-zinc-700 dark:text-[var(--color-text-primary)] hover:bg-zinc-200 dark:hover:bg-[var(--color-hover-bg)]">
            <Play className="h-4 w-4" />
            Test
          </button>
        </div>
      </div>
    </div>
  )
}
