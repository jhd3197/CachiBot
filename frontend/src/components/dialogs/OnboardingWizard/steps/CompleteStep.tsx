import { Check, Star, ExternalLink } from 'lucide-react'
import { useProvidersStore } from '../../../../stores/providers'
import { useModelsStore } from '../../../../stores/models'
import { useUIStore } from '../../../../stores/ui'
import { useOnboardingStore } from '../../../../stores/onboarding'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  claude: 'Anthropic / Claude',
  google: 'Google AI',
  groq: 'Groq',
  grok: 'Grok (xAI)',
  openrouter: 'OpenRouter',
  moonshot: 'Moonshot',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
}

export function CompleteStep() {
  const { providers } = useProvidersStore()
  const { defaultModel } = useModelsStore()
  const { theme, accentColor } = useUIStore()
  const { databaseType, smtpConfigured } = useOnboardingStore()

  const configuredProviders = providers
    .filter((p) => p.configured)
    .map((p) => PROVIDER_LABELS[p.name] || p.name)

  return (
    <div className="flex flex-col items-center py-8 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20">
        <Check className="h-10 w-10 text-green-400" />
      </div>

      <h2 className="text-2xl font-bold text-zinc-900 dark:text-[var(--color-text-primary)]">You're All Set!</h2>
      <p className="mt-2 max-w-md text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
        CachiBot is configured and ready to use. Here's a summary of your setup:
      </p>

      <div className="mt-6 w-full max-w-sm space-y-3 text-left">
        {configuredProviders.length > 0 && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-secondary)]">Providers</p>
            <p className="mt-1 text-sm text-zinc-800 dark:text-[var(--color-text-primary)]">{configuredProviders.join(', ')}</p>
          </div>
        )}

        {defaultModel && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-secondary)]">Default Model</p>
            <p className="mt-1 font-mono text-sm text-zinc-800 dark:text-[var(--color-text-primary)]">{defaultModel}</p>
          </div>
        )}

        <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-secondary)]">Database</p>
          <p className="mt-1 text-sm text-zinc-800 dark:text-[var(--color-text-primary)]">
            {databaseType === 'postgresql' ? 'PostgreSQL' : 'SQLite (default)'}
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-secondary)]">Email (SMTP)</p>
          <p className="mt-1 text-sm text-zinc-800 dark:text-[var(--color-text-primary)]">
            {smtpConfigured ? 'Configured' : 'Not configured (can be set up later)'}
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--color-border-primary)] dark:bg-[var(--card-bg)] p-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-secondary)]">Appearance</p>
          <p className="mt-1 text-sm text-zinc-800 dark:text-[var(--color-text-primary)]">
            {theme.charAt(0).toUpperCase() + theme.slice(1)} theme, {accentColor} accent
          </p>
        </div>
      </div>

      <a
        href="https://github.com/jhd3197/CachiBot"
        target="_blank"
        rel="noopener noreferrer"
        className="mt-6 flex w-full max-w-sm items-center gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 transition-colors hover:bg-amber-500/20"
      >
        <Star className="h-5 w-5 shrink-0 text-amber-400" />
        <div className="flex-1 text-left">
          <p className="text-sm font-medium text-zinc-800 dark:text-[var(--color-text-primary)]">Enjoying CachiBot?</p>
          <p className="text-xs text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Star us on GitHub to show your support!</p>
        </div>
        <ExternalLink className="h-4 w-4 shrink-0 text-[var(--color-text-secondary)]" />
      </a>
    </div>
  )
}
