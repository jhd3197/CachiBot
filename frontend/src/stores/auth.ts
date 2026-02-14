import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthModeResponse, User } from '../types'

interface AuthState {
  // State
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  setupRequired: boolean | null
  authMode: AuthModeResponse | null

  // Actions
  setUser: (user: User | null) => void
  setTokens: (accessToken: string, refreshToken: string) => void
  setAccessToken: (accessToken: string) => void
  setSetupRequired: (required: boolean) => void
  setLoading: (loading: boolean) => void
  setAuthMode: (mode: AuthModeResponse) => void
  login: (user: User, accessToken: string, refreshToken: string) => void
  logout: () => void
  updateUser: (updates: Partial<User>) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,
      setupRequired: null,
      authMode: null,

      // Actions
      setUser: (user) =>
        set({
          user,
          isAuthenticated: user !== null,
        }),

      setTokens: (accessToken, refreshToken) =>
        set({
          accessToken,
          refreshToken,
          isAuthenticated: true,
        }),

      setAccessToken: (accessToken) =>
        set({ accessToken }),

      setSetupRequired: (required) =>
        set({
          setupRequired: required,
          isLoading: false,
        }),

      setLoading: (loading) =>
        set({ isLoading: loading }),

      setAuthMode: (mode) =>
        set({ authMode: mode }),

      login: (user, accessToken, refreshToken) =>
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
          isLoading: false,
          setupRequired: false,
        }),

      logout: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          isLoading: false,
        }),

      updateUser: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),
    }),
    {
      name: 'cachibot-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
