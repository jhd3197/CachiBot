import { Star, Download } from 'lucide-react'
import { BotIconRenderer } from '../common/BotIconRenderer'
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
  return (
    <button
      onClick={onClick}
      className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 text-left transition-all hover:border-zinc-700 hover:bg-zinc-800/50"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-xl"
          style={{ backgroundColor: template.color + '20' }}
        >
          <BotIconRenderer
            icon={template.icon as BotIcon}
            size={24}
            color={template.color}
          />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-zinc-100 truncate">{template.name}</h3>
          <p className="text-xs text-zinc-500 capitalize">{template.category}</p>
        </div>
      </div>

      {/* Description */}
      <p className="mt-3 text-sm text-zinc-400 line-clamp-2">{template.description}</p>

      {/* Tags */}
      <div className="mt-3 flex flex-wrap gap-1">
        {template.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500"
          >
            {tag}
          </span>
        ))}
        {template.tags.length > 3 && (
          <span className="text-[10px] text-zinc-600">+{template.tags.length - 3}</span>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-zinc-800 pt-3">
        <div className="flex items-center gap-1 text-amber-400">
          <Star className="h-3.5 w-3.5 fill-current" />
          <span className="text-xs font-medium">{template.rating.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-1 text-zinc-500">
          <Download className="h-3.5 w-3.5" />
          <span className="text-xs">{formatDownloads(template.downloads)}</span>
        </div>
      </div>
    </button>
  )
}
