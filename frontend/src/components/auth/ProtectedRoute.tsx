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
    legacyDbDetected,
    setUser,
    setSetupRequired,
    setLegacyDbDetected,
    setLoading,
    logout,
  } = useAuthStore()
  const { status: telemetryStatus, refresh: refreshTelemetry } = useTelemetryStore()

  const [checked, setChecked] = useState(false)
  const [consentChecked, setConsentChecked] = useState(false)
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    let cancelled = false

    const withTimeout = <T,>(promise: Promise<T>, ms = 10000): Promise<T> =>
      Promise.race([
        promise,
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Request timed out')), ms)
        ),
      ])

    const verifyAuth = async () => {
      // Check if setup is required first
      if (setupRequired === null) {
        try {
          const { setup_required, legacy_db_detected } = await withTimeout(checkSetupRequired())
          if (cancelled) return
          if (legacy_db_detected) {
            setLegacyDbDetected(true)
            setLoading(false)
            setChecked(true)
            return
          }
          setSetupRequired(setup_required)
          if (setup_required) {
            setLoading(false)
            setChecked(true)
            return
          }
        } catch {
          if (cancelled) return
          // If we can't check setup, assume it's not required
          setSetupRequired(false)
        }
      }

      // Always verify token with server if we think we're authenticated
      if (isAuthenticated) {
        try {
          const currentUser = await withTimeout(getCurrentUser())
          if (cancelled) return
          setUser(currentUser)
        } catch {
          if (cancelled) return
          // Token is invalid or timed out, log out
          logout()
        }
      }

      if (!cancelled) {
        setLoading(false)
        setChecked(true)
      }
    }

    verifyAuth()
    return () => { cancelled = true }
  }, [isAuthenticated, setupRequired, setUser, setSetupRequired, setLegacyDbDetected, setLoading, logout])

  // Check consent status after auth is verified (with timeout to avoid hanging)
  useEffect(() => {
    if (!checked || !isAuthenticated) return

    const timeout = setTimeout(() => setConsentChecked(true), 10000)
    refreshTelemetry()
      .then(() => { clearTimeout(timeout); setConsentChecked(true) })
      .catch(() => { clearTimeout(timeout); setConsentChecked(true) })

    return () => clearTimeout(timeout)
  }, [checked, isAuthenticated, refreshTelemetry])

  // Show a hint after 8 seconds if still loading
  useEffect(() => {
    if (checked && (!isAuthenticated || consentChecked)) return
    const timer = setTimeout(() => setSlow(true), 8000)
    return () => clearTimeout(timer)
  }, [checked, isAuthenticated, consentChecked])

  // Show loading spinner while checking auth
  if (isLoading || !checked || (isAuthenticated && !consentChecked)) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-zinc-100 dark:bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
        {slow && (
          <p className="text-sm text-zinc-500">
            Taking longer than expected&hellip; the server may still be starting.
          </p>
        )}
      </div>
    )
  }

  // Redirect to upgrade page if legacy V1 database detected
  if (legacyDbDetected) {
    return <Navigate to="/upgrade" state={{ from: location }} replace />
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
