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
          icon={<Store size={20} style={{ color: 'var(--accent-500)' }} />}
          onClose={onClose}
        />

        <DialogContent className="p-0">
          <div className="marketplace">
            {/* Sidebar */}
            <div className="marketplace__sidebar">
              <nav className="marketplace__nav">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`marketplace__category${selectedCategory === null ? ' marketplace__category--active' : ''}`}
                >
                  All Templates
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`marketplace__category${selectedCategory === cat.id ? ' marketplace__category--active' : ''}`}
                  >
                    <span>{cat.name}</span>
                    <span className="marketplace__category-count">({cat.count})</span>
                  </button>
                ))}
              </nav>
            </div>

            {/* Main content */}
            <div className="marketplace__main">
              {/* Search */}
              <div className="marketplace__search">
                <div className="marketplace__search-wrap">
                  <Search size={16} className="marketplace__search-icon" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search templates..."
                    className="marketplace__search-input"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="marketplace__search-clear"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              </div>

              {/* Templates grid */}
              <div className="marketplace__grid">
                {loading ? (
                  <div className="marketplace__loading" style={{ gridColumn: '1 / -1' }}>
                    <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-text-secondary)' }} />
                  </div>
                ) : error ? (
                  <div className="marketplace__error" style={{ gridColumn: '1 / -1' }}>
                    <p style={{ fontSize: '0.875rem', color: 'var(--color-danger-text)' }}>{error}</p>
                    <button onClick={loadTemplates} className="marketplace__retry">
                      Try again
                    </button>
                  </div>
                ) : templates.length === 0 ? (
                  <div className="marketplace__empty" style={{ gridColumn: '1 / -1' }}>
                    <Store size={40} style={{ marginBottom: '0.75rem', color: 'var(--color-text-tertiary)' }} />
                    <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>No templates found</p>
                    {searchQuery && (
                      <button onClick={() => setSearchQuery('')} className="marketplace__retry">
                        Clear search
                      </button>
                    )}
                  </div>
                ) : (
                  templates.map((template) => (
                    <BotCard
                      key={template.id}
                      template={template}
                      onClick={() => setSelectedTemplate(template)}
                    />
                  ))
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
