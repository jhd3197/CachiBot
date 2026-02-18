import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Play,
  Save,
  GitBranch,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { ConsoleOutput } from '../automations/ConsoleOutput'
import { TimelineTab } from '../automations/TimelineTab'
import { VersionDiffModal } from '../automations/VersionDiffModal'
import {
  getScript,
  updateScript,
  runScript,
  getScriptVersions,
  approveScriptVersion,
  rollbackScriptVersion,
  type Script,
  type ScriptVersion,
} from '../../api/automations'
import type { LogLine } from '../../api/execution-log'
import { cn } from '../../lib/utils'

type EditorTab = 'code' | 'versions' | 'timeline' | 'console'

export function ScriptEditorView() {
  const navigate = useNavigate()
  const { activeBotId } = useBotStore()
  const params = useParams<{ scriptId: string }>()
  const scriptId = params.scriptId || (window.location.pathname.split('/automations/')[1]?.split('/')[0])

  const [script, setScript] = useState<Script | null>(null)
  const [code, setCode] = useState('')
  const [versions, setVersions] = useState<ScriptVersion[]>([])
  const [consoleLines, setConsoleLines] = useState<LogLine[]>([])
  const [activeTab, setActiveTab] = useState<EditorTab>('code')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [diffModal, setDiffModal] = useState<{
    open: boolean
    oldVersion: number
    newVersion: number
    oldCode: string
    newCode: string
  }>({ open: false, oldVersion: 0, newVersion: 0, oldCode: '', newCode: '' })

  useEffect(() => {
    if (!activeBotId || !scriptId) return
    let cancelled = false
    setLoading(true)

    getScript(activeBotId, scriptId)
      .then((data) => {
        if (cancelled) return
        setScript(data)
        setCode(data.sourceCode)
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          toast.error('Failed to load script')
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [activeBotId, scriptId])

  useEffect(() => {
    if (!activeBotId || !scriptId || activeTab !== 'versions') return
    getScriptVersions(activeBotId, scriptId).then(setVersions).catch(() => {})
  }, [activeBotId, scriptId, activeTab])

  const handleSave = useCallback(async () => {
    if (!activeBotId || !scriptId || !dirty) return
    setSaving(true)
    try {
      const updated = await updateScript(activeBotId, scriptId, {
        sourceCode: code,
        changelog: 'Manual edit',
      })
      setScript(updated)
      setDirty(false)
      toast.success('Script saved')
    } catch (err) {
      toast.error(`Save failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }, [activeBotId, scriptId, code, dirty])

  const handleRun = async () => {
    if (!activeBotId || !scriptId) return
    setRunning(true)
    setActiveTab('console')
    setConsoleLines([])
    try {
      await runScript(activeBotId, scriptId)
      toast.success('Script execution started')
      // Poll for log lines (simplified)
      setTimeout(() => setRunning(false), 3000)
    } catch (err) {
      toast.error(`Run failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setRunning(false)
    }
  }

  const handleCodeChange = (newCode: string) => {
    setCode(newCode)
    setDirty(newCode !== script?.sourceCode)
  }

  // Keyboard shortcut for save
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleSave])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-secondary)]" />
      </div>
    )
  }

  if (!script || !activeBotId) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--color-text-secondary)]">
        Script not found
      </div>
    )
  }

  const tabs: { id: EditorTab; label: string }[] = [
    { id: 'code', label: 'Code' },
    { id: 'versions', label: `Versions (${script.currentVersion})` },
    { id: 'timeline', label: 'Timeline' },
    { id: 'console', label: 'Console' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-[var(--color-border-primary)]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/${activeBotId}/automations`)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-text-secondary)] hover:bg-zinc-100 hover:text-[var(--color-text-tertiary)] dark:hover:bg-[var(--color-hover-bg)] dark:hover:text-[var(--color-text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-sm font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">
              {script.name}
            </h1>
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
              <span>v{script.currentVersion}</span>
              <span className={cn(
                'rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                script.status === 'active' ? 'bg-green-500/10 text-green-500' :
                script.status === 'error' ? 'bg-red-500/10 text-red-500' :
                'bg-zinc-500/10 text-[var(--color-text-secondary)]'
              )}>
                {script.status}
              </span>
              {dirty && <span className="text-yellow-500">* unsaved</span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className={cn(
              'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
              dirty
                ? 'bg-accent-600 text-white hover:bg-accent-700'
                : 'bg-zinc-100 text-[var(--color-text-secondary)] dark:bg-[var(--color-bg-secondary)]'
            )}
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
          >
            {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Run
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-zinc-200 px-4 dark:border-[var(--color-border-primary)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'border-b-2 px-3 py-2 text-xs font-medium transition-colors',
              activeTab === tab.id
                ? 'border-accent-600 text-accent-600 dark:text-accent-400'
                : 'border-transparent text-[var(--color-text-secondary)] hover:text-zinc-700 dark:hover:text-[var(--color-text-primary)]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'code' && (
          <div className="h-full">
            <textarea
              value={code}
              onChange={(e) => handleCodeChange(e.target.value)}
              spellCheck={false}
              className="h-full w-full resize-none bg-[var(--color-bg-app)] p-4 font-mono text-sm text-[var(--color-text-primary)] focus:outline-none"
              placeholder="# Write your Python script here..."
            />
          </div>
        )}

        {activeTab === 'versions' && (
          <div className="overflow-auto p-4">
            {versions.length === 0 ? (
              <div className="flex flex-col items-center py-8 text-[var(--color-text-secondary)]">
                <GitBranch className="mb-2 h-6 w-6" />
                <p className="text-sm">No versions yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {versions.map((v) => (
                  <div
                    key={v.id}
                    className="flex items-center justify-between rounded-lg border border-zinc-200 p-3 dark:border-[var(--color-border-primary)]"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-100 text-xs font-bold text-[var(--color-text-tertiary)] dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-secondary)]">
                        v{v.version}
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-900 dark:text-[var(--color-text-primary)]">
                          {v.changelog || 'No changelog'}
                        </p>
                        <p className="text-[10px] text-[var(--color-text-secondary)]">
                          {v.authorType} - {new Date(v.createdAt).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {v.approved ? (
                        <span className="flex items-center gap-1 text-[10px] text-green-500">
                          <CheckCircle2 className="h-3 w-3" /> Approved
                        </span>
                      ) : (
                        <button
                          onClick={() => {
                            approveScriptVersion(activeBotId, scriptId!, v.version)
                              .then((updated) => {
                                setVersions((prev) =>
                                  prev.map((ver) => (ver.id === updated.id ? updated : ver))
                                )
                                toast.success('Version approved')
                              })
                              .catch(() => toast.error('Failed to approve'))
                          }}
                          className="text-[10px] text-accent-600 hover:underline"
                        >
                          Approve
                        </button>
                      )}
                      {v.version !== script.currentVersion && (
                        <button
                          onClick={() => {
                            rollbackScriptVersion(activeBotId, scriptId!, v.version)
                              .then((updated) => {
                                setScript(updated)
                                setCode(updated.sourceCode)
                                setDirty(false)
                                toast.success(`Rolled back to v${v.version}`)
                              })
                              .catch(() => toast.error('Failed to rollback'))
                          }}
                          className="text-[10px] text-yellow-600 hover:underline"
                        >
                          Rollback
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="overflow-auto">
            <TimelineTab botId={activeBotId} sourceType="script" sourceId={scriptId!} />
          </div>
        )}

        {activeTab === 'console' && (
          <ConsoleOutput lines={consoleLines} className="h-full rounded-none" />
        )}
      </div>

      {/* Diff modal */}
      <VersionDiffModal
        open={diffModal.open}
        onClose={() => setDiffModal((s) => ({ ...s, open: false }))}
        oldVersion={diffModal.oldVersion}
        newVersion={diffModal.newVersion}
        oldCode={diffModal.oldCode}
        newCode={diffModal.newCode}
      />
    </div>
  )
}
