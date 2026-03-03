/**
 * WorkspaceSelector — horizontal chip row of workspace-capable plugins.
 * Shown below the chat input when the chat is empty (no messages yet).
 */

import { Puzzle, Code, Globe, Palette, Zap, FileText, Layout } from 'lucide-react'
import type { WorkspaceInfo } from '../../stores/workspace'

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  puzzle: Puzzle,
  code: Code,
  globe: Globe,
  palette: Palette,
  zap: Zap,
  'file-text': FileText,
  layout: Layout,
}

interface WorkspaceSelectorProps {
  workspaces: WorkspaceInfo[]
  activeWorkspace: string | null
  onSelect: (ws: WorkspaceInfo) => void
}

export function WorkspaceSelector({ workspaces, activeWorkspace, onSelect }: WorkspaceSelectorProps) {
  if (workspaces.length === 0) return null

  return (
    <div className="workspace-selector">
      {workspaces.map((ws) => {
        const Icon = ICON_MAP[ws.icon] || Puzzle
        const isActive = activeWorkspace === ws.pluginName
        return (
          <button
            key={ws.pluginName}
            className={`workspace-chip ${isActive ? 'workspace-chip--active' : ''}`}
            style={
              isActive && ws.accentColor
                ? { borderColor: ws.accentColor, color: ws.accentColor }
                : undefined
            }
            onClick={() => onSelect(ws)}
            title={ws.description || ws.displayName}
          >
            <Icon className="workspace-chip__icon" />
            <span className="workspace-chip__label">{ws.displayName}</span>
          </button>
        )
      })}
    </div>
  )
}
