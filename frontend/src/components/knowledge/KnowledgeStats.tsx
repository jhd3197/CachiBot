/**
 * Knowledge Stats Component
 *
 * Displays knowledge base statistics for a bot in a card grid layout.
 */

import { useEffect, useState } from 'react'
import { FileText, Puzzle, StickyNote, BookOpen, RefreshCw, RotateCcw } from 'lucide-react'
import { useKnowledgeStore, type KnowledgeStats as KnowledgeStatsType } from '../../stores/knowledge'

interface KnowledgeStatsProps {
  botId: string
}

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-5 w-5 rounded bg-zinc-700" />
        <div className="h-3 w-16 rounded bg-zinc-700" />
      </div>
      <div className="h-6 w-10 rounded bg-zinc-700" />
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  subtitle,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: React.ReactNode
  subtitle?: string
}) {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-5 w-5 text-zinc-400" />
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
      {subtitle && <p className="mt-1 text-xs text-zinc-500">{subtitle}</p>}
    </div>
  )
}

function buildDocumentSubtitle(stats: KnowledgeStatsType): string {
  const parts: string[] = []
  if (stats.documents_ready > 0) parts.push(`${stats.documents_ready} ready`)
  if (stats.documents_processing > 0) parts.push(`${stats.documents_processing} processing`)
  if (stats.documents_failed > 0) parts.push(`${stats.documents_failed} failed`)
  return parts.join(', ')
}

export function KnowledgeStats({ botId }: KnowledgeStatsProps) {
  const { stats, loadingStats, loadStats, reindexDocuments } = useKnowledgeStore()

  const botStats = stats[botId]
  const isLoading = loadingStats[botId]
  const [reindexing, setReindexing] = useState(false)
  const [confirmReindex, setConfirmReindex] = useState(false)

  const handleReindex = async () => {
    setConfirmReindex(false)
    setReindexing(true)
    try {
      await reindexDocuments(botId)
      await loadStats(botId)
    } finally {
      setReindexing(false)
    }
  }

  useEffect(() => {
    loadStats(botId)
  }, [botId, loadStats])

  if (isLoading && !botStats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  if (!botStats) {
    return null
  }

  const documentSubtitle = buildDocumentSubtitle(botStats)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-300">Knowledge Base</h3>
        <div className="flex items-center gap-1">
          {botStats.total_documents > 0 && !confirmReindex && (
            <button
              onClick={() => setConfirmReindex(true)}
              disabled={reindexing}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
              title="Re-index all documents"
            >
              <RotateCcw className={`h-3.5 w-3.5 ${reindexing ? 'animate-spin' : ''}`} />
              {reindexing ? 'Re-indexing...' : 'Re-index'}
            </button>
          )}
          {confirmReindex && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-zinc-400">Re-index all?</span>
              <button
                onClick={handleReindex}
                className="px-2 py-0.5 text-xs rounded bg-cachi-600 text-white hover:bg-cachi-500"
              >
                Yes
              </button>
              <button
                onClick={() => setConfirmReindex(false)}
                className="px-2 py-0.5 text-xs rounded border border-zinc-600 text-zinc-300 hover:bg-zinc-700"
              >
                No
              </button>
            </div>
          )}
          <button
            onClick={() => loadStats(botId)}
            disabled={isLoading}
            className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
            title="Refresh stats"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          icon={FileText}
          label="Documents"
          value={botStats.total_documents}
          subtitle={documentSubtitle || undefined}
        />

        <StatCard
          icon={Puzzle}
          label="Chunks"
          value={botStats.total_chunks}
        />

        <StatCard
          icon={StickyNote}
          label="Notes"
          value={botStats.total_notes}
        />

        <StatCard
          icon={BookOpen}
          label="Instructions"
          value={
            botStats.has_instructions ? (
              <span className="inline-flex items-center rounded-full bg-cachi-500/15 px-2.5 py-0.5 text-sm font-medium text-cachi-500">
                Active
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-zinc-700/50 px-2.5 py-0.5 text-sm font-medium text-zinc-500">
                Not set
              </span>
            )
          }
        />
      </div>
    </div>
  )
}
