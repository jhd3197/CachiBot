import { useState } from 'react'
import { ArrowLeft, Star, Download, Wrench, MessageSquare, Loader2, CircleCheck, AlertTriangle, CircleAlert } from 'lucide-react'
import { DialogButton } from '../common/Dialog'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { installMarketplaceTemplate, type MarketplaceTemplate } from '../../api/client'
import { useBotStore } from '../../stores/bots'
import { useModelCompatibility } from '../../hooks/useModelCompatibility'
import type { Bot, BotIcon } from '../../types'

interface BotDetailPanelProps {
  template: MarketplaceTemplate
  onBack: () => void
  onInstalled: (botId: string) => void
}

function formatDownloads(n: number): string {
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`
  }
  return String(n)
}

export function BotDetailPanel({ template, onBack, onInstalled }: BotDetailPanelProps) {
  const { addBot, setActiveBot } = useBotStore()
  const [isInstalling, setIsInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const compat = useModelCompatibility(template.model)

  const handleInstall = async () => {
    setIsInstalling(true)
    setError(null)

    try {
      console.log('[BotDetailPanel] Installing bot template:', template.id, template.name)
      const result = await installMarketplaceTemplate(template.id)
      console.log('[BotDetailPanel] Install API response:', result)

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
      console.log('[BotDetailPanel] Bot added to store, calling onInstalled:', result.bot_id)
      onInstalled(result.bot_id)
    } catch (err) {
      console.error('[BotDetailPanel] Install failed:', err)
      setError(err instanceof Error ? err.message : 'Failed to install template')
    } finally {
      setIsInstalling(false)
    }
  }

  return (
    <div className="marketplace__detail">
      {/* Header with back button */}
      <div className="marketplace__detail-header">
        <button onClick={onBack} className="marketplace__detail-back">
          <ArrowLeft size={18} />
        </button>
        <BotIconRenderer icon={template.icon as BotIcon} size={20} color={template.color} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ fontWeight: 600, color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {template.name}
          </h3>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {template.description}
          </p>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="marketplace__detail-content">
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
            {compat.status === 'no_model' ? (
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
                Uses your default model
              </span>
            ) : (
              <>
                <div className="bot-detail__model-compat">
                  <span className="bot-detail__model-badge">
                    {template.model}
                  </span>
                  {compat.status === 'compatible' && (
                    <span className="bot-detail__model-status bot-detail__model-status--compatible">
                      <CircleCheck size={14} />
                      Available
                    </span>
                  )}
                  {compat.status === 'alternative' && (
                    <span className="bot-detail__model-status bot-detail__model-status--alternative">
                      <AlertTriangle size={14} />
                      Not available — you have {compat.alternatives.length} model{compat.alternatives.length !== 1 ? 's' : ''} from {compat.providerLabel}
                    </span>
                  )}
                  {compat.status === 'unavailable' && (
                    <span className="bot-detail__model-status bot-detail__model-status--unavailable">
                      <CircleAlert size={14} />
                      {compat.providerLabel || 'Provider'} not configured — will use your default model ({compat.defaultModel || 'none set'})
                    </span>
                  )}
                </div>
                {compat.status === 'alternative' && compat.alternatives.length > 0 && (
                  <div className="bot-detail__model-alternatives">
                    {compat.alternatives.slice(0, 5).map((alt) => (
                      <span key={alt} className="bot-detail__tool-badge">{alt}</span>
                    ))}
                    {compat.alternatives.length > 5 && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--color-text-tertiary)', alignSelf: 'center' }}>
                        +{compat.alternatives.length - 5} more
                      </span>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {error && (
            <div className="bot-detail__error">
              <p>{error}</p>
            </div>
          )}
        </div>
      </div>

      {/* Sticky install footer */}
      <div className="marketplace__detail-footer">
        <DialogButton variant="ghost" onClick={onBack}>
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
      </div>
    </div>
  )
}
