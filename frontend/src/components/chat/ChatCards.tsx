/**
 * UI v2 chat cards (design 03) — inline, never blocking the chat.
 * Every card is backed by a real WS payload or real client action:
 * - ErrorCard: the real WS `error` event (message + code)
 * - ApprovalCard: the real `approval_needed` payload, answered via
 *   wsClient.sendApproval (the backend supports allow/deny only — no
 *   "always allow" exists, so no such button is rendered)
 * - StoppedLine: the user pressed stop in this chat; Continue resends
 */

import { Square, Hand, Server } from 'lucide-react'
import type { PendingApproval } from '../../stores/approvals'
import { parseApiDate } from '../../lib/utils'

// -----------------------------------------------------------------------------
// Error card — failed turn, with the real fix actions
// -----------------------------------------------------------------------------

interface ErrorCardProps {
  message: string
  code?: string
  onTryAgain: () => void
  onChangeModel: () => void
}

export function ErrorCard({ message, code, onTryAgain, onChangeModel }: ErrorCardProps) {
  return (
    <div className="v2-card" role="alert">
      <p className="v2-card__text">{message}</p>
      {code && <p className="v2-card__meta">{code}</p>}
      <div className="v2-card__actions">
        <button type="button" className="v2-card__btn v2-card__btn--primary" onClick={onTryAgain}>
          Try again
        </button>
        <button type="button" className="v2-card__btn" onClick={onChangeModel}>
          Change the model
        </button>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------
// Approval card — inline answer to approval_needed (never blocks the chat)
// -----------------------------------------------------------------------------

interface ApprovalCardProps {
  approval: PendingApproval
  /** Backend supports a single allow/deny decision per request */
  onAnswer: (id: string, approved: boolean) => void
}

export function ApprovalCard({ approval, onAnswer }: ApprovalCardProps) {
  return (
    <div className="v2-card" data-tool={approval.tool}>
      <p className="v2-card__text">{approval.action}</p>
      {approval.code && (
        <pre className="v2-card__code">{approval.code}</pre>
      )}
      <div className="v2-card__actions">
        <button
          type="button"
          className="v2-card__btn v2-card__btn--primary"
          onClick={() => onAnswer(approval.id, true)}
        >
          Allow once
        </button>
        <button
          type="button"
          className="v2-card__btn"
          onClick={() => onAnswer(approval.id, false)}
        >
          Deny
        </button>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------
// Stopped line — user pressed stop; not an error (design 03 "Stopped")
// -----------------------------------------------------------------------------

interface StoppedLineProps {
  onContinue: () => void
}

export function StoppedLine({ onContinue }: StoppedLineProps) {
  return (
    <div className="v2-status-line">
      <Square className="v2-status-line__icon" />
      <span>You stopped this.</span>
      <span className="v2-status-line__actions">
        <button type="button" className="v2-text-btn" onClick={onContinue}>
          Continue
        </button>
      </span>
    </div>
  )
}

// -----------------------------------------------------------------------------
// Computer needs-you card (design 08) — the real C2 needs-you state.
// Take over hands the desktop to the person; "Skip this step" answers with
// the documented closest refusal (an approval is denied, a needs-person
// pause stops the run). Viewers see the reason without control buttons.
// -----------------------------------------------------------------------------

interface ComputerNeedsYouCardProps {
  reason: string
  /** Operator+ affordances; hidden for viewers (the API requires it). */
  onTakeOver?: () => void
  onSkip?: () => void
}

export function ComputerNeedsYouCard({ reason, onTakeOver, onSkip }: ComputerNeedsYouCardProps) {
  return (
    <div className="v2-card v2-card--needs-you" role="alert">
      <p className="v2-card__text">{reason}</p>
      {onTakeOver && (
        <div className="v2-card__actions">
          <button type="button" className="v2-card__btn v2-card__btn--primary" onClick={onTakeOver}>
            Take over
          </button>
          <button type="button" className="v2-card__btn" onClick={onSkip}>
            Skip this step
          </button>
        </div>
      )}
    </div>
  )
}

// -----------------------------------------------------------------------------
// Faro needs-you — Faro is waiting on the human (real `faro_update` state).
// Deny only: approving happens in Faro, never here.
// -----------------------------------------------------------------------------

interface FaroNeedsYouCardProps {
  botId: string
  /** One line per pending approval: kind + summary + session. */
  approvals: { requestId: string; line: string }[]
  /** Older Faro builds cannot list approvals — say the plain truth instead. */
  plainWaiting: boolean
  canOperate: boolean
  onDeny: (botId: string, requestId: string) => void
}

export function FaroNeedsYouCard({
  botId,
  approvals,
  plainWaiting,
  canOperate,
  onDeny,
}: FaroNeedsYouCardProps) {
  return (
    <div className="v2-card v2-card--needs-you" role="alert">
      {approvals.length > 0 ? (
        <>
          {approvals.map((approval) => (
            <p key={approval.requestId} className="v2-card__text">
              <Server size={13} strokeWidth={1.8} aria-hidden="true" /> Faro is waiting for you:{' '}
              {approval.line} — approve it in Faro
            </p>
          ))}
          <p className="v2-card__meta">Approving happens in Faro — Deny is the only answer here.</p>
          {canOperate && (
            <div className="v2-card__actions">
              {approvals.map((approval) => (
                <button
                  key={approval.requestId}
                  type="button"
                  className="v2-card__btn"
                  onClick={() => onDeny(botId, approval.requestId)}
                >
                  Deny
                </button>
              ))}
            </div>
          )}
        </>
      ) : plainWaiting ? (
        <p className="v2-card__text">
          <Server size={13} strokeWidth={1.8} aria-hidden="true" /> Waiting on Faro — it may be
          asking you to approve in the Faro window.
        </p>
      ) : null}
    </div>
  )
}

// -----------------------------------------------------------------------------
// "You took over" line — shown only while this user holds the lease (design 08)
// -----------------------------------------------------------------------------

interface ComputerDrivingLineProps {
  since: string
  onHandBack: () => void
}

export function ComputerDrivingLine({ since, onHandBack }: ComputerDrivingLineProps) {
  const at = parseApiDate(since)
  return (
    <div className="v2-status-line v2-status-line--needs-you">
      <Hand className="v2-status-line__icon" />
      <span>You took over at {at.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
      <span className="v2-status-line__actions">
        <button type="button" className="v2-text-btn" onClick={onHandBack}>
          Hand back
        </button>
      </span>
    </div>
  )
}
