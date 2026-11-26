/**
 * FaroSection — the bot's Faro integration card (bot settings › Connections ›
 * Faro). The bridge status, Connect/Disconnect, plain setup guidance when
 * Faro is not running, and — while one of the bot's faro calls is waiting on
 * the human — the pending approvals with a Deny button each. Approving only
 * ever happens in Faro's own window; there is no Approve button here, by
 * design. Everything on this card is real backend state; the parent hides
 * the whole card while the bridge is unavailable and the bot is not
 * connected.
 */

import { useEffect, useState } from 'react'
import { Server } from 'lucide-react'
import { useFaroStore } from '../../stores/faro'
import { useBotAccess } from '../../hooks/useBotAccess'
import { Spinner } from '../common/Spinner'
import type { Bot } from '../../types'

function approvalLine(approval: {
  kind: string | null
  summary: string | null
  sessionName: string | null
}): string {
  const kind = approval.kind ? `${approval.kind}: ` : ''
  const summary = approval.summary || 'an action'
  const session = approval.sessionName ? ` on ${approval.sessionName}` : ''
  return `${kind}${summary}${session}`
}

export function FaroSection({ bot }: { bot: Bot }) {
  const { canEdit } = useBotAccess(bot.id)
  const faro = useFaroStore((s) => s.byBot[bot.id])
  const globalStatus = useFaroStore((s) => s.status)
  const [pending, setPending] = useState<string | null>(null)

  const loaded = faro !== undefined
  useEffect(() => {
    void useFaroStore.getState().fetchStatus()
    void useFaroStore.getState().ensureForBot(bot.id)
  }, [bot.id])

  if (!loaded) {
    return (
      <div className="faro-settings" data-testid="faro-section">
        <div className="faro-settings__statusrow">
          <Spinner size="sm" label="" aria-hidden="true" />
          <span className="faro-settings__sub">Checking the Faro bridge…</span>
        </div>
      </div>
    )
  }

  const connected = faro.connected
  const available = faro.available
  const canOperate = canEdit

  const run = (key: string, action: () => Promise<unknown>) => {
    setPending(key)
    action()
      .catch(() => undefined)
      .finally(() => setPending(null))
  }

  const stateLabel = connected
    ? available
      ? 'Connected'
      : 'Faro is not running'
    : available
      ? 'Not connected'
      : 'Unavailable'

  const statusSub = [
    connected && available && faro.version ? `bridge running (v${faro.version})` : null,
    !available ? (faro.reason ?? globalStatus?.reason ?? null) : null,
  ]
    .filter(Boolean)
    .join(' · ')

  const waitingOnFaro = faro.callInFlight
  const showApprovals = connected && waitingOnFaro && faro.pendingApprovals.length > 0
  const showPlainWaiting =
    connected && waitingOnFaro && faro.pendingApprovals.length === 0 && !faro.supportsApprovals

  return (
    <div className="faro-settings" data-testid="faro-section">
      <div className="faro-settings__statusrow">
        <Server size={14} strokeWidth={1.8} aria-hidden="true" />
        <span className="faro-settings__state" data-state={connected && available ? 'on' : 'off'}>
          {stateLabel}
        </span>
        {statusSub && <span className="faro-settings__sub">{statusSub}</span>}
      </div>

      {!connected && !available && (
        <p className="faro-settings__guidance">
          Open Faro and turn on the Agent Bridge, then connect the bot here. CachiBot only talks
          to the bridge on this machine — your Faro credentials never leave Faro.
        </p>
      )}
      {!connected && available && (
        <p className="faro-settings__guidance">
          Connect this bot to lend it your Faro sessions. Every change it makes is approved by you
          in Faro first.
        </p>
      )}

      {showApprovals && (
        <div className="faro-approvals">
          {faro.pendingApprovals.map((approval) => (
            <div key={approval.requestId} className="faro-approvals__row">
              <span className="faro-approvals__text" title={approvalLine(approval)}>
                Faro is waiting for you: {approvalLine(approval)} — approve it in Faro
              </span>
              {canOperate && (
                <button
                  type="button"
                  className="faro-approvals__btn"
                  disabled={pending !== null}
                  onClick={() =>
                    run(approval.requestId, () =>
                      useFaroStore.getState().denyApproval(bot.id, approval.requestId)
                    )
                  }
                >
                  {pending === approval.requestId ? 'Denying…' : 'Deny'}
                </button>
              )}
            </div>
          ))}
          <p className="faro-approvals__hint">Approving happens in Faro — Deny is the only
            answer from here.</p>
        </div>
      )}

      {showPlainWaiting && (
        <p className="faro-approvals__hint">
          Waiting on Faro — it may be asking you to approve in the Faro window.
        </p>
      )}

      {canOperate && (
        <div className="faro-settings__actions">
          {!connected ? (
            <button
              type="button"
              className="faro-settings__btn faro-settings__btn--primary"
              disabled={pending !== null || !available}
              onClick={() => run('connect', () => useFaroStore.getState().connect(bot.id))}
            >
              {pending === 'connect' ? 'Connecting…' : 'Connect'}
            </button>
          ) : (
            <button
              type="button"
              className="faro-settings__btn"
              disabled={pending !== null}
              onClick={() => run('disconnect', () => useFaroStore.getState().disconnect(bot.id))}
            >
              {pending === 'disconnect' ? 'Disconnecting…' : 'Disconnect'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
