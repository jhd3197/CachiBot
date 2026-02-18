import { Coins, Zap, RotateCw } from 'lucide-react'
import type { UsagePayload } from '../../types'
import { formatCost, formatTokens } from '../../lib/utils'

interface UsageDisplayProps {
  usage: UsagePayload
}

export function UsageDisplay({ usage }: UsageDisplayProps) {
  return (
    <div className="chat-usage">
      <div className="chat-usage__stat">
        <Zap className="h-3.5 w-3.5" />
        <span>{formatTokens(usage.totalTokens)} tokens</span>
      </div>

      <div className="chat-usage__stat">
        <Coins className="h-3.5 w-3.5" />
        <span>{formatCost(usage.totalCost)}</span>
      </div>

      <div className="chat-usage__stat">
        <RotateCw className="h-3.5 w-3.5" />
        <span>{usage.iterations} iterations</span>
      </div>
    </div>
  )
}
