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
        <div className="space-y-6">
          {/* Stats row */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-1.5 text-amber-400">
              <Star className="h-4 w-4 fill-current" />
              <span className="text-sm font-medium">{template.rating.toFixed(1)}</span>
              <span className="text-xs text-zinc-500">rating</span>
            </div>
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Download className="h-4 w-4" />
              <span className="text-sm font-medium">{formatDownloads(template.downloads)}</span>
              <span className="text-xs text-zinc-500">installs</span>
            </div>
            <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-400 capitalize">
              {template.category}
            </span>
          </div>

          {/* Tags */}
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-300">Tags</h3>
            <div className="flex flex-wrap gap-2">
              {template.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Tools */}
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-zinc-300">
              <Wrench className="h-4 w-4 text-zinc-500" />
              Enabled Tools
            </h3>
            <div className="flex flex-wrap gap-2">
              {template.tools.map((tool) => (
                <span
                  key={tool}
                  className="rounded-lg border border-zinc-700 bg-zinc-800/50 px-2.5 py-1 text-xs text-zinc-300"
                >
                  {tool.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* System Prompt */}
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-zinc-300">
              <MessageSquare className="h-4 w-4 text-zinc-500" />
              System Prompt
            </h3>
            <div className="max-h-48 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="whitespace-pre-wrap text-sm text-zinc-400">
                {template.system_prompt}
              </p>
            </div>
          </div>

          {/* Model */}
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-300">Recommended Model</h3>
            <span className="rounded-lg bg-zinc-800 px-3 py-1.5 font-mono text-xs text-zinc-300">
              {template.model}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
              <p className="text-sm text-red-400">{error}</p>
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
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Installing...
            </>
          ) : (
            <>
              <Download className="h-4 w-4 mr-2" />
              Install Template
            </>
          )}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}
