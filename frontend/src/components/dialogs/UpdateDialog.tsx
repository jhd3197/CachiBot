import { ArrowUpCircle, AlertTriangle, CheckCircle2, XCircle, ExternalLink } from 'lucide-react'
import { Dialog, DialogHeader, DialogContent, DialogFooter, DialogButton } from '../common/Dialog'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { Spinner } from '../common/Spinner'
import { useUpdateStore } from '../../stores/update'

export function UpdateDialog() {
  const {
    showDialog,
    closeDialog,
    checkResult,
    updateResult,
    isUpdating,
    isRestarting,
    optIntoBeta,
    performUpdate,
    restartServer,
    skipVersion,
    setOptIntoBeta,
  } = useUpdateStore()

  // In Electron, updates are handled via the native updater in Settings
  if (window.electronAPI?.isDesktop) return null

  if (!showDialog || !checkResult) return null

  const latestVersion = checkResult.latest_stable || checkResult.latest_prerelease

  // State: restarting
  if (isRestarting) {
    return (
      <Dialog open onClose={() => {}} closeOnBackdrop={false} closeOnEscape={false} size="md">
        <DialogHeader title="Restarting CachiBot" />
        <DialogContent>
          <div className="flex flex-col items-center gap-4 py-8">
            <Spinner size="lg" className="text-accent-500" />
            <p className="text-sm text-[var(--color-text-secondary)]">
              Waiting for the new server to come online...
            </p>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  // State: updating (pip install in progress)
  if (isUpdating) {
    return (
      <Dialog open onClose={() => {}} closeOnBackdrop={false} closeOnEscape={false} size="md">
        <DialogHeader
          title="Updating CachiBot"
          icon={<ArrowUpCircle className="h-5 w-5 text-accent-500" />}
        />
        <DialogContent>
          <div className="flex flex-col items-center gap-4 py-8">
            <Spinner size="lg" className="text-accent-500" />
            <p className="text-sm text-[var(--color-text-secondary)]">
              Installing CachiBot v{latestVersion}...
            </p>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  // State: result (success or failure)
  if (updateResult) {
    return (
      <Dialog open onClose={closeDialog} size="md">
        <DialogHeader
          title={updateResult.success ? 'Update Complete' : 'Update Failed'}
          icon={
            updateResult.success ? (
              <CheckCircle2 className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500" />
            )
          }
          onClose={closeDialog}
        />
        <DialogContent>
          <div className="space-y-3">
            <p className="text-sm text-[var(--color-text-primary)]">{updateResult.message}</p>
            {updateResult.success && (
              <p className="text-sm text-[var(--color-text-secondary)]">
                {updateResult.old_version} &rarr; {updateResult.new_version}
              </p>
            )}
            {updateResult.pip_output && (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-secondary)]">
                  Show pip output
                </summary>
                <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-[var(--color-bg-app)] p-3 text-xs text-[var(--color-text-secondary)]">
                  {updateResult.pip_output}
                </pre>
              </details>
            )}
          </div>
        </DialogContent>
        <DialogFooter>
          {updateResult.success ? (
            <>
              <DialogButton variant="secondary" onClick={closeDialog}>
                Later
              </DialogButton>
              <DialogButton variant="primary" onClick={restartServer}>
                Restart now
              </DialogButton>
            </>
          ) : (
            <DialogButton variant="secondary" onClick={closeDialog}>
              Close
            </DialogButton>
          )}
        </DialogFooter>
      </Dialog>
    )
  }

  // State: info (default view)
  return (
    <Dialog open onClose={closeDialog} size="lg">
      <DialogHeader
        title="Update Available"
        subtitle={`v${checkResult.current_version} → v${latestVersion}`}
        icon={<ArrowUpCircle className="h-5 w-5 text-accent-500" />}
        onClose={closeDialog}
      />
      <DialogContent scrollable maxHeight="max-h-[50vh]">
        <div className="space-y-4">
          {/* Docker warning */}
          {checkResult.is_docker && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-800/50 bg-yellow-900/20 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
              <p className="text-sm text-yellow-300">
                Running inside Docker. Auto-update is disabled — rebuild the container to update.
              </p>
            </div>
          )}

          {/* Release notes */}
          {checkResult.release_notes && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">Release Notes</h3>
              <div className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-app)] p-4">
                <MarkdownRenderer content={checkResult.release_notes} />
              </div>
            </div>
          )}

          {/* GitHub link */}
          {checkResult.release_url && (
            <a
              href={checkResult.release_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-accent-400 hover:text-accent-300"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View on GitHub
            </a>
          )}

          {/* Beta opt-in */}
          {checkResult.prerelease_available && (
            <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
              <input
                type="checkbox"
                checked={optIntoBeta}
                onChange={(e) => setOptIntoBeta(e.target.checked)}
                className="rounded border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] text-accent-600 focus:ring-accent-500"
              />
              Include pre-release / beta versions
            </label>
          )}
        </div>
      </DialogContent>
      <DialogFooter
        leftContent={
          latestVersion && (
            <DialogButton variant="ghost" onClick={() => skipVersion(latestVersion)}>
              Skip this version
            </DialogButton>
          )
        }
      >
        <DialogButton variant="secondary" onClick={closeDialog}>
          Not now
        </DialogButton>
        <DialogButton
          variant="primary"
          onClick={() => performUpdate()}
          disabled={checkResult.is_docker}
        >
          Update now
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}
