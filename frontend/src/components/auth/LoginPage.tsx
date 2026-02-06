import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { checkSetupRequired, login } from '../../api/auth'
import { Button } from '../common/Button'

export function LoginPage() {
  const navigate = useNavigate()
  const { login: storeLogin, setSetupRequired, isLoading, setLoading } = useAuthStore()

  // Form state
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Check if setup is required on mount - redirect to setup page if needed
  useEffect(() => {
    const checkSetup = async () => {
      try {
        const { setup_required } = await checkSetupRequired()
        setSetupRequired(setup_required)
        if (setup_required) {
          navigate('/setup', { replace: true })
        }
      } catch (err) {
        console.error('Failed to check setup status:', err)
      } finally {
        setLoading(false)
      }
    }
    checkSetup()
  }, [setSetupRequired, setLoading, navigate])

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
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 mb-4">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">CachiBot</h1>
          <p className="text-zinc-400 mt-1">Sign in to continue</p>
        </div>

        {/* Form Card */}
        <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6">
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="identifier" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Email or Username
              </label>
              <input
                id="identifier"
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Enter your email or username"
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="loginPassword" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="loginPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-3 py-2 pr-10 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-zinc-300"
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
