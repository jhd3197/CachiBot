import { useState, useEffect } from 'react'
import { Minus, Square, X, Copy } from 'lucide-react'

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false)
  const api = window.electronAPI

  const isDesktop = !!api?.isDesktop
  const isMac = api?.platform === 'darwin'

  useEffect(() => {
    if (!isDesktop || isMac) return

    // Get initial maximized state
    api!.windowIsMaximized().then(setIsMaximized)

    // Listen for maximize/unmaximize events
    const cleanup = api!.onMaximizedChange(setIsMaximized)
    return cleanup
  }, [api, isDesktop, isMac])

  // Not running in Electron, or macOS uses native traffic lights
  if (!isDesktop || isMac) return null

  return (
    <div className="title-bar">
      {/* Draggable region — fills available space */}
      <div className="title-bar__brand title-bar-drag">
        <img src="/icon.png" alt="" className="title-bar__brand-icon" />
        <span className="title-bar__brand-text">CachiBot</span>
      </div>

      {/* Window controls — not draggable */}
      <div className="title-bar__controls">
        <button
          onClick={() => api!.windowMinimize()}
          className="title-bar__btn title-bar-btn"
          aria-label="Minimize"
        >
          <Minus className="h-4 w-4" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => api!.windowMaximize()}
          className="title-bar__btn title-bar-btn"
          aria-label={isMaximized ? 'Restore' : 'Maximize'}
        >
          {isMaximized ? (
            <Copy className="h-3.5 w-3.5 rotate-180" strokeWidth={1.5} />
          ) : (
            <Square className="h-3 w-3" strokeWidth={1.5} />
          )}
        </button>
        <button
          onClick={() => api!.windowClose()}
          className="title-bar__btn title-bar__btn--close title-bar-btn"
          aria-label="Close"
        >
          <X className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  )
}
