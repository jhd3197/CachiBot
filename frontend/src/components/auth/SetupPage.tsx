import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, Loader2, UserPlus, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { checkSetupRequired, setupAdmin } from '../../api/auth'
import { Button } from '../common/Button'

export function SetupPage() {
  const navigate = useNavigate()
  const { login: storeLogin, setSetupRequired, isLoading, setLoading } = useAuthStore()

  // Form state
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null)

  // Check if setup is required on mount
  useEffect(() => {
    const checkSetup = async () => {
      try {
        const { setup_required } = await checkSetupRequired()
        setSetupRequired(setup_required)
        setSetupNeeded(setup_required)

        // If setup is not required, redirect to login
        if (!setup_required) {
          navigate('/login', { replace: true })
        }
      } catch (err) {
        console.error('Failed to check setup status:', err)
        toast.error('Failed to check setup status')
      } finally {
        setLoading(false)
      }
    }
    checkSetup()
  }, [setSetupRequired, setLoading, navigate])

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !username.trim() || !password) {
      toast.error('Please fill in all fields')
      return
    }
    if (password !== confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    if (username.length < 3) {
      toast.error('Username must be at least 3 characters')
      return
    }

    setSubmitting(true)
    try {
      const response = await setupAdmin({
        email: email.trim().toLowerCase(),
        username: username.trim().toLowerCase(),
        password,
      })
      storeLogin(response.user, response.access_token, response.refresh_token)
      toast.success('Admin account created successfully!')
      navigate('/')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Setup failed'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading || setupNeeded === null) {
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
          <h1 className="text-2xl font-bold text-white">CachiBot Setup</h1>
          <p className="text-zinc-400 mt-1">Create your admin account to get started</p>
        </div>

        {/* Setup Card */}
        <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6">
          <form onSubmit={handleSetup} className="space-y-4">
            <div className="flex items-center gap-2 mb-4 p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
              <UserPlus className="h-5 w-5 text-blue-400 flex-shrink-0" />
              <p className="text-sm text-blue-300">
                Welcome! Set up your admin account to start using CachiBot.
              </p>
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                minLength={3}
                maxLength={32}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className="w-full px-3 py-2 pr-10 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                  minLength={8}
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

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-zinc-300 mb-1.5">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password"
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <Button
              type="submit"
              className="w-full justify-center"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Creating account...
                </>
              ) : (
                <>
                  Create Admin Account
                  <ArrowRight className="h-4 w-4 ml-2" />
                </>
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
