import { useEffect, useRef } from 'react'
import { cn } from '../../lib/utils'
import type { LogLine } from '../../api/execution-log'

interface ConsoleOutputProps {
  lines: LogLine[]
  className?: string
}

const levelColors: Record<string, string> = {
  debug: 'text-zinc-500',
  info: 'text-blue-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
  stdout: 'text-zinc-300',
  stderr: 'text-red-300',
}

export function ConsoleOutput({ lines, className }: ConsoleOutputProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines])

  return (
    <div
      ref={containerRef}
      className={cn(
        'overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-xs',
        className
      )}
    >
      {lines.length === 0 ? (
        <div className="text-zinc-600">No output yet...</div>
      ) : (
        lines.map((line) => (
          <div key={line.id} className="flex gap-2 py-0.5">
            <span className="flex-shrink-0 text-zinc-600">
              {new Date(line.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={cn(
                'flex-shrink-0 w-12 text-right uppercase',
                levelColors[line.level] || 'text-zinc-500'
              )}
            >
              {line.level}
            </span>
            <span className="text-zinc-300 whitespace-pre-wrap break-all">
              {line.content}
            </span>
          </div>
        ))
      )}
    </div>
  )
}
