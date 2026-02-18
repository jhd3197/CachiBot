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
    <header className="header">
      <div className="header__left">
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

      <div className="header__right">
        {/* Connection status */}
        <div
          className={cn(
            'header__status',
            isConnected ? 'header__status--connected' : 'header__status--disconnected'
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
          <div className="header__model">
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
          <div className="header__user-menu">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-1.5"
            >
              <div className="header__user-avatar">
                {user.role === 'admin' ? (
                  <Shield className="h-3.5 w-3.5 text-purple-400" />
                ) : (
                  <User className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
                )}
              </div>
              <span className="hidden text-sm sm:inline">{user.username}</span>
              <ChevronDown className="h-4 w-4 text-[var(--color-text-secondary)]" />
            </Button>

            {userMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setUserMenuOpen(false)}
                />
                <div className="header__user-dropdown">
                  <div className="header__user-dropdown-header">
                    <div className="name">{user.username}</div>
                    <div className="email">{user.email}</div>
                    <div className="role">{user.role}</div>
                  </div>
                  {user.role === 'admin' && (
                    <button
                      onClick={() => {
                        setUserMenuOpen(false)
                        navigate('/users')
                      }}
                      className="header__user-dropdown-item"
                    >
                      <Users className="h-4 w-4 text-[var(--color-text-secondary)]" />
                      Manage Users
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      handleLogout()
                    }}
                    className="header__user-dropdown-item header__user-dropdown-item--danger"
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
