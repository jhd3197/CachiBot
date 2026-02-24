import { Star, Download } from 'lucide-react'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { useTruncate } from '../../hooks/useTruncate'
import type { MarketplaceTemplate } from '../../api/client'
import type { BotIcon } from '../../types'

interface BotCardProps {
  template: MarketplaceTemplate
  onClick: () => void
}

function formatDownloads(n: number): string {
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`
  }
  return String(n)
}

export function BotCard({ template, onClick }: BotCardProps) {
  const { ref: titleRef, display: titleText } = useTruncate(template.name)

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
        <div className="bot-card__info" ref={titleRef as React.RefObject<HTMLDivElement>}>
          <h3 className="bot-card__title" title={template.name}>{titleText}</h3>
          <p className="bot-card__author">{template.category}</p>
        </div>
      </div>

      {/* Description */}
      <p className="bot-card__description">{template.description}</p>

      {/* Tags */}
      <div className="bot-card__tags">
        {template.tags.slice(0, 3).map((tag) => (
          <span key={tag} className="bot-card__tag">
            {tag}
          </span>
        ))}
        {template.tags.length > 3 && (
          <span className="bot-card__overflow">+{template.tags.length - 3}</span>
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
      </div>
    </button>
  )
}
