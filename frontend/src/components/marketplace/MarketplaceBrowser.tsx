import { useState, useEffect } from 'react'
import { Search, Store, Loader2, X, Users } from 'lucide-react'
import {
  Dialog,
  DialogHeader,
  DialogContent,
} from '../common/Dialog'
import { BotCard } from './BotCard'
import { BotDetailPanel } from './BotDetailPanel'
import { RoomCard } from './RoomCard'
import { RoomDetailPanel } from './RoomDetailPanel'
import {
  getMarketplaceTemplates,
  getMarketplaceCategories,
  getRoomMarketplaceTemplates,
  getRoomMarketplaceCategories,
  type MarketplaceTemplate,
  type MarketplaceCategory,
} from '../../api/client'
import type { RoomMarketplaceTemplate } from '../../types'

type MarketplaceTab = 'bots' | 'rooms'

interface MarketplaceBrowserProps {
  open: boolean
  onClose: () => void
  onInstalled?: (botId: string) => void
  onRoomInstalled?: (roomId: string) => void
  initialTab?: MarketplaceTab
}

export function MarketplaceBrowser({ open, onClose, onInstalled, onRoomInstalled, initialTab = 'bots' }: MarketplaceBrowserProps) {
  const [tab, setTab] = useState<MarketplaceTab>(initialTab)
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([])
  const [categories, setCategories] = useState<MarketplaceCategory[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTemplate, setSelectedTemplate] = useState<MarketplaceTemplate | null>(null)

  // Room state
  const [roomTemplates, setRoomTemplates] = useState<RoomMarketplaceTemplate[]>([])
  const [roomLoading, setRoomLoading] = useState(false)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [selectedRoomTemplate, setSelectedRoomTemplate] = useState<RoomMarketplaceTemplate | null>(null)

  // Sync initialTab when it changes
  useEffect(() => {
    setTab(initialTab)
  }, [initialTab])

  // Fetch categories and templates on mount and tab change
  useEffect(() => {
    if (open) {
      if (tab === 'bots') {
        loadCategories()
        loadTemplates()
      } else {
        loadRoomCategories()
        loadRoomTemplates()
      }
    }
  }, [open, tab])

  // Reload templates when filter changes
  useEffect(() => {
    if (open) {
      if (tab === 'bots') {
        loadTemplates()
      } else {
        loadRoomTemplates()
      }
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

  const loadRoomCategories = async () => {
    try {
      const data = await getRoomMarketplaceCategories()
      setCategories(data)
    } catch (err) {
      console.error('Failed to load room categories:', err)
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

  const loadRoomTemplates = async () => {
    setRoomLoading(true)
    setRoomError(null)

    try {
      const data = await getRoomMarketplaceTemplates(
        selectedCategory || undefined,
        searchQuery || undefined
      )
      setRoomTemplates(data.templates)
    } catch (err) {
      setRoomError(err instanceof Error ? err.message : 'Failed to load room templates')
    } finally {
      setRoomLoading(false)
    }
  }

  const handleInstalled = (botId: string) => {
    setSelectedTemplate(null)
    onInstalled?.(botId)
    onClose()
  }

  const handleRoomInstalled = (roomId: string) => {
    setSelectedRoomTemplate(null)
    onRoomInstalled?.(roomId)
    onClose()
  }

  const showDetail = selectedTemplate || selectedRoomTemplate

  return (
    <Dialog open={open} onClose={onClose} size="xxl">
      <DialogHeader
        title="Marketplace"
        subtitle={tab === 'bots' ? 'Discover and install bot templates' : 'Discover and install room templates'}
        icon={tab === 'bots'
          ? <Store size={20} style={{ color: 'var(--accent-500)' }} />
          : <Users size={20} style={{ color: 'var(--accent-500)' }} />
        }
        onClose={onClose}
      />

      <DialogContent className="p-0">
        <div className="marketplace">
          {/* Sidebar */}
          <div className="marketplace__sidebar">
            {/* Tab switcher */}
            <div className="marketplace__tabs">
              <button
                onClick={() => { setTab('bots'); setSelectedCategory(null); setSearchQuery(''); setSelectedTemplate(null); setSelectedRoomTemplate(null) }}
                className={`marketplace__tab${tab === 'bots' ? ' marketplace__tab--active' : ''}`}
              >
                <Store size={14} />
                Bots
              </button>
              <button
                onClick={() => { setTab('rooms'); setSelectedCategory(null); setSearchQuery(''); setSelectedTemplate(null); setSelectedRoomTemplate(null) }}
                className={`marketplace__tab${tab === 'rooms' ? ' marketplace__tab--active' : ''}`}
              >
                <Users size={14} />
                Rooms
              </button>
            </div>

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
            {/* Inline detail panel when a template is selected */}
            {selectedTemplate && (
              <BotDetailPanel
                template={selectedTemplate}
                onBack={() => setSelectedTemplate(null)}
                onInstalled={handleInstalled}
              />
            )}

            {selectedRoomTemplate && (
              <RoomDetailPanel
                template={selectedRoomTemplate}
                onBack={() => setSelectedRoomTemplate(null)}
                onInstalled={handleRoomInstalled}
              />
            )}

            {/* Search + grid when no detail is shown */}
            {!showDetail && (
              <>
                {/* Search */}
                <div className="marketplace__search">
                  <div className="marketplace__search-wrap">
                    <Search size={16} className="marketplace__search-icon" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={tab === 'bots' ? 'Search bot templates...' : 'Search room templates...'}
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

                {/* Bot templates grid */}
                {tab === 'bots' && (
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
                )}

                {/* Room templates grid */}
                {tab === 'rooms' && (
                  <div className="marketplace__grid">
                    {roomLoading ? (
                      <div className="marketplace__loading" style={{ gridColumn: '1 / -1' }}>
                        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-text-secondary)' }} />
                      </div>
                    ) : roomError ? (
                      <div className="marketplace__error" style={{ gridColumn: '1 / -1' }}>
                        <p style={{ fontSize: '0.875rem', color: 'var(--color-danger-text)' }}>{roomError}</p>
                        <button onClick={loadRoomTemplates} className="marketplace__retry">
                          Try again
                        </button>
                      </div>
                    ) : roomTemplates.length === 0 ? (
                      <div className="marketplace__empty" style={{ gridColumn: '1 / -1' }}>
                        <Users size={40} style={{ marginBottom: '0.75rem', color: 'var(--color-text-tertiary)' }} />
                        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>No room templates found</p>
                        {searchQuery && (
                          <button onClick={() => setSearchQuery('')} className="marketplace__retry">
                            Clear search
                          </button>
                        )}
                      </div>
                    ) : (
                      roomTemplates.map((template) => (
                        <RoomCard
                          key={template.id}
                          template={template}
                          onClick={() => setSelectedRoomTemplate(template)}
                        />
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
