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
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Choose Your Database</h3>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
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
              : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-600'
          )}
        >
          <span className="absolute right-2 top-2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
            Recommended
          </span>
          <div className={cn(
            'flex h-12 w-12 items-center justify-center rounded-xl',
            databaseType === 'sqlite' ? 'bg-emerald-500/20' : 'bg-zinc-200 dark:bg-zinc-700/50'
          )}>
            <HardDrive className={cn(
              'h-6 w-6',
              databaseType === 'sqlite' ? 'text-emerald-400' : 'text-zinc-400'
            )} />
          </div>
          <div>
            <p className="font-medium text-zinc-900 dark:text-zinc-100">SQLite</p>
            <p className="mt-0.5 text-xs text-zinc-500">Zero config, file-based</p>
          </div>
        </button>

        {/* PostgreSQL card */}
        <button
          onClick={handleSelectPostgres}
          className={cn(
            'relative flex flex-col items-center gap-2 rounded-xl border-2 p-5 text-center transition-all',
            databaseType === 'postgresql'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-600'
          )}
        >
          <div className={cn(
            'flex h-12 w-12 items-center justify-center rounded-xl',
            databaseType === 'postgresql' ? 'bg-blue-500/20' : 'bg-zinc-200 dark:bg-zinc-700/50'
          )}>
            <Database className={cn(
              'h-6 w-6',
              databaseType === 'postgresql' ? 'text-blue-400' : 'text-zinc-400'
            )} />
          </div>
          <div>
            <p className="font-medium text-zinc-900 dark:text-zinc-100">PostgreSQL</p>
            <p className="mt-0.5 text-xs text-zinc-500">Scalable, production-ready</p>
          </div>
        </button>
      </div>

      {/* PostgreSQL connection form */}
      {databaseType === 'postgresql' && (
        <div className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-800/30 p-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Host</label>
              <input
                type="text"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-zinc-700 dark:bg-zinc-800 px-3 text-sm text-zinc-900 dark:text-zinc-100 outline-none transition-colors focus:border-accent-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Port</label>
              <input
                type="text"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-zinc-700 dark:bg-zinc-800 px-3 text-sm text-zinc-900 dark:text-zinc-100 outline-none transition-colors focus:border-accent-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Database</label>
            <input
              type="text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-zinc-700 dark:bg-zinc-800 px-3 text-sm text-zinc-900 dark:text-zinc-100 outline-none transition-colors focus:border-accent-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-zinc-700 dark:bg-zinc-800 px-3 text-sm text-zinc-900 dark:text-zinc-100 outline-none transition-colors focus:border-accent-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-zinc-700 dark:bg-zinc-800 px-3 text-sm text-zinc-900 dark:text-zinc-100 outline-none transition-colors focus:border-accent-500"
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
              className="flex items-center gap-1.5 rounded-lg border border-zinc-300 dark:border-zinc-600 px-4 py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 transition-colors hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
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
