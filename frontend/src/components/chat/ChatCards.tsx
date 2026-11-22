/**
 * UI v2 chat cards (design 03) — inline, never blocking the chat.
 * Every card is backed by a real WS payload or real client action:
 * - ErrorCard: the real WS `error` event (message + code)
 * - ApprovalCard: the real `approval_needed` payload, answered via
 *   wsClient.sendApproval (the backend supports allow/deny only — no
 *   "always allow" exists, so no such button is rendered)
 * - StoppedLine: the user pressed stop in this chat; Continue resends
 */

import { Square } from 'lucide-react'
import type { PendingApproval } from '../../stores/approvals'

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
