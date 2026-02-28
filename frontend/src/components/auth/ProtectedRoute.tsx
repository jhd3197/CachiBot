import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useTelemetryStore } from '../../stores/telemetry'

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
  } = useAuthStore()
  const { status: telemetryStatus, refresh: refreshTelemetry } = useTelemetryStore()

  // Consent check — telemetry may already be loaded by AppLoader
  const [consentChecked, setConsentChecked] = useState(telemetryStatus !== null)

  useEffect(() => {
    if (consentChecked || !isAuthenticated) return

    // If telemetry was already loaded by AppLoader, skip
    if (useTelemetryStore.getState().status !== null) {
      setConsentChecked(true)
      return
    }

    const timeout = setTimeout(() => setConsentChecked(true), 10000)
    refreshTelemetry()
      .then(() => { clearTimeout(timeout); setConsentChecked(true) })
      .catch(() => { clearTimeout(timeout); setConsentChecked(true) })

    return () => clearTimeout(timeout)
  }, [consentChecked, isAuthenticated, refreshTelemetry])

  // Fallback spinner — should rarely appear since AppLoader handles init
  if (isLoading || (isAuthenticated && !consentChecked)) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-zinc-100 dark:bg-[var(--color-bg-app)]">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
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

  // Redirect to consent page if terms not yet accepted or version outdated
  const needsConsent = telemetryStatus && (
    !telemetryStatus.terms_accepted ||
    (telemetryStatus.latest_terms_version &&
     telemetryStatus.terms_version !== telemetryStatus.latest_terms_version)
  )
  if (needsConsent) {
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
