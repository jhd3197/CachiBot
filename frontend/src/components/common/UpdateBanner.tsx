import { X, ArrowUpCircle } from 'lucide-react'
import { useUpdateStore } from '../../stores/update'

export function UpdateBanner() {
  const { showBanner, checkResult, dismissBanner, openDialog } = useUpdateStore()

  if (!showBanner || !checkResult) return null

  const latestVersion = checkResult.latest_stable || checkResult.latest_prerelease

  return (
    <div className="update-banner">
      <div className="update-banner__info">
        <ArrowUpCircle className="h-4 w-4 shrink-0" />
        <span>
          CachiBot <strong>v{latestVersion}</strong> is available{' '}
          <span className="text-caption">(current: v{checkResult.current_version})</span>
        </span>
      </div>
      <div className="update-banner__actions">
        <button onClick={openDialog} className="btn btn--primary btn--sm">
          View update
        </button>
        <button
          onClick={dismissBanner}
          className="update-banner__dismiss"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
