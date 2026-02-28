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
  Loader2,
  AlertCircle,
  X,
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
    <div className="tools-view">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="tools-header">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="tools-header__title">Tools</h1>
              <p className="tools-header__subtitle">
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
                      'tools-risk-btn',
                      `tools-risk-btn--${level}`,
                      allEnabled && 'tools-risk-btn--active'
                    )}
                  >
                    <RiskIcon className="h-3.5 w-3.5" />
                    <span className="capitalize">{level}</span>
                    <span className={cn(
                      'tools-risk-btn__count',
                      allEnabled ? 'tools-risk-btn__count--active' : 'tools-risk-btn__count--inactive'
                    )}>
                      {enabledAtLevel}/{totalAtLevel}
                    </span>
                  </button>
                )
              })}
              <div className="tools-divider" />
              <button onClick={handleEnableAll} className="tools-bulk-btn">
                All on
              </button>
              <button onClick={handleDisableAll} className="tools-bulk-btn">
                All off
              </button>
            </div>
          </div>

          {/* Search and filters */}
          <div className="mt-4 flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="tools-search__icon" />
              <input
                type="text"
                placeholder="Search tools..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="tools-search__input"
              />
            </div>

            <div className="tools-category-bar">
              <button
                onClick={() => setSelectedCategory('all')}
                className={cn(
                  'tools-category-btn',
                  selectedCategory === 'all' ? 'tools-category-btn--active' : 'tools-category-btn--inactive'
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
                      'tools-category-btn',
                      selectedCategory === key ? 'tools-category-btn--active' : 'tools-category-btn--inactive'
                    )}
                  >
                    {config.label}
                  </button>
                ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="tools-content">
          {loading && (
            <div className="tools-content__loading">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading plugins...
            </div>
          )}

          {error && (
            <div className="tools-content__error">
              <AlertCircle className="h-5 w-5" />
              {error}
            </div>
          )}

          {!loading && !error && filteredGroups.length === 0 && (
            <div className="tools-content__empty">No tools match your search</div>
          )}

          {!loading &&
            !error &&
            filteredGroups.map(({ plugin, tools }) => {
              // Use API-driven display name and icon
              const pluginDisplayName = plugin.displayName || humanizeName(plugin.name)
              const PluginIcon = resolveIconName(plugin.icon)
              return (
                <div key={plugin.name} className="tools-plugin-group">
                  <div className="tools-plugin-group__header">
                    <PluginIcon className="tools-plugin-group__icon" />
                    <h2 className="tools-plugin-group__name">{pluginDisplayName}</h2>
                    <span className="tools-plugin-group__count">
                      {tools.length}
                    </span>
                    {plugin.capability && (
                      <span className="tools-plugin-group__capability">
                        {plugin.capability}
                      </span>
                    )}
                    {plugin.alwaysEnabled && (
                      <span className="tools-plugin-group__always-on">
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

      {/* Tool detail modal */}
      {selectedTool && (
        <ToolDetailDialog
          tool={selectedTool}
          enabled={isToolEnabled(selectedTool.id)}
          onToggle={() => handleToggleTool(selectedTool.id)}
          onClose={() => setSelectedTool(null)}
          onConfigure={() => {
            setConfigTool(selectedTool)
            setSelectedTool(null)
          }}
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
        'tool-card group',
        enabled ? 'tool-card--enabled' : 'tool-card--disabled'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="tool-card__icon-box">
            <ToolIconRenderer toolId={tool.id} icon={tool.icon} className="tool-card__icon" />
          </div>
          <div>
            <h3 className="tool-card__name">{tool.name}</h3>
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
      <p className="tool-card__description line-clamp-2">{tool.description}</p>

      {/* Actions */}
      <div className="tool-card__actions">
        <button onClick={onSelect} className="tool-card__action-btn">
          <Info className="h-3 w-3" />
          Details
        </button>
        {tool.configParams && tool.configParams.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onConfigure()
            }}
            className="tool-card__action-btn"
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
// TOOL DETAIL DIALOG (modal)
// =============================================================================

interface ToolDetailDialogProps {
  tool: Tool
  enabled: boolean
  onToggle: () => void
  onClose: () => void
  onConfigure: () => void
}

function ToolDetailDialog({ tool, enabled, onToggle, onClose, onConfigure }: ToolDetailDialogProps) {
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
  const hasConfigParams = tool.configParams && tool.configParams.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-lg rounded-xl bg-[var(--color-bg-dialog)] shadow-xl border border-[var(--color-border-primary)]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border-primary)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-bg-secondary)]">
              <ToolIconRenderer toolId={tool.id} icon={tool.icon} className="h-5 w-5 text-[var(--color-text-primary)]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">{tool.name}</h2>
                <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', config.bg, config.color, 'border', config.border)}>
                  <RiskIcon className="h-3 w-3" />
                  {tool.riskLevel}
                </span>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)]">
                {categoryConfig[tool.category]?.label || tool.category}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto p-4 space-y-4">
          {/* Description */}
          <div>
            <h4 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">Description</h4>
            <p className="text-sm text-[var(--color-text-secondary)]">{tool.description}</p>
          </div>

          {/* Parameters */}
          {tool.parameters && tool.parameters.length > 0 && (
            <div>
              <h4 className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">Parameters</h4>
              <div className="space-y-2">
                {tool.parameters.map((param) => (
                  <div key={param.name} className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)] p-3">
                    <div className="flex items-center gap-2">
                      <code className="font-mono text-sm text-cachi-400">{param.name}</code>
                      <span className="rounded-sm bg-[var(--color-bg-secondary)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]">
                        {param.type}
                      </span>
                      {param.required && (
                        <span className="rounded-sm bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
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

          {/* Configure button */}
          {hasConfigParams && (
            <button
              onClick={onConfigure}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-border-secondary)] px-4 py-2.5 text-sm text-[var(--color-text-secondary)] hover:border-cachi-500 hover:text-cachi-400 transition-colors"
            >
              <Settings className="h-4 w-4" />
              Configure ({tool.configParams!.length} parameter{tool.configParams!.length > 1 ? 's' : ''})
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-[var(--color-border-primary)] p-4">
          <button
            onClick={onToggle}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
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
        </div>
      </div>
    </div>
  )
}
