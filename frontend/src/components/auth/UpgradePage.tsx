import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Loader2, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { resetLegacyDatabase, keepLegacyDatabase } from '../../api/auth'
import { Button } from '../common/Button'

export function UpgradePage() {
  const navigate = useNavigate()
  const { setLegacyDbDetected } = useAuthStore()
  const [submitting, setSubmitting] = useState(false)

  const handleReset = async () => {
    setSubmitting(true)
    try {
      await resetLegacyDatabase()
      setLegacyDbDetected(false)
      toast.success('Database reset successfully. Your old data has been backed up.')
      navigate('/setup', { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Reset failed'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleKeep = async () => {
    try {
      await keepLegacyDatabase()
      setLegacyDbDetected(false)
      navigate('/login', { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to continue'
      toast.error(message)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-[var(--color-bg-app)] px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 mb-4">
            <AlertTriangle className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Database Upgrade</h1>
          <p className="text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] mt-1">
            An older version of the database was detected
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-[var(--color-bg-primary)] rounded-xl border border-zinc-200 dark:border-[var(--color-border-primary)] p-6 shadow-sm space-y-4">
          <div className="flex items-start gap-3 p-3 bg-amber-500/10 rounded-lg border border-amber-500/20">
            <AlertTriangle className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-300">
              Your database was created with an older version of CachiBot that uses an
              incompatible schema. Your account still works, but bots and other data
              cannot be migrated automatically.
            </p>
          </div>

          <p className="text-sm text-[var(--color-text-tertiary)] dark:text-[var(--color-text-secondary)]">
            We recommend starting fresh with a clean database. Your old database will be
            safely backed up before any changes are made.
          </p>

          <Button
            onClick={handleReset}
            className="w-full justify-center"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Resetting...
              </>
            ) : (
              <>
                Start Fresh (Recommended)
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>

          <button
            onClick={handleKeep}
            disabled={submitting}
            className="w-full text-center text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:text-zinc-700 dark:hover:text-[var(--color-text-primary)] transition-colors"
          >
            Continue with existing database
          </button>

          <p className="text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] text-center">
            Your old database will be safely backed up before any changes.
          </p>
        </div>

        {/* Footer */}
        <p className="text-center text-[var(--color-text-secondary)] text-sm mt-6">
          The Armored AI Agent
        </p>
      </div>
    </div>
  )
}
