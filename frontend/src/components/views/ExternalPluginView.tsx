import { useEffect, useRef, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import { useUIStore } from '../../stores/ui'

interface ExternalPluginViewProps {
  pluginName: string
}

/**
 * Iframe wrapper for view-type external plugins.
 *
 * Loads the plugin's static HTML via GET /api/plugins/{name}/view
 * in a sandboxed iframe, with a postMessage bridge for basic
 * parent-app communication (navigate, toast, theme).
 */
export function ExternalPluginView({ pluginName }: ExternalPluginViewProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const { theme } = useUIStore()

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      if (!iframeRef.current || event.source !== iframeRef.current.contentWindow) return

      const { type, payload } = event.data ?? {}
      switch (type) {
        case 'navigate':
          // Allow plugin to request navigation
          if (typeof payload?.path === 'string') {
            window.location.hash = payload.path
          }
          break
        case 'toast':
          // Allow plugin to show a toast notification
          if (typeof payload?.message === 'string') {
            import('sonner').then(({ toast }) => {
              const level = payload.level ?? 'info'
              if (level === 'error') toast.error(payload.message)
              else if (level === 'success') toast.success(payload.message)
              else toast(payload.message)
            })
          }
          break
        case 'getTheme':
          // Send current theme to iframe
          iframeRef.current.contentWindow?.postMessage(
            { type: 'theme', payload: { theme } },
            '*'
          )
          break
      }
    },
    [theme]
  )

  useEffect(() => {
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [handleMessage])

  // Push theme changes to iframe
  useEffect(() => {
    iframeRef.current?.contentWindow?.postMessage(
      { type: 'theme', payload: { theme } },
      '*'
    )
  }, [theme])

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden">
      <div className="relative flex-1">
        <iframe
          ref={iframeRef}
          src={`/api/plugins/${pluginName}/view`}
          title={pluginName}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          className="h-full w-full border-0"
          style={{ background: 'transparent' }}
        />
      </div>
    </div>
  )
}
