import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, Loader2, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { checkSetupRequired, getAuthMode, login } from '../../api/auth'
import { Button } from '../common/Button'

export function LoginPage() {
  const navigate = useNavigate()
  const {
    login: storeLogin,
    setSetupRequired,
    setLegacyDbDetected,
    setAuthMode,
    authMode,
    isLoading,
    setLoading,
  } = useAuthStore()

  // Form state
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Check auth mode and setup status on mount
  useEffect(() => {
    const init = async () => {
      try {
        // Fetch auth mode first
        const mode = await getAuthMode()
        setAuthMode(mode)

        // In cloud mode, skip setup check (handled by website)
        if (mode.mode === 'cloud') {
          setLoading(false)
          return
        }

        // Selfhosted: check setup
        const { setup_required, legacy_db_detected } = await checkSetupRequired()
        setSetupRequired(setup_required)
        if (legacy_db_detected) {
          setLegacyDbDetected(true)
          navigate('/upgrade', { replace: true })
          return
        }
        if (setup_required) {
          navigate('/setup', { replace: true })
        }
      } catch (err) {
        console.error('Failed to check auth mode:', err)
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [setSetupRequired, setAuthMode, setLoading, navigate])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!identifier.trim() || !password) {
      toast.error('Please enter your credentials')
      return
    }

    setSubmitting(true)
    try {
      const response = await login({
        identifier: identifier.trim(),
        password,
      })
      storeLogin(response.user, response.access_token, response.refresh_token)
      toast.success(`Welcome back, ${response.user.username}!`)
      navigate('/')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="layout-auth">
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--accent-500)' }} />
      </div>
    )
  }

  // Cloud mode: show redirect to website
  if (authMode?.mode === 'cloud' && authMode.login_url) {
    return (
      <div className="layout-auth">
        <div className="login">
          <div className="login__logo">
            <div className="login__logo-icon">
              <Shield size={32} style={{ color: 'white' }} />
            </div>
            <h1 className="login__title">CachiBot</h1>
            <p className="login__subtitle">Sign in to continue</p>
          </div>

          <div className="login__card" style={{ textAlign: 'center' }}>
            <p className="login__cloud-text">
              This platform uses cachibot.ai for authentication.
            </p>
            <a href={authMode.login_url}>
              <Button className="login__submit">
                <ExternalLink size={16} style={{ marginRight: '0.5rem' }} />
                Sign in via cachibot.ai
              </Button>
            </a>
          </div>

          <p className="login__footer">
            The Armored AI Agent
          </p>
        </div>
      </div>
    )
  }

  // Selfhosted mode: standard login form
  return (
    <div className="layout-auth">
      <div className="login">
        {/* Logo */}
        <div className="login__logo">
          <div className="login__logo-icon">
            <Shield size={32} style={{ color: 'white' }} />
          </div>
          <h1 className="login__title">CachiBot</h1>
          <p className="login__subtitle">Sign in to continue</p>
        </div>

        {/* Form Card */}
        <div className="login__card">
          <form onSubmit={handleLogin} className="login__form">
            <div className="login__field">
              <label htmlFor="identifier" className="login__label">
                Email or Username
              </label>
              <input
                id="identifier"
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Enter your email or username"
                className="login__input"
                required
                autoFocus
              />
            </div>

            <div className="login__field">
              <label htmlFor="loginPassword" className="login__label">
                Password
              </label>
              <div className="login__password-wrap">
                <input
                  id="loginPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="login__input"
                  style={{ paddingRight: '2.5rem' }}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="login__password-toggle"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              className="login__submit"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" style={{ marginRight: '0.5rem' }} />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </div>

        {/* Footer */}
        <p className="login__footer">
          The Armored AI Agent
        </p>
      </div>
    </div>
  )
}
