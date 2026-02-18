import { useState, useEffect, useCallback } from 'react'
import {
  X,
  Settings,
  Wrench,
  Search,
  ToggleLeft,
  ToggleRight,
  Loader2,
  FileText,
  Code,
  GitBranch,
  Terminal,
  Globe,
  Database,
  MessageSquare,
  Briefcase,
  Image,
  AudioLines,
  Sparkles,
} from 'lucide-react'
import { Button } from '../common/Button'
import { ModelSelect } from '../common/ModelSelect'
import { useUIStore } from '../../stores/ui'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { useAuthStore } from '../../stores/auth'
import { usePlatformToolsStore } from '../../stores/platform-tools'
import { updateConfig } from '../../api/client'
import * as skillsApi from '../../api/skills'
import { cn } from '../../lib/utils'
import type { SkillDefinition } from '../../types'

type SettingsTab = 'general' | 'platform-tools'

export function SettingsDialog() {
  const { settingsOpen, setSettingsOpen, showThinking, setShowThinking, showCost, setShowCost } = useUIStore()
  const { config, updateConfig: updateLocalConfig } = useConfigStore()
  const { defaultModel, updateDefaultModel } = useModelsStore()
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')

  const isAdmin = user?.role === 'admin'

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
      <div className={cn(
        'w-full rounded-xl bg-white shadow-xl dark:bg-[var(--color-bg-primary)]',
        activeTab === 'platform-tools' ? 'max-w-2xl' : 'max-w-md'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-[var(--color-border-primary)]">
          <h2 className="text-lg font-semibold">Settings</h2>
          <Button variant="ghost" size="sm" onClick={() => setSettingsOpen(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Tabs */}
        {isAdmin && (
          <div className="flex border-b border-zinc-200 px-6 dark:border-[var(--color-border-primary)]">
            <button
              onClick={() => setActiveTab('general')}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === 'general'
                  ? 'border-cachi-500 text-cachi-600 dark:text-cachi-400'
                  : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
              )}
            >
              <Settings className="h-4 w-4" />
              General
            </button>
            <button
              onClick={() => setActiveTab('platform-tools')}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === 'platform-tools'
                  ? 'border-cachi-500 text-cachi-600 dark:text-cachi-400'
                  : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
              )}
            >
              <Wrench className="h-4 w-4" />
              Platform Tools
            </button>
          </div>
        )}

        {/* Content */}
        <div className="max-h-[70vh] overflow-y-auto p-6">
          {activeTab === 'general' && (
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
                  <p className="truncate text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
                    {config.workspacePath}
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'platform-tools' && isAdmin && (
            <PlatformToolsTab />
          )}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// PLATFORM TOOLS TAB
// =============================================================================

// Capability metadata for display
const CAPABILITY_META: Record<string, { label: string; description: string; icon: React.ComponentType<{ className?: string }> }> = {
  fileOperations: { label: 'File Operations', description: 'Read, write, edit, and list files in the workspace', icon: FileText },
  codeExecution: { label: 'Code Execution', description: 'Run Python code in a sandboxed environment', icon: Code },
  gitOperations: { label: 'Git Operations', description: 'Git status, diff, log, commit, and branch management', icon: GitBranch },
  shellAccess: { label: 'Shell Access', description: 'Execute shell commands and check available programs', icon: Terminal },
  webAccess: { label: 'Web Access', description: 'Fetch web pages, search the web, and make HTTP requests', icon: Globe },
  dataOperations: { label: 'Data Operations', description: 'SQLite queries, ZIP/TAR compression and extraction', icon: Database },
  connections: { label: 'Platform Connections', description: 'Send messages via Telegram, Discord, and other platforms', icon: MessageSquare },
  workManagement: { label: 'Work Management', description: 'Create and manage work items, tasks, and background jobs', icon: Briefcase },
  imageGeneration: { label: 'Image Generation', description: 'Generate images via DALL-E, Imagen, Stability AI', icon: Image },
  audioGeneration: { label: 'Audio Generation', description: 'Text-to-speech and speech-to-text via OpenAI, ElevenLabs', icon: AudioLines },
}

function PlatformToolsTab() {
  const { config, loading, error, fetchConfig, toggleCapability, toggleSkill } = usePlatformToolsStore()
  const [allSkills, setAllSkills] = useState<SkillDefinition[]>([])
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillSearch, setSkillSearch] = useState('')

  // Load platform config + all skills (unfiltered — we need the full list here)
  const loadData = useCallback(async () => {
    await fetchConfig()
    setSkillsLoading(true)
    try {
      const skills = await skillsApi.getSkills()
      setAllSkills(skills)
    } catch {
      // Skills list failed — non-critical
    } finally {
      setSkillsLoading(false)
    }
  }, [fetchConfig])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
        <span className="text-sm text-[var(--color-text-secondary)]">Loading platform tools...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
        {error}
      </div>
    )
  }

  if (!config) return null

  const filteredSkills = allSkills.filter((skill) => {
    if (!skillSearch) return true
    const q = skillSearch.toLowerCase()
    return (
      skill.name.toLowerCase().includes(q) ||
      skill.description.toLowerCase().includes(q) ||
      skill.tags.some((t) => t.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
        Disable capabilities or skills globally. Disabled items won't appear in any bot's settings or be available at runtime.
      </p>

      {/* Capabilities */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">Capabilities</h3>
        <div className="space-y-2">
          {Object.entries(CAPABILITY_META).map(([key, meta]) => {
            const disabled = config.disabledCapabilities.includes(key)
            const Icon = meta.icon
            return (
              <div
                key={key}
                className={cn(
                  'flex items-center justify-between rounded-lg border p-3 transition-colors',
                  disabled
                    ? 'border-red-500/30 bg-red-500/5'
                    : 'border-[var(--color-border-secondary)] bg-[var(--card-bg)]'
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon className={cn('h-4 w-4', disabled ? 'text-red-400' : 'text-[var(--color-text-secondary)]')} />
                  <div>
                    <div className="text-sm font-medium text-[var(--color-text-primary)]">{meta.label}</div>
                    <div className="text-xs text-[var(--color-text-secondary)]">{meta.description}</div>
                  </div>
                </div>
                <button
                  onClick={() => toggleCapability(key)}
                  className={disabled ? 'text-red-400' : 'text-cachi-500'}
                  title={disabled ? 'Enable globally' : 'Disable globally'}
                >
                  {disabled
                    ? <ToggleLeft className="h-7 w-7" />
                    : <ToggleRight className="h-7 w-7" />}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* Skills */}
      <div className="border-t border-[var(--color-border-primary)] pt-6">
        <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">Skills</h3>

        {skillsLoading ? (
          <div className="flex items-center py-4 text-sm text-[var(--color-text-secondary)]">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading skills...
          </div>
        ) : allSkills.length === 0 ? (
          <p className="text-sm text-[var(--color-text-secondary)]">No skills installed.</p>
        ) : (
          <>
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
              <input
                type="text"
                value={skillSearch}
                onChange={(e) => setSkillSearch(e.target.value)}
                placeholder="Search skills..."
                className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--input-placeholder)] focus:border-[var(--color-border-focus)] focus:outline-none"
              />
            </div>

            <div className="max-h-60 space-y-2 overflow-y-auto">
              {filteredSkills.map((skill) => {
                const disabled = config.disabledSkills.includes(skill.id)
                return (
                  <div
                    key={skill.id}
                    className={cn(
                      'flex items-center justify-between rounded-lg border p-3 transition-colors',
                      disabled
                        ? 'border-red-500/30 bg-red-500/5'
                        : 'border-[var(--color-border-secondary)] bg-[var(--card-bg)]'
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Sparkles className={cn('h-3.5 w-3.5', disabled ? 'text-red-400' : 'text-[var(--color-text-secondary)]')} />
                        <span className="text-sm font-medium text-[var(--color-text-primary)]">{skill.name}</span>
                        {skill.version && (
                          <span className="rounded bg-[var(--color-hover-bg)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]">
                            v{skill.version}
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-[var(--color-text-secondary)]">{skill.description}</p>
                    </div>
                    <button
                      onClick={() => toggleSkill(skill.id)}
                      className={cn('ml-3 flex-shrink-0', disabled ? 'text-red-400' : 'text-cachi-500')}
                      title={disabled ? 'Enable globally' : 'Disable globally'}
                    >
                      {disabled
                        ? <ToggleLeft className="h-7 w-7" />
                        : <ToggleRight className="h-7 w-7" />}
                    </button>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Summary */}
      <div className="text-center text-xs text-[var(--color-text-secondary)]">
        {config.disabledCapabilities.length} capabilities disabled,{' '}
        {config.disabledSkills.length} skills disabled
      </div>
    </div>
  )
}

// =============================================================================
// TOGGLE COMPONENT
// =============================================================================

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
        <p className="text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-cachi-600' : 'bg-zinc-200 dark:bg-[var(--color-hover-bg)]'
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
