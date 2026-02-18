import { FileText, Code, Terminal, Globe } from 'lucide-react'
import { useCreationStore } from '../../../../stores/creation'
import { cn } from '../../../../lib/utils'

const TOOL_GROUPS = [
  {
    name: 'File Operations',
    description: 'Read, write, and manage files',
    tools: [
      { id: 'file_read', name: 'Read Files', icon: FileText },
      { id: 'file_write', name: 'Write Files', icon: FileText },
      { id: 'file_list', name: 'List Files', icon: FileText },
      { id: 'file_edit', name: 'Edit Files', icon: FileText },
    ],
  },
  {
    name: 'Code Execution',
    description: 'Run code and commands',
    tools: [
      { id: 'python_execute', name: 'Python', icon: Code },
      { id: 'shell_run', name: 'Shell Commands', icon: Terminal },
    ],
  },
  {
    name: 'Web & Data',
    description: 'Access web and data tools',
    tools: [
      { id: 'web_search', name: 'Web Search', icon: Globe },
      { id: 'web_fetch', name: 'Fetch URLs', icon: Globe },
    ],
  },
]

export function CapabilitiesStep() {
  const { form, updateForm } = useCreationStore()

  const toggleTool = (toolId: string) => {
    const newTools = form.tools.includes(toolId)
      ? form.tools.filter((t) => t !== toolId)
      : [...form.tools, toolId]
    updateForm({ tools: newTools })
  }

  const toggleGroup = (groupTools: string[]) => {
    const allSelected = groupTools.every((t) => form.tools.includes(t))
    if (allSelected) {
      updateForm({ tools: form.tools.filter((t) => !groupTools.includes(t)) })
    } else {
      updateForm({ tools: [...new Set([...form.tools, ...groupTools])] })
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-4">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Select the tools your bot can use. More tools = more capabilities, but also more potential for unintended actions.
        </p>
      </div>

      {TOOL_GROUPS.map((group) => {
        const groupToolIds = group.tools.map((t) => t.id)
        const selectedCount = groupToolIds.filter((id) => form.tools.includes(id)).length
        const allSelected = selectedCount === groupToolIds.length

        return (
          <div key={group.name} className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium text-[var(--color-text-primary)]">{group.name}</h3>
                <p className="text-xs text-[var(--color-text-secondary)]">{group.description}</p>
              </div>
              <button
                onClick={() => toggleGroup(groupToolIds)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                  allSelected
                    ? 'bg-cachi-600/20 text-cachi-400 hover:bg-cachi-600/30'
                    : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)]'
                )}
              >
                {allSelected ? 'Deselect All' : 'Select All'}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {group.tools.map((tool) => {
                const Icon = tool.icon
                const isSelected = form.tools.includes(tool.id)

                return (
                  <button
                    key={tool.id}
                    onClick={() => toggleTool(tool.id)}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border p-3 text-left transition-all',
                      isSelected
                        ? 'border-cachi-500 bg-cachi-500/10'
                        : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)]'
                    )}
                  >
                    <div
                      className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-lg',
                        isSelected ? 'bg-cachi-600/20' : 'bg-[var(--color-bg-secondary)]'
                      )}
                    >
                      <Icon
                        className={cn(
                          'h-4 w-4',
                          isSelected ? 'text-cachi-400' : 'text-[var(--color-text-secondary)]'
                        )}
                      />
                    </div>
                    <span
                      className={cn(
                        'text-sm font-medium',
                        isSelected ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-secondary)]'
                      )}
                    >
                      {tool.name}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}

      <div className="flex items-center justify-between rounded-lg bg-[var(--card-bg)] px-4 py-3">
        <span className="text-sm text-[var(--color-text-secondary)]">Selected tools:</span>
        <span className="font-medium text-[var(--color-text-primary)]">{form.tools.length}</span>
      </div>
    </div>
  )
}
