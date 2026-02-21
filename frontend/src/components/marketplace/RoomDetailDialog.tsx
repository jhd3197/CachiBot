import { useState } from 'react'
import { Star, Download, Loader2, Users } from 'lucide-react'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
} from '../common/Dialog'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { installRoomMarketplaceTemplate } from '../../api/client'
import { useRoomStore } from '../../stores/rooms'
import type { RoomMarketplaceTemplate, BotIcon } from '../../types'

const MODE_LABELS: Record<string, string> = {
  parallel: 'Parallel',
  sequential: 'Sequential',
  chain: 'Chain',
  router: 'Router',
  debate: 'Debate',
  waterfall: 'Waterfall',
}

const MODE_DESCRIPTIONS: Record<string, string> = {
  parallel: 'All bots respond simultaneously to each message',
  sequential: 'Bots take turns responding one after another',
  chain: 'Each bot builds on the previous bot\'s output',
  router: 'AI picks the best bot for each message',
  debate: 'Bots argue different positions in structured rounds',
  waterfall: 'Bots respond in sequence, stopping when resolved',
}

interface RoomDetailDialogProps {
  template: RoomMarketplaceTemplate | null
  onClose: () => void
  onInstalled: (roomId: string) => void
}

function formatDownloads(n: number): string {
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`
  }
  return String(n)
}

export function RoomDetailDialog({ template, onClose, onInstalled }: RoomDetailDialogProps) {
  const { addRoom, setActiveRoom } = useRoomStore()
  const [isInstalling, setIsInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = async () => {
    if (!template) return

    setIsInstalling(true)
    setError(null)

    try {
      const result = await installRoomMarketplaceTemplate(template.id)

      // Refresh rooms to pick up the newly created room
      const { getRooms } = await import('../../api/rooms')
      const rooms = await getRooms()
      const newRoom = rooms.find((r) => r.id === result.room_id)
      if (newRoom) {
        addRoom(newRoom)
        setActiveRoom(newRoom.id)
      }

      onInstalled(result.room_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to install room template')
    } finally {
      setIsInstalling(false)
    }
  }

  if (!template) return null

  return (
    <Dialog open={!!template} onClose={onClose} size="lg">
      <DialogHeader
        title={template.name}
        subtitle={template.description}
        icon={
          <BotIconRenderer
            icon={template.icon as BotIcon}
            size={20}
            color={template.color}
          />
        }
        onClose={onClose}
      />

      <DialogContent scrollable>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Stats row */}
          <div className="bot-detail__stats">
            <div className="bot-detail__stat bot-detail__stat--rating">
              <Star size={16} />
              <span>{template.rating.toFixed(1)}</span>
              <span className="bot-detail__stat-label">rating</span>
            </div>
            <div className="bot-detail__stat bot-detail__stat--downloads">
              <Download size={16} />
              <span>{formatDownloads(template.downloads)}</span>
              <span className="bot-detail__stat-label">installs</span>
            </div>
            <span className="bot-detail__category-badge">
              {template.category}
            </span>
          </div>

          {/* Response Mode */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">Response Mode</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="bot-detail__tool-badge" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6' }}>
                {MODE_LABELS[template.response_mode] || template.response_mode}
              </span>
            </div>
            <p className="form-field__help" style={{ marginTop: '0.25rem' }}>
              {MODE_DESCRIPTIONS[template.response_mode] || ''}
            </p>
          </div>

          {/* Tags */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">Tags</h3>
            <div className="bot-detail__tags">
              {template.tags.map((tag) => (
                <span key={tag} className="bot-detail__tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Included Bots */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">
              <Users size={16} style={{ color: 'var(--color-text-secondary)' }} />
              Included Bots ({template.bots.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {template.bots.map((bot, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '0.5rem',
                    background: 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border-primary)',
                  }}
                >
                  <span style={{ flex: 1, fontSize: '0.875rem', textTransform: 'capitalize' }}>
                    {bot.template_id.replace(/-/g, ' ')}
                  </span>
                  <span className="bot-detail__tool-badge">{bot.role}</span>
                  {bot.position && (
                    <span className="bot-detail__tool-badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                      {bot.position}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="bot-detail__error">
              <p>{error}</p>
            </div>
          )}
        </div>
      </DialogContent>

      <DialogFooter>
        <DialogButton variant="ghost" onClick={onClose}>
          Cancel
        </DialogButton>
        <DialogButton
          variant="primary"
          onClick={handleInstall}
          disabled={isInstalling}
        >
          {isInstalling ? (
            <>
              <Loader2 size={16} className="animate-spin" style={{ marginRight: '0.5rem' }} />
              Installing...
            </>
          ) : (
            <>
              <Download size={16} style={{ marginRight: '0.5rem' }} />
              Install Room
            </>
          )}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}
