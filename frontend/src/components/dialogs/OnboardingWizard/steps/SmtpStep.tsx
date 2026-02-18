import { useState, useEffect } from 'react'
import { Loader2, CheckCircle2, AlertCircle, Send } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '../../../../lib/utils'
import { useOnboardingStore } from '../../../../stores/onboarding'
import {
  getSmtpStatus,
  testSmtpConnection,
  saveSmtpConfig,
} from '../../../../api/client'

export function SmtpStep() {
  const { smtpConfigured, setSmtpConfigured } = useOnboardingStore()

  const [host, setHost] = useState('')
  const [port, setPort] = useState('587')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fromAddress, setFromAddress] = useState('')
  const [useTls, setUseTls] = useState(true)
  const [testTo, setTestTo] = useState('')

  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [dirty, setDirty] = useState(false)

  // Load existing status on mount
  useEffect(() => {
    getSmtpStatus()
      .then((status) => {
        if (status.configured) {
          setHost(status.host)
          setPort(status.port.toString())
          setFromAddress(status.from_address)
          setUseTls(status.use_tls)
          setSmtpConfigured(true)
        }
      })
      .catch(() => {
        // Ignore — not configured yet
      })
  }, [setSmtpConfigured])

  const markDirty = () => {
    setDirty(true)
    setSmtpConfigured(false)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testSmtpConnection({
        host,
        port: parseInt(port, 10) || 587,
        username: username || undefined,
        password: password || undefined,
        use_tls: useTls,
        from_address: fromAddress || undefined,
        send_test_to: testTo || undefined,
      })
      setTestResult({ success: result.success, message: result.message })
      if (result.success) {
        toast.success(result.message)
      } else {
        toast.error(result.message)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'SMTP test failed'
      setTestResult({ success: false, message })
      toast.error(message)
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveSmtpConfig({
        host,
        port: parseInt(port, 10) || 587,
        username: username || undefined,
        password: password || undefined,
        from_address: fromAddress || undefined,
        use_tls: useTls,
      })
      setSmtpConfigured(true)
      setDirty(false)
      toast.success('SMTP configuration saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save SMTP config')
    } finally {
      setSaving(false)
    }
  }

  const hasFormValues = host.trim().length > 0

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">Email Configuration</h3>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
          Configure SMTP to enable email notifications and alerts.{' '}
          <span className="text-[var(--color-text-secondary)]">This step is optional — you can set it up later.</span>
        </p>
      </div>

      <div className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">SMTP Host</label>
            <input
              type="text"
              value={host}
              onChange={(e) => { setHost(e.target.value); markDirty() }}
              placeholder="smtp.gmail.com"
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Port</label>
            <input
              type="text"
              value={port}
              onChange={(e) => { setPort(e.target.value); markDirty() }}
              placeholder="587"
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); markDirty() }}
              placeholder="user@example.com"
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); markDirty() }}
              placeholder="••••••••"
              className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">From Address</label>
          <input
            type="email"
            value={fromAddress}
            onChange={(e) => { setFromAddress(e.target.value); markDirty() }}
            placeholder="noreply@example.com"
            className="h-9 w-full rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => { setUseTls(!useTls); markDirty() }}
            className={cn(
              'relative h-5 w-9 rounded-full transition-colors',
              useTls ? 'bg-accent-600' : 'bg-zinc-300 dark:bg-zinc-600'
            )}
          >
            <span
              className={cn(
                'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform',
                useTls ? 'left-[18px]' : 'left-0.5'
              )}
            />
          </button>
          <span className="text-sm text-zinc-700 dark:text-[var(--color-text-primary)]">Use TLS</span>
        </div>

        {/* Send test email */}
        <div className="border-t border-zinc-300 dark:border-[var(--color-border-secondary)] pt-3">
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
            Send Test Email To <span className="text-[var(--color-text-tertiary)]">(optional)</span>
          </label>
          <div className="flex gap-2">
            <input
              type="email"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="you@example.com"
              className="h-9 flex-1 rounded-lg border border-zinc-300 bg-white dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] px-3 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-tertiary)] focus:border-accent-500"
            />
          </div>
        </div>

        {/* Test result */}
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

        {/* Dirty warning */}
        {dirty && hasFormValues && (
          <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>Unsaved changes — test and save before continuing.</span>
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleTest}
            disabled={testing || !host}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] px-4 py-2 text-sm font-medium text-zinc-800 dark:text-[var(--color-text-primary)] transition-colors hover:bg-zinc-200 dark:hover:bg-[var(--color-hover-bg)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {testing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Test Connection
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !host}
            className="flex items-center gap-1.5 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </button>
        </div>
      </div>

      {/* Configured indicator */}
      {smtpConfigured && !dirty && (
        <div className="flex items-center gap-2 rounded-lg bg-green-500/10 px-3 py-2 text-sm text-green-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>SMTP configured successfully</span>
        </div>
      )}
    </div>
  )
}
