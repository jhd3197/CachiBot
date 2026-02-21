import { Star, Download, Users } from 'lucide-react'
import { BotIconRenderer } from '../common/BotIconRenderer'
import type { RoomMarketplaceTemplate } from '../../types'
import type { BotIcon } from '../../types'

const MODE_LABELS: Record<string, string> = {
  parallel: 'Parallel',
  sequential: 'Sequential',
  chain: 'Chain',
  router: 'Router',
  debate: 'Debate',
  waterfall: 'Waterfall',
}

interface RoomCardProps {
  template: RoomMarketplaceTemplate
  onClick: () => void
}

function formatDownloads(n: number): string {
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`
  }
  return String(n)
}

export function RoomCard({ template, onClick }: RoomCardProps) {
  return (
    <button onClick={onClick} className="bot-card">
      {/* Header */}
      <div className="bot-card__header">
        <div
          className="bot-card__icon"
          style={{ backgroundColor: template.color + '20' }}
        >
          <BotIconRenderer
            icon={template.icon as BotIcon}
            size={24}
            color={template.color}
          />
        </div>
        <div className="bot-card__info">
          <h3 className="bot-card__title">{template.name}</h3>
          <p className="bot-card__author">{MODE_LABELS[template.response_mode] || template.response_mode} mode</p>
        </div>
      </div>

      {/* Description */}
      <p className="bot-card__description">{template.description}</p>

      {/* Tags */}
      <div className="bot-card__tags">
        <span className="bot-card__tag bot-card__tag--mode">
          {MODE_LABELS[template.response_mode] || template.response_mode}
        </span>
        {template.tags.slice(0, 2).map((tag) => (
          <span key={tag} className="bot-card__tag">
            {tag}
          </span>
        ))}
        {template.tags.length > 2 && (
          <span className="bot-card__overflow">+{template.tags.length - 2}</span>
        )}
      </div>

      {/* Footer */}
      <div className="bot-card__footer">
        <div className="bot-card__rating">
          <Star size={14} />
          <span className="bot-card__rating-value">{template.rating.toFixed(1)}</span>
        </div>
        <div className="bot-card__downloads">
          <Download size={14} />
          <span>{formatDownloads(template.downloads)}</span>
        </div>
        <div className="bot-card__downloads">
          <Users size={14} />
          <span>{template.bots.length} bots</span>
        </div>
      </div>
    </button>
  )
}
