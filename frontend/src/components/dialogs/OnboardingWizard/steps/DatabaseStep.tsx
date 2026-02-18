import { useState, useEffect } from 'react'
import { HardDrive, Database, Loader2, CheckCircle2, AlertCircle, Info } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '../../../../lib/utils'
import { useOnboardingStore } from '../../../../stores/onboarding'
import {
  getDatabaseStatus,
  testDatabaseConnection,
  saveDatabaseConfig,
} from '../../../../api/client'

export function DatabaseStep() {
  const {
    databaseType,
    databaseConfigured,
    setDatabaseType,
    setDatabaseConfigured,
  } = useOnboardingStore()

  const [host, setHost] = useState('localhost')
  const [port, setPort] = useState('5432')
  const [database, setDatabase] = useState('cachibot')
  const [username, setUsername] = useState('postgres')
  const [password, setPassword] = useState('')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [restartRequired, setRestartRequired] = useState(false)

  // Load existing status on mount
  useEffect(() => {
    getDatabaseStatus()
      .then((status) => {
        if (status.db_type === 'postgresql') {
          setDatabaseType('postgresql')
          setDatabaseConfigured(status.url_configured)
        } else {
          setDatabaseType('sqlite')
          setDatabaseConfigured(true)
        }
      })
      .catch(() => {
        // Default to sqlite if status check fails
      })
  }, [setDatabaseType, setDatabaseConfigured])

  const handleSelectSqlite = async () => {
    setDatabaseType('sqlite')
    setTestResult(null)
    setRestartRequired(false)

    try {
      await saveDatabaseConfig({ db_type: 'sqlite' })
      setDatabaseConfigured(true)
    } catch {
      toast.error('Failed to save database configuration')
    }
  }

  const handleSelectPostgres = () => {
    setDatabaseType('postgresql')
    setDatabaseConfigured(false)
    setTestResult(null)
    setRestartRequired(false)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testDatabaseConnection({
        host,
        port: parseInt(port, 10) || 5432,
        database,
        username,
        password,
      })
      setTestResult({ success: result.success, message: result.message })
      if (result.success) {
        toast.success(result.db_version ? `Connected — ${result.db_version}` : 'Connection successful')
      } else {
        toast.error(result.message)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection test failed'
      setTestResult({ success: false, message })
      toast.error(message)
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await saveDatabaseConfig({
        db_type: 'postgresql',
        host,
        port: parseInt(port, 10) || 5432,
        database,
        username,
        password,
      })
      setDatabaseConfigured(true)
      setRestartRequired(result.restart_required)
      toast.success('PostgreSQL configuration saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">Choose Your Database</h3>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
          Select where CachiBot stores its data. You can change this later in settings.
        </p>
      </div>

      {/* Selection cards */}
      <div className="grid grid-cols-2 gap-3">
        {/* SQLite card */}
        <button
          onClick={handleSelectSqlite}
          className={cn(
            'relative flex flex-col items-center gap-2 rounded-xl border-2 p-5 text-center transition-all',
            databaseType === 'sqlite'
              ? 'border-emerald-500 bg-emerald-500/10'
              : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-[var(--color-border-secondary)] dark:bg-[var(--card-bg)] dark:hover:border-[var(--color-border-secondary)]'
          )}
        >
          <span className="absolute right-2 top-2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
            Recommended
          </span>
          <div className={cn(
            'flex h-12 w-12 items-center justify-center rounded-xl',
            databaseType === 'sqlite' ? 'bg-emerald-500/20' : 'bg-zinc-200 dark:bg-[var(--color-bg-inset)]'
          )}>
            <HardDrive className={cn(
              'h-6 w-6',
              databaseType === 'sqlite' ? 'text-emerald-400' : 'text-[var(--color-text-secondary)]'
            )} />
          </div>
          <div>
            <p className="font-medium text-zinc-900 dark:text-[var(--color-text-primary)]">SQLite</p>
            <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">Zero config, file-based</p>
          </div>
        </button>

        {/* PostgreSQL card */}
        <button
          onClick={handleSelectPostgres}
          className={cn(
            'relative flex flex-col items-center gap-2 rounded-xl border-2 p-5 text-center transition-all',
            databaseType === 'postgresql'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-[var(--color-border-secondary)] dark:bg-[var(--card-bg)] dark:hover:border-[var(--color-border-secondary)]'
          )}
        >
          <div className={cn(
            'flex h-12 w-12 items-center justify-center rounded-xl',
            databaseType === 'postgresql' ? 'bg-blue-500/20' : 'bg-zinc-200 dark:bg-[var(--color-bg-inset)]'
          )}>
            <Database className={cn(
              'h-6 w-6',
              databaseType === 'postgresql' ? 'text-blue-400' : 'text-[var(--color-text-secondary)]'
            )} />
          </div>
          <div>
            <p className="font-medium text-zinc-900 dark:text-[var(--color-text-primary)]">PostgreSQL</p>
            <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">Scalable, production-ready</p>
          </div>
        </button>
      </div>

      {/* PostgreSQL connection form */}
      {databaseType === 'postgresql' && (
        <div className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Host</label>
              <input
                type="text"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors focus:border-accent-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Port</label>
              <input
                type="text"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors focus:border-accent-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Database</label>
            <input
              type="text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors focus:border-accent-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors focus:border-accent-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors focus:border-accent-500"
              />
            </div>
          </div>

          {/* Test result indicator */}
          {testResult && (
            <div className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm',
              testResult.success
                ? 'bg-green-500/10 text-green-400'
                : 'bg-red-500/10 text-red-400'
            )}>
              {testResult.success ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 shrink-0" />
              )}
              <span className="truncate">{testResult.message}</span>
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleTest}
              disabled={testing || !host}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] px-4 py-2 text-sm font-medium text-zinc-800 dark:text-[var(--color-text-primary)] transition-colors hover:bg-zinc-200 dark:hover:bg-[var(--color-hover-bg)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {testing && <Loader2 className="h-4 w-4 animate-spin" />}
              Test Connection
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !testResult?.success}
              className="flex items-center gap-1.5 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save &amp; Use PostgreSQL
            </button>
          </div>
        </div>
      )}

      {/* Restart notice */}
      {restartRequired && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-300">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Database configuration saved. A server restart is required for the change to take effect.
          </span>
        </div>
      )}

      {/* SQLite confirmation */}
      {databaseType === 'sqlite' && databaseConfigured && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>SQLite selected — data stored locally at <code className="font-mono text-xs">~/.cachibot/cachibot.db</code></span>
        </div>
      )}
    </div>
  )
}
