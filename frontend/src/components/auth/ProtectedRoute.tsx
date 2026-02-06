import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { checkSetupRequired, getCurrentUser } from '../../api/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAdmin?: boolean
}

export function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
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

  const [checked, setChecked] = useState(false)

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

      // If we have a token but no user, verify the token
      if (isAuthenticated && !user) {
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
  }, [isAuthenticated, user, setupRequired, setUser, setSetupRequired, setLoading, logout])

  // Show loading spinner while checking auth
  if (isLoading || !checked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
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

  // Check admin requirement
  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
