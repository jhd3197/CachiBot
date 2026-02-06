import {
  FileText,
  FilePen,
  Trash2,
  Code,
  Terminal,
  Globe,
  Search,
  Database,
  Wrench,
  type LucideIcon,
} from 'lucide-react'

const toolIconMap: Record<string, LucideIcon> = {
  'file_read': FileText,
  'file_write': FilePen,
  'file_delete': Trash2,
  'python_execute': Code,
  'shell_run': Terminal,
  'web_fetch': Globe,
  'web_search': Search,
  'database_query': Database,
}

interface ToolIconRendererProps {
  toolId: string
  className?: string
  size?: number
}

export function ToolIconRenderer({ toolId, className, size = 20 }: ToolIconRendererProps) {
  const IconComponent = toolIconMap[toolId] || Wrench
  return <IconComponent className={className} size={size} />
}

export function getToolIconComponent(toolId: string): LucideIcon {
  return toolIconMap[toolId] || Wrench
}
