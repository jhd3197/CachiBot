import { useEffect, useRef } from 'react'
import { cn } from '../../lib/utils'
import type { LogLine } from '../../api/execution-log'

interface ConsoleOutputProps {
  lines: LogLine[]
  className?: string
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
      className={cn('console-output', className)}
    >
      {lines.length === 0 ? (
        <div className="console-output__empty">No output yet...</div>
      ) : (
        lines.map((line) => (
          <div key={line.id} className="console-output__line">
            <span className="console-output__timestamp">
              {new Date(line.timestamp).toLocaleTimeString()}
            </span>
            <span className={`console-output__level console-output__level--${line.level}`}>
              {line.level}
            </span>
            <span className="console-output__text">
              {line.content}
            </span>
          </div>
        ))
      )}
    </div>
  )
}
