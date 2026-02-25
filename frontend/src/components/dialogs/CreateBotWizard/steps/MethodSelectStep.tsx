import { useState, useEffect } from 'react'
import { Wand2, FileCode2, Upload, Store } from 'lucide-react'
import { useCreationStore, type WizardMethod } from '../../../../stores/creation'
import { MarketplaceBrowser } from '../../../marketplace'
import { getMarketplaceTemplates, type MarketplaceTemplate } from '../../../../api/client'
import { BotIconRenderer } from '../../../common/BotIconRenderer'
import { cn } from '../../../../lib/utils'

const METHODS: {
  id: WizardMethod
  name: string
  description: string
  icon: typeof Wand2
  color: string
  badge?: string
}[] = [
  {
    id: 'ai-assisted',
    name: 'AI-Assisted',
    description: 'Describe what you want and let AI generate the perfect system prompt',
    icon: Wand2,
    color: '#8b5cf6',
    badge: 'Recommended',
  },
  {
    id: 'blank',
    name: 'Start Blank',
    description: 'Build everything from scratch with full control',
    icon: FileCode2,
    color: '#22c55e',
  },
  {
    id: 'import',
    name: 'Import',
    description: 'Import a bot configuration from a JSON file',
    icon: Upload,
    color: '#f59e0b',
  },
]

export function MethodSelectStep() {
  const { form, setMethod, nextStep, close, reset } = useCreationStore()
  const [marketplaceOpen, setMarketplaceOpen] = useState(false)
  const [popularTemplates, setPopularTemplates] = useState<MarketplaceTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMarketplaceTemplates()
      .then((res) => {
        if (cancelled) return
        const sorted = [...res.templates].sort((a, b) => (b.downloads ?? 0) - (a.downloads ?? 0))
        setPopularTemplates(sorted.slice(0, 3))
      })
      .catch(() => {
        // Silently fail — marketplace preview is non-critical
      })
      .finally(() => {
        if (!cancelled) setTemplatesLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const handleSelect = (method: WizardMethod) => {
    setMethod(method)
    // Auto-advance after selection
    setTimeout(nextStep, 150)
  }

  const handleMarketplaceInstalled = () => {
    close()
    setTimeout(reset, 200)
  }

  const handleRoomInstalled = () => {
    close()
    setTimeout(reset, 200)
  }

  return (
    <div className="space-y-4">
      {/* Method cards — 1 full-width + 2 side-by-side, all horizontal layout */}
      <div className="space-y-3">
        {(() => {
          const primary = METHODS[0]
          const Icon = primary.icon
          const isSelected = form.method === primary.id
          return (
            <button
              onClick={() => handleSelect(primary.id)}
              className={cn(
                'relative flex w-full items-center gap-4 rounded-xl border p-5 text-left transition-all',
                isSelected
                  ? 'border-cachi-500 bg-cachi-500/10 ring-1 ring-cachi-500'
                  : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]'
              )}
            >
              {primary.badge && (
                <span className="absolute -top-2 right-3 rounded-full bg-cachi-600 px-2 py-0.5 text-[10px] font-medium text-white">
                  {primary.badge}
                </span>
              )}
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
                style={{ backgroundColor: primary.color + '20' }}
              >
                <Icon className="h-6 w-6" style={{ color: primary.color }} />
              </div>
              <div>
                <h3 className="font-semibold text-[var(--color-text-primary)]">{primary.name}</h3>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{primary.description}</p>
              </div>
            </button>
          )
        })()}

        <div className="grid grid-cols-2 gap-3">
          {METHODS.slice(1).map((method) => {
            const Icon = method.icon
            const isSelected = form.method === method.id

            return (
              <button
                key={method.id}
                onClick={() => handleSelect(method.id)}
                className={cn(
                  'relative flex items-center gap-3 rounded-xl border p-4 text-left transition-all',
                  isSelected
                    ? 'border-cachi-500 bg-cachi-500/10 ring-1 ring-cachi-500'
                    : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]'
                )}
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                  style={{ backgroundColor: method.color + '20' }}
                >
                  <Icon className="h-5 w-5" style={{ color: method.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{method.name}</h3>
                  <p className="text-xs text-[var(--color-text-secondary)]">{method.description}</p>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Marketplace Mini Preview */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-medium text-[var(--color-text-tertiary)]">
            Popular from Marketplace
          </h4>
          <button
            onClick={() => setMarketplaceOpen(true)}
            className="text-xs text-cachi-400 transition-colors hover:text-cachi-300"
          >
            See all
          </button>
        </div>

        {templatesLoading ? (
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="flex flex-col items-center gap-2 rounded-lg border border-[var(--color-border-primary)] bg-[var(--card-bg)] px-3 py-3"
              >
                <div className="h-8 w-8 animate-pulse rounded-lg bg-[var(--color-bg-tertiary)]" />
                <div className="h-3 w-3/4 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
              </div>
            ))}
          </div>
        ) : popularTemplates.length > 0 ? (
          <div className="grid grid-cols-3 gap-2">
            {popularTemplates.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => setMarketplaceOpen(true)}
                className="flex flex-col items-center gap-2 rounded-lg border border-[var(--color-border-primary)] bg-[var(--card-bg)] px-3 py-3 text-center transition-all hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]"
              >
                <div
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  style={{ backgroundColor: (tpl.color || '#3b82f6') + '20' }}
                >
                  <BotIconRenderer icon={tpl.icon} size={16} color={tpl.color} />
                </div>
                <p className="w-full truncate text-xs font-medium text-[var(--color-text-primary)]">
                  {tpl.name}
                </p>
              </button>
            ))}
          </div>
        ) : (
          <button
            onClick={() => setMarketplaceOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-border-secondary)] py-3 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-cachi-500 hover:text-cachi-400"
          >
            <Store className="h-4 w-4" />
            Browse Bot Marketplace
          </button>
        )}
      </div>

      {/* Marketplace dialog */}
      <MarketplaceBrowser
        open={marketplaceOpen}
        onClose={() => setMarketplaceOpen(false)}
        onInstalled={handleMarketplaceInstalled}
        onRoomInstalled={handleRoomInstalled}
      />
    </div>
  )
}
