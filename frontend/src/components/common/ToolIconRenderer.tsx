import {
  FileText,
  FilePen,
  FolderOpen,
  FileSearch,
  FileScan,
  Trash2,
  Code,
  Terminal,
  Globe,
  Search,
  Database,
  Wrench,
  CheckCircle,
  Send,
  MessageCircle,
  Briefcase,
  ListTodo,
  ListChecks,
  CircleCheck,
  ClipboardPlus,
  ClipboardList,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  Diff,
  History,
  FileTerminal,
  Network,
  FileArchive,
  FolderArchive,
  Table,
  DatabaseZap,
  Folder,
  type LucideIcon,
} from 'lucide-react'

// Map Lucide icon name strings (from Tukuy) to imported components
const lucideIconMap: Record<string, LucideIcon> = {
  'file-text': FileText,
  'file-pen': FilePen,
  'folder-open': FolderOpen,
  'file-search': FileSearch,
  'file-scan': FileScan,
  'trash-2': Trash2,
  'code': Code,
  'terminal': Terminal,
  'globe': Globe,
  'search': Search,
  'database': Database,
  'wrench': Wrench,
  'check-circle': CheckCircle,
  'send': Send,
  'message-circle': MessageCircle,
  'briefcase': Briefcase,
  'list-todo': ListTodo,
  'list-checks': ListChecks,
  'circle-check': CircleCheck,
  'clipboard-plus': ClipboardPlus,
  'clipboard-list': ClipboardList,
  'git-branch': GitBranch,
  'git-commit-horizontal': GitCommitHorizontal,
  'git-pull-request': GitPullRequest,
  'diff': Diff,
  'history': History,
  'file-terminal': FileTerminal,
  'network': Network,
  'file-archive': FileArchive,
  'folder-archive': FolderArchive,
  'table': Table,
  'database-zap': DatabaseZap,
  'folder': Folder,
}

// Legacy fallback: map tool IDs to icons (for tools without icon metadata)
const toolIconMap: Record<string, LucideIcon> = {
  'file_read': FileText,
  'file_write': FilePen,
  'file_list': FolderOpen,
  'file_edit': FileSearch,
  'file_info': FileScan,
  'file_delete': Trash2,
  'python_execute': Code,
  'shell_execute': Terminal,
  'shell_which': FileTerminal,
  'git_status': GitPullRequest,
  'git_diff': Diff,
  'git_log': History,
  'git_commit': GitCommitHorizontal,
  'git_branch': GitBranch,
  'web_fetch': Globe,
  'web_search': Search,
  'http_request': Network,
  'sqlite_query': Database,
  'sqlite_execute': DatabaseZap,
  'sqlite_tables': Table,
  'zip_create': FolderArchive,
  'zip_extract': FolderArchive,
  'zip_list': FileArchive,
  'tar_create': FolderArchive,
  'tar_extract': FolderArchive,
  'task_complete': CheckCircle,
  'telegram_send': Send,
  'discord_send': MessageCircle,
  'work_create': Briefcase,
  'work_list': ClipboardList,
  'work_update': ClipboardPlus,
  'todo_create': ListTodo,
  'todo_list': ListChecks,
  'todo_done': CircleCheck,
}

interface ToolIconRendererProps {
  toolId: string
  icon?: string | null  // Lucide icon name from API
  className?: string
  size?: number
}

export function ToolIconRenderer({ toolId, icon, className, size = 20 }: ToolIconRendererProps) {
  // Prefer API-provided icon name, then fall back to legacy tool ID map
  const IconComponent = (icon && lucideIconMap[icon]) || toolIconMap[toolId] || Wrench
  return <IconComponent className={className} size={size} />
}

export function getToolIconComponent(toolId: string, icon?: string | null): LucideIcon {
  return (icon && lucideIconMap[icon]) || toolIconMap[toolId] || Wrench
}

// Resolve a Lucide icon name string to a component (for plugin headers)
export function resolveIconName(iconName: string | null | undefined): LucideIcon {
  if (iconName && lucideIconMap[iconName]) {
    return lucideIconMap[iconName]
  }
  return Wrench
}
