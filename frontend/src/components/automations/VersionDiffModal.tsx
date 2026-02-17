import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

interface VersionDiffModalProps {
  open: boolean
  onClose: () => void
  oldVersion: number
  newVersion: number
  oldCode: string
  newCode: string
}

export function VersionDiffModal({
  open,
  onClose,
  oldVersion,
  newVersion,
  oldCode,
  newCode,
}: VersionDiffModalProps) {
  if (!open) return null

  const oldLines = oldCode.split('\n')
  const newLines = newCode.split('\n')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 flex max-h-[80vh] w-full max-w-5xl flex-col rounded-xl bg-white shadow-2xl dark:bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Version {oldVersion} vs Version {newVersion}
          </h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Diff content - side by side */}
        <div className="flex flex-1 overflow-hidden">
          {/* Old version */}
          <div className="flex-1 overflow-auto border-r border-zinc-200 dark:border-zinc-800">
            <div className="sticky top-0 border-b border-zinc-200 bg-red-50 px-4 py-2 text-xs font-medium text-red-700 dark:border-zinc-800 dark:bg-red-950/30 dark:text-red-400">
              v{oldVersion}
            </div>
            <pre className="p-4 text-xs">
              {oldLines.map((line, i) => (
                <div key={i} className="flex">
                  <span className="mr-4 w-8 flex-shrink-0 text-right text-zinc-400">{i + 1}</span>
                  <span className="text-zinc-700 dark:text-zinc-300">{line}</span>
                </div>
              ))}
            </pre>
          </div>

          {/* New version */}
          <div className="flex-1 overflow-auto">
            <div className="sticky top-0 border-b border-zinc-200 bg-green-50 px-4 py-2 text-xs font-medium text-green-700 dark:border-zinc-800 dark:bg-green-950/30 dark:text-green-400">
              v{newVersion}
            </div>
            <pre className="p-4 text-xs">
              {newLines.map((line, i) => (
                <div key={i} className="flex">
                  <span className="mr-4 w-8 flex-shrink-0 text-right text-zinc-400">{i + 1}</span>
                  <span className="text-zinc-700 dark:text-zinc-300">{line}</span>
                </div>
              ))}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
