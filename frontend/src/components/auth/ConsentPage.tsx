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
      <div className="layout-auth">
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--accent-500)' }} />
      </div>
    )
  }

  return (
    <div className="layout-auth">
      <div className="consent">
        {/* Logo */}
        <div className="consent__logo">
          <div className="consent__logo-icon">
            <Shield size={32} style={{ color: 'white' }} />
          </div>
          <h1 className="consent__title">Welcome to CachiBot</h1>
          <p className="consent__subtitle">Just a few things before we get started</p>
        </div>

        {/* Consent Card */}
        <div className="consent__card">
          {/* Terms Section */}
          <div>
            <h3 className="consent__section-title">Terms of Service</h3>
            <p className="consent__text">
              By using CachiBot, you agree to our{' '}
              <a
                href="https://cachibot.ai/terms"
                target="_blank"
                rel="noopener noreferrer"
                className="consent__link"
              >
                Terms of Service
                <ExternalLink size={12} />
              </a>{' '}
              and{' '}
              <a
                href="https://cachibot.ai/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="consent__link"
              >
                Privacy Policy
                <ExternalLink size={12} />
              </a>
              .
            </p>

            <label className="consent__option">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="consent__checkbox"
              />
              <span className="consent__option-text">
                I accept the Terms of Service and Privacy Policy
              </span>
            </label>
          </div>

          {/* Analytics Section */}
          <div className="consent__divider">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <BarChart3 size={16} style={{ color: 'var(--color-text-secondary)' }} />
              <h3 className="consent__section-title" style={{ marginBottom: 0 }}>Anonymous Analytics</h3>
            </div>

            <label className="consent__option" style={{ marginBottom: '0.75rem' }}>
              <input
                type="checkbox"
                checked={telemetryEnabled}
                onChange={(e) => setTelemetryEnabled(e.target.checked)}
                className="consent__checkbox"
              />
              <span className="consent__option-text">
                Help improve CachiBot by sending anonymous usage statistics
              </span>
            </label>

            {/* Expandable details */}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="consent__details-toggle"
            >
              {showDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showDetails ? 'Hide details' : 'What we collect & what we never collect'}
            </button>

            {showDetails && (
              <div className="consent__details">
                <div className="consent__details-box consent__details-box--positive">
                  <p className="consent__details-title consent__details-title--positive">What we collect:</p>
                  <ul className="consent__details-list">
                    <li>- App version, OS type, Python version</li>
                    <li>- Database type (sqlite/postgresql)</li>
                    <li>- Aggregate counts: bots, messages, users</li>
                    <li>- Uptime duration</li>
                    <li>- A random install ID (resettable)</li>
                  </ul>
                </div>
                <div className="consent__details-box consent__details-box--negative">
                  <p className="consent__details-title consent__details-title--negative">What we NEVER collect:</p>
                  <ul className="consent__details-list">
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
                  className="consent__link"
                >
                  Full telemetry disclosure
                  <ExternalLink size={12} />
                </a>
              </div>
            )}
          </div>

          {/* Continue button */}
          <Button
            onClick={handleContinue}
            className="consent__submit"
            disabled={!termsAccepted || submitting}
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" style={{ marginRight: '0.5rem' }} />
                Saving...
              </>
            ) : (
              <>
                Continue
                <ArrowRight size={16} style={{ marginLeft: '0.5rem' }} />
              </>
            )}
          </Button>
        </div>

        {/* Footer */}
        <p className="consent__footer">
          You can change analytics settings anytime in Settings &gt; Data &amp; Privacy
        </p>
      </div>
    </div>
  )
}
