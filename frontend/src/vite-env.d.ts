/// <reference types="vite/client" />

declare module '*.css' {
  const content: string
  export default content
}

interface ElectronAPI {
  platform: string
  isDesktop: boolean
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
}

interface Window {
  electronAPI?: ElectronAPI
}
