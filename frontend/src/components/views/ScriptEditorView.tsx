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
    <div className="script-editor">
      {/* Header */}
      <div className="editor-header">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/${activeBotId}/automations`)}
            className="editor-header__back-btn"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="editor-header__title">
              {script.name}
            </h1>
            <div className="editor-header__meta">
              <span>v{script.currentVersion}</span>
              <span className={cn(
                'editor-header__status',
                script.status === 'active' ? 'editor-header__status--active' :
                script.status === 'error' ? 'editor-header__status--error' :
                'editor-header__status--default'
              )}>
                {script.status}
              </span>
              {dirty && <span className="editor-header__unsaved">* unsaved</span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className={cn(
              'editor-btn',
              dirty ? 'editor-btn--save' : 'editor-btn--save',
            )}
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className="editor-btn editor-btn--run"
          >
            {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Run
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="editor-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'editor-tab',
              activeTab === tab.id && 'editor-tab--active'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'code' && (
          <div className="editor-code">
            <textarea
              value={code}
              onChange={(e) => handleCodeChange(e.target.value)}
              spellCheck={false}
              className="editor-code__textarea"
              placeholder="# Write your Python script here..."
            />
          </div>
        )}

        {activeTab === 'versions' && (
          <div className="editor-versions">
            {versions.length === 0 ? (
              <div className="editor-versions__empty">
                <GitBranch className="mb-2 h-6 w-6" />
                <p className="text-sm">No versions yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {versions.map((v) => (
                  <div
                    key={v.id}
                    className="editor-versions__item"
                  >
                    <div className="flex items-center gap-3">
                      <div className="editor-versions__badge">
                        v{v.version}
                      </div>
                      <div>
                        <p className="editor-versions__name">
                          {v.changelog || 'No changelog'}
                        </p>
                        <p className="editor-versions__meta">
                          {v.authorType} - {new Date(v.createdAt).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {v.approved ? (
                        <span className="editor-versions__approved">
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
                          className="editor-versions__link editor-versions__link--approve"
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
                          className="editor-versions__link editor-versions__link--rollback"
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
