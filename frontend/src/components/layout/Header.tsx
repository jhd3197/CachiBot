import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Moon, Sun, Settings, Menu, Wifi, WifiOff, LogOut, Users, User, Shield, ChevronDown } from 'lucide-react'
import { Button } from '../common/Button'
import { useUIStore } from '../../stores/ui'
import { useModelsStore } from '../../stores/models'
import { useAuthStore } from '../../stores/auth'
import { cn } from '../../lib/utils'

interface HeaderProps {
  isConnected: boolean
}

export function Header({ isConnected }: HeaderProps) {
  const navigate = useNavigate()
  const { theme, toggleTheme, toggleMobileMenu, setSettingsOpen } = useUIStore()
  const { defaultModel, groups } = useModelsStore()
  const { user, logout } = useAuthStore()
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Find the model info from groups
  const allModels = Object.values(groups).flat()
  const modelInfo = allModels.find((m) => m.id === defaultModel)

  return (
    <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleMobileMenu}
          className="lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cachi-600">
            <span className="text-lg font-bold text-white">C</span>
          </div>
          <span className="text-lg font-semibold">CachiBot</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Connection status */}
        <div
          className={cn(
            'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
            isConnected
              ? 'bg-cachi-100 text-cachi-700 dark:bg-cachi-900/30 dark:text-cachi-400'
              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          )}
        >
          {isConnected ? (
            <>
              <Wifi className="h-3 w-3" />
              Connected
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3" />
              Disconnected
            </>
          )}
        </div>

        {/* Model indicator */}
        {defaultModel && (
          <div className="hidden items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 sm:flex font-mono">
            {modelInfo?.id || defaultModel}
          </div>
        )}

        {/* Theme toggle */}
        <Button variant="ghost" size="sm" onClick={toggleTheme}>
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        {/* Settings */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSettingsOpen(true)}
        >
          <Settings className="h-5 w-5" />
        </Button>

        {/* User menu */}
        {user && (
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-1.5"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-700">
                {user.role === 'admin' ? (
                  <Shield className="h-3.5 w-3.5 text-purple-400" />
                ) : (
                  <User className="h-3.5 w-3.5 text-zinc-400" />
                )}
              </div>
              <span className="hidden text-sm sm:inline">{user.username}</span>
              <ChevronDown className="h-4 w-4 text-zinc-400" />
            </Button>

            {userMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setUserMenuOpen(false)}
                />
                <div className="absolute right-0 top-full mt-1 w-48 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg py-1 z-20">
                  <div className="px-3 py-2 border-b border-zinc-700">
                    <div className="text-sm font-medium text-white">{user.username}</div>
                    <div className="text-xs text-zinc-400">{user.email}</div>
                    <div className="text-xs text-zinc-500 mt-0.5 capitalize">{user.role}</div>
                  </div>
                  {user.role === 'admin' && (
                    <button
                      onClick={() => {
                        setUserMenuOpen(false)
                        navigate('/users')
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-zinc-700 transition-colors"
                    >
                      <Users className="h-4 w-4 text-zinc-400" />
                      Manage Users
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      handleLogout()
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left text-red-400 hover:bg-zinc-700 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
