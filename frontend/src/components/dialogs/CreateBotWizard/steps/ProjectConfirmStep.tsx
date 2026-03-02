import { Check, Bot, Layers } from 'lucide-react'
import { useCreationStore } from '../../../../stores/creation'
import { BotIconRenderer } from '../../../common/BotIconRenderer'

const MODE_LABELS: Record<string, string> = {
  parallel: 'Parallel',
  sequential: 'Sequential',
  chain: 'Chain',
  router: 'Router',
  debate: 'Debate',
  waterfall: 'Waterfall',
  relay: 'Relay',
  consensus: 'Consensus',
  interview: 'Interview',
}

export function ProjectConfirmStep() {
  const { form } = useCreationStore()
  const proposal = form.projectProposal

  if (!proposal) return null

  return (
    <div className="space-y-6">
      {/* Project header */}
      <div className="rounded-xl border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-5">
        <h2 className="text-lg font-bold text-[var(--color-text-primary)]">
          {proposal.projectName}
        </h2>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          {proposal.projectDescription}
        </p>
      </div>

      {/* Bots summary */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Bot className="h-4 w-4 text-cachi-400" />
          {proposal.bots.length} Bots
        </h3>
        <div className="flex flex-wrap gap-2">
          {proposal.bots.map((bot) => (
            <div
              key={bot.tempId}
              className="flex items-center gap-2 rounded-full border border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)] px-3 py-1.5"
            >
              <BotIconRenderer icon={bot.icon} size={14} color={bot.color} />
              <span className="text-xs font-medium text-[var(--color-text-primary)]">
                {bot.name}
              </span>
              <span className="text-[10px] text-[var(--color-text-tertiary)]">
                {bot.role} · {bot.tone} · {bot.expertiseLevel}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Rooms summary */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Layers className="h-4 w-4 text-cachi-400" />
          {proposal.rooms.length} Rooms
        </h3>
        <div className="space-y-2">
          {proposal.rooms.map((room) => {
            const assignedBots = proposal.bots.filter((b) =>
              room.botTempIds.includes(b.tempId),
            )
            return (
              <div
                key={room.tempId}
                className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)] p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {room.name}
                  </span>
                  <span className="rounded-full bg-[var(--color-bg-primary)] px-2.5 py-0.5 text-[10px] text-[var(--color-text-secondary)]">
                    {MODE_LABELS[room.responseMode] || room.responseMode}
                  </span>
                </div>
                {assignedBots.length > 0 && (
                  <div className="mt-2 flex items-center gap-1.5">
                    {assignedBots.map((bot, i) => (
                      <span key={bot.tempId} className="flex items-center gap-1">
                        <BotIconRenderer icon={bot.icon} size={12} color={bot.color} />
                        <span className="text-[10px] text-[var(--color-text-secondary)]">
                          {bot.name}
                        </span>
                        {i < assignedBots.length - 1 && (
                          <span className="text-[10px] text-[var(--color-text-tertiary)]">
                            {room.responseMode === 'chain' ? '→' : '·'}
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Ready indicator */}
      <div className="flex items-center gap-3 rounded-lg border border-cachi-500/30 bg-cachi-500/10 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cachi-600">
          <Check className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="font-medium text-cachi-400">Ready to create your project</p>
          <p className="text-xs text-cachi-400/70">
            This will create {proposal.bots.length} bots and {proposal.rooms.length} room
            {proposal.rooms.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>
    </div>
  )
}
