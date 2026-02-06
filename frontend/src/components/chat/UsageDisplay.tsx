import { Coins, Zap, RotateCw } from 'lucide-react'
import type { UsagePayload } from '../../types'
import { formatCost, formatTokens } from '../../lib/utils'

interface UsageDisplayProps {
  usage: UsagePayload
}

export function UsageDisplay({ usage }: UsageDisplayProps) {
  return (
    <div className="flex items-center justify-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
      <div className="flex items-center gap-1.5">
        <Zap className="h-3.5 w-3.5" />
        <span>{formatTokens(usage.totalTokens)} tokens</span>
      </div>

      <div className="flex items-center gap-1.5">
        <Coins className="h-3.5 w-3.5" />
        <span>{formatCost(usage.totalCost)}</span>
      </div>

      <div className="flex items-center gap-1.5">
        <RotateCw className="h-3.5 w-3.5" />
        <span>{usage.iterations} iterations</span>
      </div>
    </div>
  )
}
