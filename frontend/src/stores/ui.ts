import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'system'
export type AccentColor = 'green' | 'pink' | 'blue' | 'purple' | 'orange' | 'red' | 'cyan' | 'yellow'
export type SettingsSection = 'general' | 'knowledge' | 'skills' | 'connections' | 'environment' | 'voice' | 'advanced' | 'danger'
export type WorkSection = 'overview' | 'active' | 'completed' | 'history'
export type ScheduleSection = 'all' | 'enabled' | 'disabled' | 'create'
export type AutomationSection = 'all' | 'functions' | 'scripts' | 'schedules'

// Accent color palettes (Tailwind-style)
export const accentColors: Record<AccentColor, { name: string; palette: Record<string, string> }> = {
  green: {
    name: 'Green',
    palette: {
      50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80',
      500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d', 950: '#052e16',
    },
  },
  pink: {
    name: 'Pink',
    palette: {
      50: '#fdf2f8', 100: '#fce7f3', 200: '#fbcfe8', 300: '#f9a8d4', 400: '#f472b6',
      500: '#ec4899', 600: '#db2777', 700: '#be185d', 800: '#9d174d', 900: '#831843', 950: '#500724',
    },
  },
  blue: {
    name: 'Blue',
    palette: {
      50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
      500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a', 950: '#172554',
    },
  },
  purple: {
    name: 'Purple',
    palette: {
      50: '#faf5ff', 100: '#f3e8ff', 200: '#e9d5ff', 300: '#d8b4fe', 400: '#c084fc',
      500: '#a855f7', 600: '#9333ea', 700: '#7c3aed', 800: '#6b21a8', 900: '#581c87', 950: '#3b0764',
    },
  },
  orange: {
    name: 'Orange',
    palette: {
      50: '#fff7ed', 100: '#ffedd5', 200: '#fed7aa', 300: '#fdba74', 400: '#fb923c',
      500: '#f97316', 600: '#ea580c', 700: '#c2410c', 800: '#9a3412', 900: '#7c2d12', 950: '#431407',
    },
  },
  red: {
    name: 'Red',
    palette: {
      50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5', 400: '#f87171',
      500: '#ef4444', 600: '#dc2626', 700: '#b91c1c', 800: '#991b1b', 900: '#7f1d1d', 950: '#450a0a',
    },
  },
  cyan: {
    name: 'Cyan',
    palette: {
      50: '#ecfeff', 100: '#cffafe', 200: '#a5f3fc', 300: '#67e8f9', 400: '#22d3ee',
      500: '#06b6d4', 600: '#0891b2', 700: '#0e7490', 800: '#155e75', 900: '#164e63', 950: '#083344',
    },
  },
  yellow: {
    name: 'Yellow',
    palette: {
      50: '#fefce8', 100: '#fef9c3', 200: '#fef08a', 300: '#fde047', 400: '#facc15',
      500: '#eab308', 600: '#ca8a04', 700: '#a16207', 800: '#854d0e', 900: '#713f12', 950: '#422006',
    },
  },
}

interface UIState {
  theme: Theme
  accentColor: AccentColor
  sidebarCollapsed: boolean
  mobileMenuOpen: boolean
  settingsOpen: boolean
  botSettingsOpen: boolean
  createBotOpen: boolean
  commandPaletteOpen: boolean
  showThinking: boolean
  showCost: boolean
  settingsSection: SettingsSection
  workSection: WorkSection
  scheduleSection: ScheduleSection
  automationSection: AutomationSection

  // Actions
  setTheme: (theme: Theme) => void
  setAccentColor: (color: AccentColor) => void
  toggleTheme: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void
  setMobileMenuOpen: (open: boolean) => void
  toggleMobileMenu: () => void
  setSettingsOpen: (open: boolean) => void
  setBotSettingsOpen: (open: boolean) => void
  setCreateBotOpen: (open: boolean) => void
  setCommandPaletteOpen: (open: boolean) => void
  setShowThinking: (show: boolean) => void
  setShowCost: (show: boolean) => void
  setSettingsSection: (section: SettingsSection) => void
  setWorkSection: (section: WorkSection) => void
  setScheduleSection: (section: ScheduleSection) => void
  setAutomationSection: (section: AutomationSection) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'system',
      accentColor: 'green',
      sidebarCollapsed: false,
      mobileMenuOpen: false,
      settingsOpen: false,
      botSettingsOpen: false,
      createBotOpen: false,
      commandPaletteOpen: false,
      showThinking: true,
      showCost: true,
      settingsSection: 'general',
      workSection: 'overview',
      scheduleSection: 'all',
      automationSection: 'all',

      setTheme: (theme) => set({ theme }),
      setAccentColor: (accentColor) => set({ accentColor }),
      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'light' ? 'dark' : 'light',
        })),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setMobileMenuOpen: (mobileMenuOpen) => set({ mobileMenuOpen }),
      toggleMobileMenu: () =>
        set((state) => ({ mobileMenuOpen: !state.mobileMenuOpen })),
      setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
      setBotSettingsOpen: (botSettingsOpen) => set({ botSettingsOpen }),
      setCreateBotOpen: (createBotOpen) => set({ createBotOpen }),
      setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
      setShowThinking: (showThinking) => set({ showThinking }),
      setShowCost: (showCost) => set({ showCost }),
      setSettingsSection: (settingsSection) => set({ settingsSection }),
      setWorkSection: (workSection) => set({ workSection }),
      setScheduleSection: (scheduleSection) => set({ scheduleSection }),
      setAutomationSection: (automationSection) => set({ automationSection }),
    }),
    {
      name: 'cachibot-ui',
      partialize: (state) => ({
        theme: state.theme,
        accentColor: state.accentColor,
        sidebarCollapsed: state.sidebarCollapsed,
        showThinking: state.showThinking,
        showCost: state.showCost,
      }),
    }
  )
)
