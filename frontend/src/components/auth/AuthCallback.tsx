import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Shield, Loader2, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../../stores/auth'
import { exchangeToken } from '../../api/auth'
import { Button } from '../common/Button'

export function AuthCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login: storeLogin, authMode } = useAuthStore()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = searchParams.get('token')

    if (!token) {
      setError('No token provided')
      return
    }

    const doExchange = async () => {
      try {
        const response = await exchangeToken({ token })
        storeLogin(response.user, response.access_token, response.refresh_token)
        toast.success(`Welcome, ${response.user.username}!`)
        navigate('/', { replace: true })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Token exchange failed'
        setError(message)
      }
    }

    doExchange()
  }, [searchParams, storeLogin, navigate])

  const websiteUrl = authMode?.login_url

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-100 dark:bg-zinc-950 px-4">
      <div className="w-full max-w-md text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-500 to-accent-600 mb-4">
          <Shield className="h-8 w-8 text-white" />
        </div>

        {error ? (
          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
            <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white mb-2">
              Authentication Failed
            </h2>
            <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">{error}</p>
            {websiteUrl && (
              <a href={websiteUrl}>
                <Button className="w-full justify-center">Back to Website</Button>
              </a>
            )}
          </div>
        ) : (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-accent-500 mx-auto mb-4" />
            <p className="text-zinc-500 dark:text-zinc-400">Signing you in...</p>
          </>
        )}
      </div>
    </div>
  )
}
