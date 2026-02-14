import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from './components/layout/MainLayout'
import { AuthCallback } from './components/auth/AuthCallback'
import { LoginPage } from './components/auth/LoginPage'
import { SetupPage } from './components/auth/SetupPage'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { UsersView } from './components/views/UsersView'
import { useUIStore } from './stores/ui'

function App() {
  const { theme } = useUIStore()

  useEffect(() => {
    // Apply theme to document
    const root = document.documentElement
    if (theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  return (
    <Routes>
      {/* Auth routes (public) */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/:settingsTab"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />

      {/* Admin-only routes */}
      <Route
        path="/users"
        element={
          <ProtectedRoute requireAdmin>
            <UsersView />
          </ProtectedRoute>
        }
      />

      {/* Bot view routes: /:botId/view */}
      <Route
        path="/:botId/chats"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/chats/:chatId"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/tasks"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/tasks/:taskId"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/work"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/work/:workId"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/schedules"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/schedules/:scheduleId"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/rooms"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/rooms/:roomId"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/tools"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/:botId/settings"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />

      {/* Default and fallback */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
