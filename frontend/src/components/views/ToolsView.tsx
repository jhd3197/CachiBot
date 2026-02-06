import { useState } from 'react'
import {
  Search,
  Shield,
  ShieldAlert,
  ShieldOff,
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
} from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { ToolIconRenderer } from '../common/ToolIconRenderer'
import { ToolConfigDialog } from '../dialogs/ToolConfigDialog'
import { cn } from '../../lib/utils'
import type { Tool, ToolCategory } from '../../types'

// Mock tools data - in a real app, this would come from the backend
const availableTools: Tool[] = [
  {
    id: 'file_read',
    name: 'File Read',
    description: 'Read contents of files in the workspace',
    category: 'filesystem',
    icon: 'file-text',
    enabled: true,
    riskLevel: 'safe',
  },
  {
    id: 'file_write',
    name: 'File Write',
    description: 'Create or modify files in the workspace',
    category: 'filesystem',
    icon: 'file-pen',
    enabled: true,
    riskLevel: 'moderate',
  },
  {
    id: 'file_delete',
    name: 'File Delete',
    description: 'Delete files from the workspace',
    category: 'filesystem',
    icon: 'trash',
    enabled: false,
    riskLevel: 'dangerous',
  },
  {
    id: 'python_execute',
    name: 'Python Execute',
    description: 'Execute Python code in a sandboxed environment',
    category: 'code',
    icon: 'code',
    enabled: true,
    riskLevel: 'moderate',
  },
  {
    id: 'shell_run',
    name: 'Shell Run',
    description: 'Run shell commands (restricted)',
    category: 'system',
    icon: 'terminal',
    enabled: true,
    riskLevel: 'dangerous',
  },
  {
    id: 'web_fetch',
    name: 'Web Fetch',
    description: 'Fetch content from URLs',
    category: 'web',
    icon: 'globe',
    enabled: false,
    riskLevel: 'moderate',
  },
  {
    id: 'web_search',
    name: 'Web Search',
    description: 'Search the web for information',
    category: 'web',
    icon: 'search',
    enabled: false,
    riskLevel: 'safe',
  },
  {
    id: 'database_query',
    name: 'Database Query',
    description: 'Execute SQL queries on connected databases',
    category: 'data',
    icon: 'database',
    enabled: false,
    riskLevel: 'dangerous',
  },
]

const categoryConfig: Record<ToolCategory, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  filesystem: { label: 'Filesystem', icon: FileText },
  code: { label: 'Code Execution', icon: Code },
  web: { label: 'Web', icon: Globe },
  system: { label: 'System', icon: Terminal },
  data: { label: 'Data', icon: Database },
  custom: { label: 'Custom', icon: Puzzle },
}

export function ToolsView() {
  const { getActiveBot, updateBot } = useBotStore()
  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<ToolCategory | 'all'>('all')
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [configTool, setConfigTool] = useState<Tool | null>(null)

  const activeBot = getActiveBot()
  if (!activeBot) return null

  const filteredTools = availableTools.filter((tool) => {
    if (search && !tool.name.toLowerCase().includes(search.toLowerCase())) return false
    if (selectedCategory !== 'all' && tool.category !== selectedCategory) return false
    return true
  })

  const handleToggleTool = (toolId: string) => {
    const currentTools = activeBot.tools
    const newTools = currentTools.includes(toolId)
      ? currentTools.filter((id) => id !== toolId)
      : [...currentTools, toolId]
    updateBot(activeBot.id, { tools: newTools })
  }

  const isToolEnabled = (toolId: string) => activeBot.tools.includes(toolId)

  const groupedTools = filteredTools.reduce((acc, tool) => {
    if (!acc[tool.category]) acc[tool.category] = []
    acc[tool.category].push(tool)
    return acc
  }, {} as Record<ToolCategory, Tool[]>)

  return (
    <div className="flex h-full bg-zinc-950">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="border-b border-zinc-800 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-zinc-100">Tools</h1>
              <p className="text-sm text-zinc-500">
                {activeBot.tools.length} tools enabled for {activeBot.name}
              </p>
            </div>

            {/* Risk level legend */}
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-green-500" />
                <span className="text-zinc-400">Safe</span>
              </div>
              <div className="flex items-center gap-1.5">
                <ShieldAlert className="h-4 w-4 text-yellow-500" />
                <span className="text-zinc-400">Moderate</span>
              </div>
              <div className="flex items-center gap-1.5">
                <ShieldOff className="h-4 w-4 text-red-500" />
                <span className="text-zinc-400">Dangerous</span>
              </div>
            </div>
          </div>

          {/* Search and filters */}
          <div className="mt-4 flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search tools..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-4 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500"
              />
            </div>

            <div className="flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800/50 p-1">
              <button
                onClick={() => setSelectedCategory('all')}
                className={cn(
                  'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                  selectedCategory === 'all'
                    ? 'bg-zinc-700 text-zinc-100'
                    : 'text-zinc-400 hover:text-zinc-200'
                )}
              >
                All
              </button>
              {Object.entries(categoryConfig).map(([key, config]) => (
                <button
                  key={key}
                  onClick={() => setSelectedCategory(key as ToolCategory)}
                  className={cn(
                    'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                    selectedCategory === key
                      ? 'bg-zinc-700 text-zinc-100'
                      : 'text-zinc-400 hover:text-zinc-200'
                  )}
                >
                  {config.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tools grid */}
        <div className="p-6">
          {Object.entries(groupedTools).map(([category, tools]) => (
            <div key={category} className="mb-8">
              <div className="mb-3 flex items-center gap-2">
                {(() => {
                  const Icon = categoryConfig[category as ToolCategory]?.icon || Puzzle
                  return <Icon className="h-5 w-5 text-zinc-500" />
                })()}
                <h2 className="text-sm font-semibold text-zinc-300">
                  {categoryConfig[category as ToolCategory]?.label || category}
                </h2>
                <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500">
                  {tools.length}
                </span>
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
          ))}

          {filteredTools.length === 0 && (
            <div className="py-12 text-center text-zinc-500">
              No tools match your search
            </div>
          )}
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
  }

  const config = riskConfig[tool.riskLevel]
  const RiskIcon = config.icon

  return (
    <div
      className={cn(
        'group relative rounded-xl border p-4 transition-all',
        enabled
          ? 'border-cachi-500/50 bg-cachi-500/5'
          : 'border-zinc-800 bg-zinc-900/30 hover:border-zinc-700'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-800">
            <ToolIconRenderer toolId={tool.id} className="h-5 w-5 text-zinc-300" />
          </div>
          <div>
            <h3 className="font-medium text-zinc-200">{tool.name}</h3>
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
          className={cn(
            'transition-colors',
            enabled ? 'text-cachi-500' : 'text-zinc-600'
          )}
        >
          {enabled ? (
            <ToggleRight className="h-6 w-6" />
          ) : (
            <ToggleLeft className="h-6 w-6" />
          )}
        </button>
      </div>

      {/* Description */}
      <p className="mt-3 text-sm text-zinc-500 line-clamp-2">{tool.description}</p>

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={onSelect}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        >
          <Info className="h-3 w-3" />
          Details
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onConfigure()
          }}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        >
          <Settings className="h-3 w-3" />
          Configure
        </button>
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
    safe: { icon: Shield, color: 'text-green-500', bg: 'bg-green-500/10', border: 'border-green-500/30' },
    moderate: { icon: ShieldAlert, color: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
    dangerous: { icon: ShieldOff, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30' },
  }

  const config = riskConfig[tool.riskLevel]
  const RiskIcon = config.icon

  return (
    <div className="w-96 flex-shrink-0 border-l border-zinc-800 bg-zinc-900/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <h2 className="font-semibold text-zinc-100">Tool Details</h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        >
          ×
        </button>
      </div>

      <div className="p-4">
        {/* Tool info */}
        <div className="mb-6 flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-zinc-800">
            <ToolIconRenderer toolId={tool.id} className="h-7 w-7 text-zinc-300" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-zinc-100">{tool.name}</h3>
            <p className="text-sm text-zinc-500">
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
          <p className="mt-2 text-sm text-zinc-400">
            {tool.riskLevel === 'safe' &&
              'This tool is safe to use and cannot modify system resources.'}
            {tool.riskLevel === 'moderate' &&
              'This tool can modify files or execute code. Actions may require approval.'}
            {tool.riskLevel === 'dangerous' &&
              'This tool can perform system-level operations. Use with caution.'}
          </p>
        </div>

        {/* Description */}
        <div className="mb-6">
          <h4 className="mb-2 text-sm font-medium text-zinc-300">Description</h4>
          <p className="text-sm text-zinc-500">{tool.description}</p>
        </div>

        {/* Parameters */}
        {tool.parameters && tool.parameters.length > 0 && (
          <div className="mb-6">
            <h4 className="mb-2 text-sm font-medium text-zinc-300">Parameters</h4>
            <div className="space-y-2">
              {tool.parameters.map((param) => (
                <div
                  key={param.name}
                  className="rounded-lg border border-zinc-800 bg-zinc-900 p-3"
                >
                  <div className="flex items-center gap-2">
                    <code className="text-sm font-mono text-cachi-400">{param.name}</code>
                    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500">
                      {param.type}
                    </span>
                    {param.required && (
                      <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
                        required
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">{param.description}</p>
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
          <button className="flex items-center justify-center gap-2 rounded-lg bg-zinc-800 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700">
            <Play className="h-4 w-4" />
            Test
          </button>
        </div>
      </div>
    </div>
  )
}
