import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../../stores/auth'
import { useTelemetryStore } from '../../stores/telemetry'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { useProvidersStore } from '../../stores/providers'
import { checkSetupRequired, getCurrentUser, tryRefreshToken } from '../../api/auth'
import { checkHealth, getConfig } from '../../api/client'
import type { Config } from '../../types'

interface AppLoaderProps {
  children: React.ReactNode
}

async function waitForBackend(
  onStatus: (msg: string) => void,
  maxAttempts = 30,
  interval = 1000,
): Promise<void> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      await checkHealth()
      return
    } catch {
      onStatus(i === 0 ? 'Waiting for server...' : `Waiting for server... (${i + 1}s)`)
      await new Promise((r) => setTimeout(r, interval))
    }
  }
  // Give up waiting — proceed anyway and let individual calls handle errors
}

export function AppLoader({ children }: AppLoaderProps) {
  const [ready, setReady] = useState(false)
  const [visible, setVisible] = useState(true)
  const [status, setStatus] = useState('Initializing...')
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    const run = async () => {
      const auth = useAuthStore.getState()

      // Phase 0: Wait for backend to be ready
      await waitForBackend(setStatus)

      // Phase 1: Check setup status
      setStatus('Checking system status...')
      try {
        const { setup_required, legacy_db_detected } = await checkSetupRequired()
        if (legacy_db_detected) {
          auth.setLegacyDbDetected(true)
          auth.setLoading(false)
          finish()
          return
        }
        auth.setSetupRequired(setup_required)
        if (setup_required) {
          auth.setLoading(false)
          finish()
          return
        }
      } catch {
        auth.setSetupRequired(false)
      }

      // Phase 2: Verify auth
      if (auth.isAuthenticated) {
        setStatus('Verifying session...')
        try {
          const user = await getCurrentUser()
          auth.setUser(user)
        } catch {
          // Token might be expired, try refresh
          const newToken = await tryRefreshToken()
          if (newToken) {
            try {
              const user = await getCurrentUser()
              auth.setUser(user)
            } catch {
              auth.logout()
            }
          } else {
            auth.logout()
          }
        }
      }

      auth.setLoading(false)

      // Phase 3: Load app data in parallel (only if authenticated)
      if (useAuthStore.getState().isAuthenticated) {
        setStatus('Loading configuration...')

        const results = await Promise.allSettled([
          useTelemetryStore.getState().refresh(),
          loadConfig(),
          useModelsStore.getState().refresh(),
          useProvidersStore.getState().refresh(),
        ])

        // Log any failures but don't block
        results.forEach((r, i) => {
          if (r.status === 'rejected') {
            const labels = ['telemetry', 'config', 'models', 'providers']
            console.warn(`[AppLoader] Failed to load ${labels[i]}:`, r.reason)
          }
        })
      }

      setStatus('Almost ready...')
      finish()
    }

    const loadConfig = async () => {
      const configData = await getConfig()
      const config: Config = {
        agent: {
          model: configData.agent.model,
          maxIterations: configData.agent.max_iterations,
          approveActions: configData.agent.approve_actions,
          temperature: configData.agent.temperature,
        },
        sandbox: {
          allowedImports: configData.sandbox.allowed_imports,
          timeoutSeconds: configData.sandbox.timeout_seconds,
          maxOutputLength: configData.sandbox.max_output_length,
        },
        display: {
          showThinking: configData.display.show_thinking,
          showCost: configData.display.show_cost,
          style: configData.display.style as 'detailed' | 'compact',
        },
        workspacePath: configData.workspace_path,
        timezone: configData.timezone || 'UTC',
      }
      useConfigStore.getState().setConfig(config)
    }

    const finish = () => {
      setReady(true)
      // Fade out after a brief moment
      setTimeout(() => setVisible(false), 400)
    }

    run()
  }, [])

  if (!visible) return <>{children}</>

  return (
    <>
      <div className={`app-loader ${ready ? 'app-loader--fade' : ''}`}>
        <div className="app-loader__content">
          <div className="app-loader__logo">
            Cachi<span className="app-loader__accent">Bot</span>
          </div>

          <div className="app-loader__rings">
            <div className="app-loader__ring app-loader__ring--1" />
            <div className="app-loader__ring app-loader__ring--2" />
            <div className="app-loader__ring app-loader__ring--3" />
            <div className="app-loader__core-dot" />
          </div>
        </div>

        <div className="app-loader__bottom">
          <div className="app-loader__track">
            <div className="app-loader__bar" />
          </div>
          <div className="app-loader__status-container">
            <p className="app-loader__status">{status}</p>
          </div>
        </div>
      </div>
      {ready && children}
    </>
  )
}
