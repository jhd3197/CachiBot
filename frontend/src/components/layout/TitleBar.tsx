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
    <div className="title-bar flex h-8 shrink-0 select-none items-center bg-zinc-950">
      {/* Draggable region — fills available space */}
      <div className="title-bar-drag flex flex-1 items-center gap-2 px-3">
        <div className="flex h-4 w-4 items-center justify-center rounded bg-accent-600">
          <span className="text-[9px] font-bold leading-none text-white">C</span>
        </div>
        <span className="text-[11px] font-medium text-zinc-500">CachiBot</span>
      </div>

      {/* Window controls — not draggable */}
      <div className="flex h-full">
        <button
          onClick={() => api!.windowMinimize()}
          className="title-bar-btn flex h-full w-[46px] items-center justify-center text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
          aria-label="Minimize"
        >
          <Minus className="h-4 w-4" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => api!.windowMaximize()}
          className="title-bar-btn flex h-full w-[46px] items-center justify-center text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
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
          className="title-bar-btn flex h-full w-[46px] items-center justify-center text-zinc-400 transition-colors hover:bg-red-600 hover:text-white"
          aria-label="Close"
        >
          <X className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  )
}
