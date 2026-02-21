import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'system'
export type PresetColor = 'green' | 'pink' | 'blue' | 'purple' | 'orange' | 'red' | 'cyan' | 'yellow' | 'teal' | 'indigo' | 'rose' | 'amber' | 'lime'
export type AccentColor = PresetColor | 'custom'
export type SettingsSection = 'general' | 'knowledge' | 'skills' | 'connections' | 'environment' | 'developer' | 'danger'
export type WorkSection = 'overview' | 'active' | 'completed' | 'history'
export type ScheduleSection = 'all' | 'enabled' | 'disabled' | 'create'
export type AutomationSection = 'all' | 'functions' | 'scripts' | 'schedules'

// Accent color palettes (Tailwind-style)
export const accentColors: Record<PresetColor, { name: string; palette: Record<string, string> }> = {
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
  teal: {
    name: 'Teal',
    palette: {
      50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf',
      500: '#14b8a6', 600: '#0d9488', 700: '#0f766e', 800: '#115e59', 900: '#134e4a', 950: '#042f2e',
    },
  },
  indigo: {
    name: 'Indigo',
    palette: {
      50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc', 400: '#818cf8',
      500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 800: '#3730a3', 900: '#312e81', 950: '#1e1b4b',
    },
  },
  rose: {
    name: 'Rose',
    palette: {
      50: '#fff1f2', 100: '#ffe4e6', 200: '#fecdd3', 300: '#fda4af', 400: '#fb7185',
      500: '#f43f5e', 600: '#e11d48', 700: '#be123c', 800: '#9f1239', 900: '#881337', 950: '#4c0519',
    },
  },
  amber: {
    name: 'Amber',
    palette: {
      50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d', 400: '#fbbf24',
      500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e', 900: '#78350f', 950: '#451a03',
    },
  },
  lime: {
    name: 'Lime',
    palette: {
      50: '#f7fee7', 100: '#ecfccb', 200: '#d9f99d', 300: '#bef264', 400: '#a3e635',
      500: '#84cc16', 600: '#65a30d', 700: '#4d7c0f', 800: '#3f6212', 900: '#365314', 950: '#1a2e05',
    },
  },
}

// Generate a full palette from a single hex color
function hexToHsl(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max - min)
  let h = 0
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  return [h * 360, s * 100, l * 100]
}

function hslToHex(h: number, s: number, l: number): string {
  s /= 100; l /= 100
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * Math.max(0, Math.min(1, color))).toString(16).padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

export function generatePalette(hex: string): Record<string, string> {
  const [h, s] = hexToHsl(hex)
  const shades: [string, number, number][] = [
    ['50', Math.max(s - 30, 5), 97],
    ['100', Math.max(s - 20, 10), 93],
    ['200', Math.max(s - 10, 15), 86],
    ['300', s, 76],
    ['400', s, 64],
    ['500', s, 50],
    ['600', s, 42],
    ['700', Math.min(s + 5, 100), 34],
    ['800', Math.min(s + 10, 100), 26],
    ['900', Math.min(s + 10, 100), 20],
    ['950', Math.min(s + 15, 100), 12],
  ]
  const palette: Record<string, string> = {}
  for (const [key, sat, light] of shades) {
    palette[key] = hslToHex(h, sat, light)
  }
  return palette
}

interface UIState {
  theme: Theme
  accentColor: AccentColor
  customHex: string
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
  setCustomHex: (hex: string) => void
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
      customHex: '#8b5cf6',
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
      setCustomHex: (customHex) => set({ customHex, accentColor: 'custom' }),
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
        customHex: state.customHex,
        sidebarCollapsed: state.sidebarCollapsed,
        showThinking: state.showThinking,
        showCost: state.showCost,
      }),
    }
  )
)
