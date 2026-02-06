import { Wrench, Check, X, Loader2 } from 'lucide-react'
import type { ToolCall } from '../../types'
import { cn } from '../../lib/utils'

interface ToolCallListProps {
  toolCalls: ToolCall[]
}

export function ToolCallList({ toolCalls }: ToolCallListProps) {
  return (
    <div className="space-y-2">
      {toolCalls.map((call) => (
        <ToolCallItem key={call.id} call={call} />
      ))}
    </div>
  )
}

interface ToolCallItemProps {
  call: ToolCall
}

function ToolCallItem({ call }: ToolCallItemProps) {
  const isComplete = call.endTime !== undefined
  const isSuccess = call.success !== false

  return (
    <div
      className={cn(
        'rounded-lg border p-3',
        isComplete
          ? isSuccess
            ? 'border-cachi-200 bg-cachi-50 dark:border-cachi-900 dark:bg-cachi-900/20'
            : 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-900/20'
          : 'border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800/50'
      )}
    >
      <div className="flex items-center gap-2">
        {/* Status icon */}
        <div
          className={cn(
            'flex h-6 w-6 items-center justify-center rounded-full',
            isComplete
              ? isSuccess
                ? 'bg-cachi-200 text-cachi-700 dark:bg-cachi-800 dark:text-cachi-300'
                : 'bg-red-200 text-red-700 dark:bg-red-800 dark:text-red-300'
              : 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300'
          )}
        >
          {isComplete ? (
            isSuccess ? (
              <Check className="h-3 w-3" />
            ) : (
              <X className="h-3 w-3" />
            )
          ) : (
            <Loader2 className="h-3 w-3 animate-spin" />
          )}
        </div>

        {/* Tool name */}
        <div className="flex items-center gap-1.5">
          <Wrench className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-sm font-medium">{call.tool}</span>
        </div>

        {/* Duration */}
        {isComplete && (
          <span className="ml-auto text-xs text-zinc-500">
            {((call.endTime! - call.startTime) / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      {/* Arguments preview */}
      {Object.keys(call.args).length > 0 ? (
        <div className="mt-2 overflow-x-auto">
          <pre className="text-xs text-zinc-600 dark:text-zinc-400">
            {JSON.stringify(call.args, null, 2).slice(0, 200)}
            {JSON.stringify(call.args, null, 2).length > 200 ? '...' : null}
          </pre>
        </div>
      ) : null}

      {/* Result preview */}
      {isComplete && call.result ? (
        <div className="mt-2 overflow-x-auto border-t border-zinc-200 pt-2 dark:border-zinc-700">
          <pre className="text-xs text-zinc-600 dark:text-zinc-400">
            {String(call.result).slice(0, 300)}
            {String(call.result).length > 300 ? '...' : null}
          </pre>
        </div>
      ) : null}
    </div>
  )
}
