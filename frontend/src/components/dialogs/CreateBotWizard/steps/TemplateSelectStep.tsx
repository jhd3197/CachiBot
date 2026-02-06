import { useEffect, useState } from 'react'
import { Loader2, Store } from 'lucide-react'
import { useCreationStore } from '../../../../stores/creation'
import { BotCard } from '../../../marketplace/BotCard'
import { MarketplaceBrowser } from '../../../marketplace'
import {
  getMarketplaceTemplates,
  type MarketplaceTemplate,
} from '../../../../api/client'
import type { BotIcon } from '../../../../types'

export function TemplateSelectStep() {
  const { updateForm, nextStep, close, reset } = useCreationStore()
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [marketplaceOpen, setMarketplaceOpen] = useState(false)

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await getMarketplaceTemplates()
      // Show top 6 most popular templates
      const sorted = [...data.templates].sort((a, b) => b.downloads - a.downloads)
      setTemplates(sorted.slice(0, 6))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectTemplate = (template: MarketplaceTemplate) => {
    updateForm({
      name: template.name,
      description: template.description,
      icon: template.icon as BotIcon,
      color: template.color,
      model: template.model,
      systemPrompt: template.system_prompt,
      tools: template.tools,
    })
    nextStep()
  }

  const handleMarketplaceInstalled = () => {
    close()
    setTimeout(reset, 200)
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-center">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={loadTemplates}
          className="mt-2 text-sm text-cachi-400 hover:underline"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        Select a template to customize, or browse the full marketplace.
      </p>

      <div className="grid grid-cols-2 gap-3">
        {templates.map((template) => (
          <BotCard
            key={template.id}
            template={template}
            onClick={() => handleSelectTemplate(template)}
          />
        ))}
      </div>

      {/* More templates link */}
      <button
        onClick={() => setMarketplaceOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-zinc-700 py-3 text-sm text-zinc-400 transition-colors hover:border-cachi-500 hover:text-cachi-400"
      >
        <Store className="h-4 w-4" />
        Browse All Templates
      </button>

      <MarketplaceBrowser
        open={marketplaceOpen}
        onClose={() => setMarketplaceOpen(false)}
        onInstalled={handleMarketplaceInstalled}
      />
    </div>
  )
}
