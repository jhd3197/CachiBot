import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Loader2, ArrowRight, ChevronDown, ChevronUp, BarChart3, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { useTelemetryStore } from '../../stores/telemetry'
import { acceptConsent } from '../../api/telemetry'
import { Button } from '../common/Button'

const TERMS_VERSION = '1.0'

export function ConsentPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  const { status, refresh } = useTelemetryStore()

  const [termsAccepted, setTermsAccepted] = useState(false)
  const [telemetryEnabled, setTelemetryEnabled] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { replace: true })
      return
    }

    refresh().then(() => setLoading(false)).catch(() => setLoading(false))
  }, [isAuthenticated, navigate, refresh])

  // If terms already accepted, redirect to dashboard
  useEffect(() => {
    if (status?.terms_accepted) {
      navigate('/', { replace: true })
    }
  }, [status, navigate])

  const handleContinue = async () => {
    if (!termsAccepted) {
      toast.error('Please accept the Terms of Service to continue')
      return
    }

    setSubmitting(true)
    try {
      await acceptConsent({
        terms_accepted: true,
        terms_version: TERMS_VERSION,
        telemetry_enabled: telemetryEnabled,
      })
      await refresh()
      toast.success('Welcome to CachiBot!')
      navigate('/', { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save consent'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-zinc-950 px-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-500 to-accent-600 mb-4">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Welcome to CachiBot</h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1">Just a few things before we get started</p>
        </div>

        {/* Consent Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm space-y-6">
          {/* Terms Section */}
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3">Terms of Service</h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
              By using CachiBot, you agree to our{' '}
              <a
                href="https://cachibot.ai/terms"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-500 hover:text-accent-400 underline inline-flex items-center gap-0.5"
              >
                Terms of Service
                <ExternalLink className="h-3 w-3" />
              </a>{' '}
              and{' '}
              <a
                href="https://cachibot.ai/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-500 hover:text-accent-400 underline inline-flex items-center gap-0.5"
              >
                Privacy Policy
                <ExternalLink className="h-3 w-3" />
              </a>
              .
            </p>

            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-accent-600 focus:ring-accent-500 dark:border-zinc-600 dark:bg-zinc-800"
              />
              <span className="text-sm text-zinc-700 dark:text-zinc-300 group-hover:text-zinc-900 dark:group-hover:text-zinc-100">
                I accept the Terms of Service and Privacy Policy
              </span>
            </label>
          </div>

          {/* Analytics Section */}
          <div className="border-t border-zinc-200 dark:border-zinc-800 pt-5">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="h-4 w-4 text-zinc-500" />
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Anonymous Analytics</h3>
            </div>

            <label className="flex items-start gap-3 cursor-pointer group mb-3">
              <input
                type="checkbox"
                checked={telemetryEnabled}
                onChange={(e) => setTelemetryEnabled(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-accent-600 focus:ring-accent-500 dark:border-zinc-600 dark:bg-zinc-800"
              />
              <span className="text-sm text-zinc-700 dark:text-zinc-300 group-hover:text-zinc-900 dark:group-hover:text-zinc-100">
                Help improve CachiBot by sending anonymous usage statistics
              </span>
            </label>

            {/* Expandable details */}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
            >
              {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {showDetails ? 'Hide details' : 'What we collect & what we never collect'}
            </button>

            {showDetails && (
              <div className="mt-3 space-y-3 text-xs">
                <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-3">
                  <p className="font-medium text-green-600 dark:text-green-400 mb-1.5">What we collect:</p>
                  <ul className="space-y-1 text-zinc-600 dark:text-zinc-400">
                    <li>- App version, OS type, Python version</li>
                    <li>- Database type (sqlite/postgresql)</li>
                    <li>- Aggregate counts: bots, messages, users</li>
                    <li>- Uptime duration</li>
                    <li>- A random install ID (resettable)</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                  <p className="font-medium text-red-500 dark:text-red-400 mb-1.5">What we NEVER collect:</p>
                  <ul className="space-y-1 text-zinc-600 dark:text-zinc-400">
                    <li>- Messages or conversation content</li>
                    <li>- API keys or passwords</li>
                    <li>- Email addresses or usernames</li>
                    <li>- IP addresses (anonymized to 0.0.0.0)</li>
                    <li>- File paths or workspace content</li>
                  </ul>
                </div>
                <a
                  href="https://cachibot.ai/telemetry"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-accent-500 hover:text-accent-400"
                >
                  Full telemetry disclosure
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>

          {/* Continue button */}
          <Button
            onClick={handleContinue}
            className="w-full justify-center"
            disabled={!termsAccepted || submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Saving...
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </div>

        {/* Footer */}
        <p className="text-center text-zinc-500 text-xs mt-6">
          You can change analytics settings anytime in Settings &gt; Data &amp; Privacy
        </p>
      </div>
    </div>
  )
}
