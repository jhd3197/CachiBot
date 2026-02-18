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
      <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    )
  }

  // Cloud mode: show redirect to website
  if (authMode?.mode === 'cloud' && authMode.login_url) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-zinc-950 px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-500 to-accent-600 mb-4">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">CachiBot</h1>
            <p className="text-zinc-500 dark:text-zinc-400 mt-1">Sign in to continue</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm text-center">
            <p className="text-zinc-600 dark:text-zinc-300 text-sm mb-4">
              This platform uses cachibot.ai for authentication.
            </p>
            <a href={authMode.login_url}>
              <Button className="w-full justify-center">
                <ExternalLink className="h-4 w-4 mr-2" />
                Sign in via cachibot.ai
              </Button>
            </a>
          </div>

          <p className="text-center text-zinc-500 text-sm mt-6">
            The Armored AI Agent
          </p>
        </div>
      </div>
    )
  }

  // Selfhosted mode: standard login form
  return (
    <div className="flex-1 min-h-0 flex items-center justify-center bg-zinc-100 dark:bg-zinc-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-500 to-accent-600 mb-4">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">CachiBot</h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1">Sign in to continue</p>
        </div>

        {/* Form Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="identifier" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Email or Username
              </label>
              <input
                id="identifier"
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Enter your email or username"
                className="w-full px-3 py-2 bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent"
                required
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="loginPassword" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="loginPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-3 py-2 pr-10 bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              className="w-full justify-center"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-zinc-500 text-sm mt-6">
          The Armored AI Agent
        </p>
      </div>
    </div>
  )
}
