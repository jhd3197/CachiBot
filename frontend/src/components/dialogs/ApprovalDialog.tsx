import { useState, useEffect } from 'react'
import { ShieldAlert, AlertTriangle, Code } from 'lucide-react'
import { Button } from '../common/Button'
import { getPendingApproval, onPendingApprovalChange } from '../../hooks/useWebSocket'
import { cn } from '../../lib/utils'
import type { ApprovalPayload } from '../../types'

interface ApprovalDialogProps {
  onApprove: (id: string, approved: boolean) => void
}

export function ApprovalDialog({ onApprove }: ApprovalDialogProps) {
  const [pendingApproval, setPendingApproval] = useState<ApprovalPayload | null>(getPendingApproval())

  useEffect(() => {
    return onPendingApprovalChange(setPendingApproval)
  }, [])

  if (!pendingApproval) return null

  const { id, tool, action, details } = pendingApproval
  const riskLevel = details.riskLevel || 'UNKNOWN'
  const reasons = details.reasons || []
  const code = details.code

  const isHighRisk = riskLevel === 'HIGH' || riskLevel === 'CRITICAL'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl dark:bg-zinc-900">
        {/* Header */}
        <div
          className={cn(
            'flex items-center gap-3 rounded-t-xl px-6 py-4',
            isHighRisk
              ? 'bg-red-50 dark:bg-red-900/20'
              : 'bg-amber-50 dark:bg-amber-900/20'
          )}
        >
          <div
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-full',
              isHighRisk
                ? 'bg-red-100 text-red-600 dark:bg-red-800 dark:text-red-300'
                : 'bg-amber-100 text-amber-600 dark:bg-amber-800 dark:text-amber-300'
            )}
          >
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold">Approval Required</h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {action}
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto p-6">
          {/* Tool info */}
          <div className="mb-4">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Tool</p>
            <p className="font-medium">{tool}</p>
          </div>

          {/* Risk level */}
          <div className="mb-4">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Risk Level</p>
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-sm font-medium',
                {
                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400':
                    riskLevel === 'CRITICAL',
                  'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400':
                    riskLevel === 'HIGH',
                  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400':
                    riskLevel === 'MEDIUM',
                  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400':
                    riskLevel === 'LOW',
                }
              )}
            >
              <AlertTriangle className="h-3 w-3" />
              {riskLevel}
            </span>
          </div>

          {/* Risk reasons */}
          {reasons.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-sm text-zinc-500 dark:text-zinc-400">
                Risk Factors
              </p>
              <ul className="space-y-1">
                {reasons.map((reason: string, index: number) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 text-sm"
                  >
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Code preview */}
          {code && (
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-sm text-zinc-500 dark:text-zinc-400">
                <Code className="h-4 w-4" />
                Code to Execute
              </div>
              <pre className="max-h-48 overflow-auto rounded-lg bg-zinc-900 p-4 text-sm text-zinc-100">
                <code>{code}</code>
              </pre>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <Button
            variant="secondary"
            onClick={() => onApprove(id, false)}
          >
            Deny
          </Button>
          <Button
            variant={isHighRisk ? 'danger' : 'primary'}
            onClick={() => onApprove(id, true)}
          >
            {isHighRisk ? 'Allow Anyway' : 'Approve'}
          </Button>
        </div>
      </div>
    </div>
  )
}
