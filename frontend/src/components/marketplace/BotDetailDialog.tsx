import { useState } from 'react'
import { Star, Download, Wrench, MessageSquare, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
} from '../common/Dialog'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { installMarketplaceTemplate, type MarketplaceTemplate } from '../../api/client'
import { useBotStore } from '../../stores/bots'
import type { Bot, BotIcon } from '../../types'

interface BotDetailDialogProps {
  template: MarketplaceTemplate | null
  onClose: () => void
  onInstalled: (botId: string) => void
}

function formatDownloads(n: number): string {
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`
  }
  return String(n)
}

export function BotDetailDialog({ template, onClose, onInstalled }: BotDetailDialogProps) {
  const { addBot, setActiveBot } = useBotStore()
  const [isInstalling, setIsInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = async () => {
    if (!template) return

    setIsInstalling(true)
    setError(null)

    try {
      const result = await installMarketplaceTemplate(template.id)

      // Also add to local store for immediate availability
      const newBot: Bot = {
        id: result.bot_id,
        name: template.name,
        description: template.description,
        icon: template.icon as BotIcon,
        color: template.color,
        model: template.model,
        systemPrompt: template.system_prompt,
        tools: template.tools,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }
      addBot(newBot)
      setActiveBot(result.bot_id)
      onInstalled(result.bot_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to install template')
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
        iconClassName={`bg-[${template.color}20]`}
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

          {/* Tools */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">
              <Wrench size={16} style={{ color: 'var(--color-text-secondary)' }} />
              Enabled Tools
            </h3>
            <div className="bot-detail__tools">
              {template.tools.map((tool) => (
                <span key={tool} className="bot-detail__tool-badge">
                  {tool.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* System Prompt */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">
              <MessageSquare size={16} style={{ color: 'var(--color-text-secondary)' }} />
              System Prompt
            </h3>
            <div className="bot-detail__prompt-box">
              <p className="bot-detail__prompt-text">
                {template.system_prompt}
              </p>
            </div>
          </div>

          {/* Model */}
          <div className="bot-detail__section">
            <h3 className="bot-detail__section-title">Recommended Model</h3>
            <span className="bot-detail__model-badge">
              {template.model}
            </span>
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
              Install Template
            </>
          )}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}
