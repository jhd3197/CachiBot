/// <reference types="vite/client" />

declare module '*.css' {
  const content: string
  export default content
}

interface UpdateCheckResult {
  available: boolean
  version?: string
  releaseNotes?: string | { version: string; note: string }[] | null
}

interface UpdateDownloadProgress {
  bytesPerSecond: number
  percent: number
  transferred: number
  total: number
}

interface ElectronAPI {
  platform: string
  isDesktop: boolean
  appVersion: string
  versions: {
    electron: string
    node: string
    chrome: string
  }
  windowMinimize: () => void
  windowMaximize: () => void
  windowClose: () => void
  windowIsMaximized: () => Promise<boolean>
  onMaximizedChange: (callback: (maximized: boolean) => void) => () => void
  // Update management
  checkForUpdate: () => Promise<UpdateCheckResult>
  downloadUpdate: () => Promise<{ success: boolean }>
  installUpdate: () => void
  onUpdateAvailable: (callback: (info: UpdateCheckResult) => void) => () => void
  onUpdateProgress: (callback: (progress: UpdateDownloadProgress) => void) => () => void
  onUpdateError: (callback: (error: { message: string }) => void) => () => void
  onUpdateDownloaded: (callback: (info: { version: string }) => void) => () => void
  // Cache management
  clearCache: () => Promise<{ success: boolean; error?: string }>
  // Settings
  getSetting: (key: string, defaultValue?: unknown) => Promise<unknown>
  setSetting: (key: string, value: unknown) => Promise<{ success: boolean }>
  // Start on boot
  getStartOnBoot: () => Promise<boolean>
  setStartOnBoot: (enabled: boolean) => Promise<{ success: boolean }>
}

interface Window {
  electronAPI?: ElectronAPI
}
