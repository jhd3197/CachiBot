import { X, ArrowUpCircle } from 'lucide-react'
import { useUpdateStore } from '../../stores/update'

export function UpdateBanner() {
  const { showBanner, checkResult, dismissBanner, openDialog } = useUpdateStore()

  if (!showBanner || !checkResult) return null

  const latestVersion = checkResult.latest_stable || checkResult.latest_prerelease

  return (
    <div className="flex items-center justify-between gap-3 bg-accent-600/10 border-b border-accent-600/20 px-4 py-2 text-sm">
      <div className="flex items-center gap-2 text-accent-400">
        <ArrowUpCircle className="h-4 w-4 shrink-0" />
        <span>
          CachiBot <strong>v{latestVersion}</strong> is available{' '}
          <span className="text-zinc-400">(current: v{checkResult.current_version})</span>
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={openDialog}
          className="rounded-md bg-accent-600 px-3 py-1 text-xs font-medium text-white hover:bg-accent-500 transition-colors"
        >
          View update
        </button>
        <button
          onClick={dismissBanner}
          className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
