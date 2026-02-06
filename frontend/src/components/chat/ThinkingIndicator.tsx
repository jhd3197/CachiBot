import { Brain } from 'lucide-react'

interface ThinkingIndicatorProps {
  content: string
}

export function ThinkingIndicator({ content }: ThinkingIndicatorProps) {
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 flex-shrink-0 animate-thinking items-center justify-center rounded-full bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">
        <Brain className="h-4 w-4" />
      </div>

      <div className="flex-1 rounded-xl bg-purple-50 p-3 dark:bg-purple-900/20">
        <p className="mb-1 text-xs font-medium text-purple-700 dark:text-purple-400">
          Thinking...
        </p>
        <p className="text-sm italic text-purple-600 dark:text-purple-300">
          {content}
        </p>
      </div>
    </div>
  )
}
