import { useState } from 'react'
import { Wand2, LayoutTemplate, FileCode2, Upload, Store } from 'lucide-react'
import { useCreationStore, type WizardMethod } from '../../../../stores/creation'
import { MarketplaceBrowser } from '../../../marketplace'
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
    id: 'template',
    name: 'Use Template',
    description: 'Start with a pre-configured template and customize it',
    icon: LayoutTemplate,
    color: '#3b82f6',
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
      <div className="grid grid-cols-2 gap-4">
        {METHODS.map((method) => {
          const Icon = method.icon
          const isSelected = form.method === method.id

          return (
            <button
              key={method.id}
              onClick={() => handleSelect(method.id)}
              className={cn(
                'relative flex flex-col items-start gap-3 rounded-xl border p-5 text-left transition-all',
                isSelected
                  ? 'border-cachi-500 bg-cachi-500/10 ring-1 ring-cachi-500'
                  : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]'
              )}
            >
              {method.badge && (
                <span className="absolute -top-2 right-3 rounded-full bg-cachi-600 px-2 py-0.5 text-[10px] font-medium text-white">
                  {method.badge}
                </span>
              )}
              <div
                className="flex h-12 w-12 items-center justify-center rounded-xl"
                style={{ backgroundColor: method.color + '20' }}
              >
                <Icon className="h-6 w-6" style={{ color: method.color }} />
              </div>
              <div>
                <h3 className="font-semibold text-[var(--color-text-primary)]">{method.name}</h3>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{method.description}</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Marketplace link */}
      <button
        onClick={() => setMarketplaceOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-border-secondary)] py-4 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-cachi-500 hover:text-cachi-400"
      >
        <Store className="h-4 w-4" />
        Browse Bot Marketplace
      </button>

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
