import { MessageSquare, FolderOpen, History, Trash2 } from 'lucide-react'
import { Button } from '../common/Button'
import { useUIStore } from '../../stores/ui'
import { useChatStore } from '../../stores/bots'
import { useConfigStore } from '../../stores/config'
import { cn } from '../../lib/utils'

export function Sidebar() {
  const { sidebarCollapsed } = useUIStore()
  const { chats } = useChatStore()
  const { config } = useConfigStore()

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-zinc-200 bg-zinc-50 transition-transform dark:border-[var(--color-border-primary)] dark:bg-[var(--color-bg-primary)]/50 lg:static lg:translate-x-0',
        sidebarCollapsed ? '-translate-x-full' : 'translate-x-0'
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-zinc-200 px-4 dark:border-[var(--color-border-primary)]">
        <span className="font-medium">Chat</span>
        <Button
          variant="ghost"
          size="sm"
          disabled={chats.length === 0}
          title="Clear chat"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3">
        <div className="space-y-1">
          <SidebarItem
            icon={<MessageSquare className="h-4 w-4" />}
            label="New Chat"
            active
          />
          <SidebarItem
            icon={<History className="h-4 w-4" />}
            label="History"
          />
        </div>
      </nav>

      {/* Workspace info */}
      {config && (
        <div className="border-t border-zinc-200 p-4 dark:border-[var(--color-border-primary)]">
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">
            <FolderOpen className="h-4 w-4 flex-shrink-0" />
            <span className="truncate" title={config.workspacePath}>
              {config.workspacePath.split(/[/\\]/).pop()}
            </span>
          </div>
        </div>
      )}
    </aside>
  )
}

interface SidebarItemProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick?: () => void
}

function SidebarItem({ icon, label, active, onClick }: SidebarItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
        active
          ? 'bg-cachi-100 text-cachi-700 dark:bg-cachi-900/30 dark:text-cachi-400'
          : 'text-[var(--color-text-tertiary)] hover:bg-zinc-100 dark:text-[var(--color-text-secondary)] dark:hover:bg-[var(--color-hover-bg)]'
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
