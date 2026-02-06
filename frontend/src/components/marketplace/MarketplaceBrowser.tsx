import { useState, useEffect } from 'react'
import { Search, Store, Loader2, X } from 'lucide-react'
import {
  Dialog,
  DialogHeader,
  DialogContent,
} from '../common/Dialog'
import { BotCard } from './BotCard'
import { BotDetailDialog } from './BotDetailDialog'
import {
  getMarketplaceTemplates,
  getMarketplaceCategories,
  type MarketplaceTemplate,
  type MarketplaceCategory,
} from '../../api/client'
import { cn } from '../../lib/utils'

interface MarketplaceBrowserProps {
  open: boolean
  onClose: () => void
  onInstalled?: (botId: string) => void
}

export function MarketplaceBrowser({ open, onClose, onInstalled }: MarketplaceBrowserProps) {
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([])
  const [categories, setCategories] = useState<MarketplaceCategory[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTemplate, setSelectedTemplate] = useState<MarketplaceTemplate | null>(null)

  // Fetch categories on mount
  useEffect(() => {
    if (open) {
      loadCategories()
      loadTemplates()
    }
  }, [open])

  // Reload templates when filter changes
  useEffect(() => {
    if (open) {
      loadTemplates()
    }
  }, [selectedCategory, searchQuery])

  const loadCategories = async () => {
    try {
      const data = await getMarketplaceCategories()
      setCategories(data)
    } catch (err) {
      console.error('Failed to load categories:', err)
    }
  }

  const loadTemplates = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await getMarketplaceTemplates(
        selectedCategory || undefined,
        searchQuery || undefined
      )
      setTemplates(data.templates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates')
    } finally {
      setLoading(false)
    }
  }

  const handleInstalled = (botId: string) => {
    setSelectedTemplate(null)
    onInstalled?.(botId)
    onClose()
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} size="xl">
        <DialogHeader
          title="Bot Marketplace"
          subtitle="Discover and install bot templates"
          icon={<Store className="h-5 w-5 text-cachi-500" />}
          onClose={onClose}
        />

        <DialogContent className="p-0">
          <div className="flex h-[500px]">
            {/* Sidebar */}
            <div className="w-56 shrink-0 border-r border-zinc-800 p-4">
              <nav className="space-y-1">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={cn(
                    'w-full rounded-lg px-3 py-2 text-left text-sm transition-colors',
                    selectedCategory === null
                      ? 'bg-cachi-600/20 text-cachi-400'
                      : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                  )}
                >
                  All Templates
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={cn(
                      'w-full rounded-lg px-3 py-2 text-left text-sm transition-colors',
                      selectedCategory === cat.id
                        ? 'bg-cachi-600/20 text-cachi-400'
                        : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                    )}
                  >
                    <span>{cat.name}</span>
                    <span className="ml-2 text-xs text-zinc-600">({cat.count})</span>
                  </button>
                ))}
              </nav>
            </div>

            {/* Main content */}
            <div className="flex-1 overflow-hidden">
              {/* Search */}
              <div className="border-b border-zinc-800 p-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search templates..."
                    className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 pl-10 pr-10 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Templates grid */}
              <div className="h-[calc(100%-68px)] overflow-y-auto p-4">
                {loading ? (
                  <div className="flex h-full items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
                  </div>
                ) : error ? (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <p className="text-sm text-red-400">{error}</p>
                    <button
                      onClick={loadTemplates}
                      className="mt-2 text-sm text-cachi-400 hover:underline"
                    >
                      Try again
                    </button>
                  </div>
                ) : templates.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <Store className="mb-3 h-10 w-10 text-zinc-600" />
                    <p className="text-sm text-zinc-500">No templates found</p>
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="mt-2 text-sm text-cachi-400 hover:underline"
                      >
                        Clear search
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-4">
                    {templates.map((template) => (
                      <BotCard
                        key={template.id}
                        template={template}
                        onClick={() => setSelectedTemplate(template)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Template detail dialog */}
      <BotDetailDialog
        template={selectedTemplate}
        onClose={() => setSelectedTemplate(null)}
        onInstalled={handleInstalled}
      />
    </>
  )
}
