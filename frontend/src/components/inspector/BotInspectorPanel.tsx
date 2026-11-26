/**
 * BotInspectorPanel — the collapsible right-hand bot inspector (a desktop
 * assistant's right sidebar), shown when a bot is selected in the v2 shell.
 *
 * Everything on it is real or hidden:
 * - header: the bot's avatar + name (BotAvatar + bot record)
 * - Activity / Library tabs: the live computer activity line and the recent
 *   runs (real executions API); Library is the bot's knowledge documents and
 *   only appears when there are any
 * - Suggested: only real prompts — a computer that needs you, open quick
 *   tasks — and hidden entirely when there is nothing to suggest
 * - Computer: the design-04 panel (state card, activity, windows), hidden
 *   when the computer feature is off
 * - Voice/Language: the app's real voice-mode settings (a preference the
 *   voice pipeline uses), shown read-only; hidden when absent
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PanelRightClose,
  CheckCircle2,
  XCircle,
  Ban,
  Hand,
  ListTodo,
  ChevronRight,
} from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useUIStore } from '../../stores/ui'
import { useComputerStore } from '../../stores/computer'
import { useKnowledgeStore } from '../../stores/knowledge'
import { useVoiceStore } from '../../stores/voice'
import { useBotAccess } from '../../hooks/useBotAccess'
import { getExecutions } from '../../api/execution-log'
import { getOpenTodos } from '../../api/client'
import { parseApiDate } from '../../lib/utils'
import { BotAvatar } from '../common/Avatar'
import { Spinner } from '../common/Spinner'
import { ComputerSection } from '../computer/ComputerSection'
import { COMPUTER_FACTS } from '../computer/utils'
import type { Bot } from '../../types'
import type { ExecutionLog } from '../../api/execution-log'
import { cn } from '../../lib/utils'

const NO_RUNS: ExecutionLog[] = []

export function BotInspectorPanel({ bot }: { bot: Bot }) {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const access = useBotAccess(bot.id)
  const toggleInspector = useUIStore((s) => s.toggleInspector)
  const computerStatus = useComputerStore((s) => s.status)
  const computer = useComputerStore((s) => s.byBot[bot.id])

  const [tab, setTab] = useState<'activity' | 'library'>('activity')
  const [runs, setRuns] = useState<ExecutionLog[] | null>(null)
  const [openTodos, setOpenTodos] = useState<number | null>(null)

  const docs = useKnowledgeStore((s) => s.documents[bot.id])
  const voiceSettings = useVoiceStore((s) => s.voiceSettings)

  useEffect(() => {
    void useKnowledgeStore.getState().loadDocuments(bot.id)
    getExecutions(bot.id, { limit: 6 })
      .then(setRuns)
      .catch(() => setRuns(NO_RUNS))
    if (access.canOperate) {
      getOpenTodos(bot.id)
        .then((todos) => setOpenTodos(todos.length))
        .catch(() => setOpenTodos(null))
    }
  }, [bot.id, access.canOperate])

  // Library is the real knowledge source; the tab appears only when the bot
  // has documents (never an always-empty tab).
  const hasLibrary = !!docs && docs.length > 0
  const effectiveTab = tab === 'library' && !hasLibrary ? 'activity' : tab

  // Suggested actions: real needs-you / take-over prompts and real open
  // quick tasks only. Nothing else is invented.
  const needsYou = computer?.state === 'needs_you'
  const suggested: { key: string; icon: typeof Hand; label: string; run: () => void }[] = []
  if (computerStatus?.available && needsYou) {
    suggested.push({
      key: 'needs-you',
      icon: Hand,
      label: computer.needsYou || 'Its computer needs you',
      run: () =>
        access.canOperate
          ? void useComputerStore.getState().respondNeedsYou(bot.id, 'takeover')
          : navigate(`/${bot.id}/chats`),
    })
  }
  if (access.canOperate && openTodos && openTodos > 0) {
    suggested.push({
      key: 'todos',
      icon: ListTodo,
      label: `${openTodos} open quick task${openTodos === 1 ? '' : 's'}`,
      run: () => navigate(`/${bot.id}/work`),
    })
  }

  const activityText =
    computer?.state === 'awake' || needsYou ? computer?.activity?.text : undefined

  return (
    <aside className="inspector" aria-label={`${bot.name} details`}>
      <div className="inspector__head">
        <BotAvatar color={bot.color} name={bot.name} size={56} />
        <span className="inspector__name">{bot.name}</span>
        <button
          type="button"
          className="v2-icon-btn inspector__collapse"
          aria-label="Hide panel"
          title="Hide panel"
          onClick={toggleInspector}
        >
          <PanelRightClose size={16} strokeWidth={1.8} />
        </button>
      </div>

      <div className="inspector__tabs" role="tablist" aria-label="Bot details">
        <button
          type="button"
          role="tab"
          aria-selected={effectiveTab === 'activity'}
          className={cn('inspector__tab', effectiveTab === 'activity' && 'inspector__tab--active')}
          onClick={() => setTab('activity')}
        >
          Activity
        </button>
        {hasLibrary && (
          <button
            type="button"
            role="tab"
            aria-selected={effectiveTab === 'library'}
            className={cn(
              'inspector__tab',
              effectiveTab === 'library' && 'inspector__tab--active'
            )}
            onClick={() => setTab('library')}
          >
            Library
          </button>
        )}
      </div>

      <div className="inspector__scroll">
        {effectiveTab === 'activity' ? (
          <div className="inspector__tabbody">
            {activityText && (
              <p className="inspector__activity-line">
                <Spinner size="sm" label="" aria-hidden="true" />
                {activityText}
              </p>
            )}
            {runs === null ? (
              <p className="inspector__empty">Loading…</p>
            ) : runs.length === 0 ? (
              <p className="inspector__empty">Nothing recent.</p>
            ) : (
              <ul className="inspector__runs">
                {runs.map((run) => (
                  <RunRow key={run.id} run={run} />
                ))}
              </ul>
            )}
            <button
              type="button"
              className="inspector__link"
              onClick={() => navigate('/runs')}
            >
              See all runs
              <ChevronRight size={13} strokeWidth={1.8} />
            </button>
          </div>
        ) : (
          <ul className="inspector__library">
            {(docs ?? []).map((doc) => (
              <li key={doc.id} className="inspector__doc">
                <span className="inspector__doc-name" title={doc.filename}>
                  {doc.filename}
                </span>
                <span className="inspector__doc-meta">
                  {[
                    doc.chunk_count > 0 ? `${doc.chunk_count} chunks` : null,
                    doc.status === 'processing'
                      ? 'Processing'
                      : doc.status === 'failed'
                        ? 'Failed'
                        : parseApiDate(doc.uploaded_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                          }),
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              </li>
            ))}
            <button
              type="button"
              className="inspector__link"
              onClick={() => navigate(`/${bot.id}/settings#knowledge`)}
            >
              Manage knowledge
              <ChevronRight size={13} strokeWidth={1.8} />
            </button>
          </ul>
        )}

        {suggested.length > 0 && (
          <section className="inspector__block" aria-label="Suggested">
            <h3 className="inspector__block-title">Suggested</h3>
            <div className="inspector__suggested">
              {suggested.map((s) => (
                <button key={s.key} type="button" className="inspector__suggested-row" onClick={s.run}>
                  <s.icon size={15} strokeWidth={1.8} />
                  <span className="inspector__suggested-label">{s.label}</span>
                  <ChevronRight size={14} strokeWidth={1.8} />
                </button>
              ))}
            </div>
          </section>
        )}

        {computerStatus?.available && (
          <section className="inspector__block" aria-label="Computer">
            <h3 className="inspector__block-title">Computer</h3>
            <ComputerSection bot={bot} canOperate={access.canOperate} userId={user?.id} />
            {(computer?.state === 'off' || computer?.state === undefined) && (
              <>
                <dl className="computer-facts">
                  {COMPUTER_FACTS.map((fact) => (
                    <div key={fact.label} className="computer-facts__row">
                      <dt className="computer-facts__label">{fact.label}</dt>
                      <dd>{fact.value}</dd>
                    </div>
                  ))}
                </dl>
                <button
                  type="button"
                  className="inspector__link"
                  onClick={() => navigate(`/${bot.id}/settings#computer`)}
                >
                  Change in bot settings
                  <ChevronRight size={13} strokeWidth={1.8} />
                </button>
              </>
            )}
          </section>
        )}

        {voiceSettings && (
          <section className="inspector__block" aria-label="Voice chat">
            <h3 className="inspector__block-title">Voice chat</h3>
            <div className="inspector__voice">
              <div className="inspector__voice-row">
                <span>Voice</span>
                <span className="inspector__voice-value">
                  {voiceSettings.ttsVoice} {voiceSettings.ttsSpeed}×
                </span>
              </div>
              <div className="inspector__voice-row">
                <span>Language</span>
                <span className="inspector__voice-value">
                  {voiceSettings.sttLanguage || 'Auto-detect'}
                </span>
              </div>
            </div>
          </section>
        )}
      </div>
    </aside>
  )
}

function RunRow({ run }: { run: ExecutionLog }) {
  const Icon =
    run.status === 'success'
      ? CheckCircle2
      : run.status === 'cancelled'
        ? Ban
        : XCircle
  const when = parseApiDate(run.startedAt)
  return (
    <li className="inspector__run" data-status={run.status}>
      {run.status === 'running' ? (
        <Spinner size="sm" label="" aria-hidden="true" />
      ) : (
        <Icon
          size={14}
          strokeWidth={1.8}
          className={cn(
            'inspector__run-icon',
            run.status === 'success' && 'inspector__run-icon--ok',
            (run.status === 'error' || run.status === 'timeout') && 'inspector__run-icon--error'
          )}
        />
      )}
      <span className="inspector__run-main">
        <span className="inspector__run-name" title={run.sourceName}>
          {run.sourceName || run.executionType}
        </span>
        <span className="inspector__run-meta">
          {run.executionType} ·{' '}
          {when.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
          {run.durationMs != null ? ` · ${formatDuration(run.durationMs)}` : ''}
        </span>
      </span>
    </li>
  )
}

function formatDuration(ms: number): string {
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
}
