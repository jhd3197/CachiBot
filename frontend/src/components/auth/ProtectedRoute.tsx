import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useTelemetryStore } from '../../stores/telemetry'
import { checkSetupRequired, getCurrentUser } from '../../api/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAdmin?: boolean
  requireManager?: boolean
}

export function ProtectedRoute({ children, requireAdmin = false, requireManager = false }: ProtectedRouteProps) {
  const location = useLocation()
  const {
    isAuthenticated,
    isLoading,
    user,
    setupRequired,
    setUser,
    setSetupRequired,
    setLoading,
    logout,
  } = useAuthStore()
  const { status: telemetryStatus, refresh: refreshTelemetry } = useTelemetryStore()

  const [checked, setChecked] = useState(false)
  const [consentChecked, setConsentChecked] = useState(false)

  useEffect(() => {
    const verifyAuth = async () => {
      // Check if setup is required first
      if (setupRequired === null) {
        try {
          const { setup_required } = await checkSetupRequired()
          setSetupRequired(setup_required)
          if (setup_required) {
            setLoading(false)
            setChecked(true)
            return
          }
        } catch {
          // If we can't check setup, assume it's not required
          setSetupRequired(false)
        }
      }

      // Always verify token with server if we think we're authenticated
      if (isAuthenticated) {
        try {
          const currentUser = await getCurrentUser()
          setUser(currentUser)
        } catch {
          // Token is invalid, log out
          logout()
        }
      }

      setLoading(false)
      setChecked(true)
    }

    verifyAuth()
  }, [isAuthenticated, setupRequired, setUser, setSetupRequired, setLoading, logout])

  // Check consent status after auth is verified
  useEffect(() => {
    if (!checked || !isAuthenticated) return

    refreshTelemetry()
      .then(() => setConsentChecked(true))
      .catch(() => setConsentChecked(true))
  }, [checked, isAuthenticated, refreshTelemetry])

  // Show loading spinner while checking auth
  if (isLoading || !checked || (isAuthenticated && !consentChecked)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-100 dark:bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    )
  }

  // Redirect to setup if needed, otherwise to login if not authenticated
  if (setupRequired) {
    return <Navigate to="/setup" state={{ from: location }} replace />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Redirect to consent page if terms not yet accepted
  if (telemetryStatus && !telemetryStatus.terms_accepted) {
    return <Navigate to="/consent" state={{ from: location }} replace />
  }

  // Check admin requirement
  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  // Check manager requirement (admin also passes)
  if (requireManager && user?.role !== 'admin' && user?.role !== 'manager') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
