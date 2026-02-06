import { useState, useEffect } from 'react'
import { X, Save, RotateCcw, Clock, FileText, FolderLock } from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import type { Tool, ToolConfigs, PythonExecuteConfig, FileOperationsConfig, ShellRunConfig } from '../../types'
import { cn } from '../../lib/utils'

interface ToolConfigDialogProps {
  tool: Tool
  botId: string
  currentConfigs?: ToolConfigs
  isOpen: boolean
  onClose: () => void
}

// Default values for each tool type
const DEFAULT_PYTHON_CONFIG: PythonExecuteConfig = {
  timeoutSeconds: 30,
  maxOutputLength: 10000,
}

const DEFAULT_FILE_CONFIG: FileOperationsConfig = {
  maxFileSizeKb: 1024,
  restrictToWorkspace: true,
}

const DEFAULT_SHELL_CONFIG: ShellRunConfig = {
  timeoutSeconds: 30,
}

export function ToolConfigDialog({ tool, botId, currentConfigs, isOpen, onClose }: ToolConfigDialogProps) {
  const { updateBot } = useBotStore()

  // Python execute config state
  const [pyTimeout, setPyTimeout] = useState(DEFAULT_PYTHON_CONFIG.timeoutSeconds)
  const [pyMaxOutput, setPyMaxOutput] = useState(DEFAULT_PYTHON_CONFIG.maxOutputLength)

  // File operations config state
  const [fileMaxSize, setFileMaxSize] = useState(DEFAULT_FILE_CONFIG.maxFileSizeKb)
  const [fileRestrictWorkspace, setFileRestrictWorkspace] = useState(DEFAULT_FILE_CONFIG.restrictToWorkspace)

  // Shell run config state
  const [shellTimeout, setShellTimeout] = useState(DEFAULT_SHELL_CONFIG.timeoutSeconds)

  // Initialize state from current configs
  useEffect(() => {
    if (!isOpen) return

    if (tool.id === 'python_execute') {
      const cfg = currentConfigs?.python_execute
      setPyTimeout(cfg?.timeoutSeconds ?? DEFAULT_PYTHON_CONFIG.timeoutSeconds)
      setPyMaxOutput(cfg?.maxOutputLength ?? DEFAULT_PYTHON_CONFIG.maxOutputLength)
    } else if (['file_read', 'file_write', 'file_list'].includes(tool.id)) {
      const cfg = currentConfigs?.[tool.id as keyof ToolConfigs] as FileOperationsConfig | undefined
      setFileMaxSize(cfg?.maxFileSizeKb ?? DEFAULT_FILE_CONFIG.maxFileSizeKb)
      setFileRestrictWorkspace(cfg?.restrictToWorkspace ?? DEFAULT_FILE_CONFIG.restrictToWorkspace)
    } else if (tool.id === 'shell_run') {
      const cfg = currentConfigs?.shell_run
      setShellTimeout(cfg?.timeoutSeconds ?? DEFAULT_SHELL_CONFIG.timeoutSeconds)
    }
  }, [isOpen, tool.id, currentConfigs])

  const handleSave = () => {
    const newConfigs: ToolConfigs = { ...currentConfigs }

    if (tool.id === 'python_execute') {
      newConfigs.python_execute = {
        timeoutSeconds: pyTimeout,
        maxOutputLength: pyMaxOutput,
      }
    } else if (['file_read', 'file_write', 'file_list'].includes(tool.id)) {
      const fileConfig: FileOperationsConfig = {
        maxFileSizeKb: fileMaxSize,
        restrictToWorkspace: fileRestrictWorkspace,
      }
      newConfigs[tool.id as 'file_read' | 'file_write' | 'file_list'] = fileConfig
    } else if (tool.id === 'shell_run') {
      newConfigs.shell_run = {
        timeoutSeconds: shellTimeout,
      }
    }

    updateBot(botId, { toolConfigs: newConfigs })
    onClose()
  }

  const handleReset = () => {
    if (tool.id === 'python_execute') {
      setPyTimeout(DEFAULT_PYTHON_CONFIG.timeoutSeconds)
      setPyMaxOutput(DEFAULT_PYTHON_CONFIG.maxOutputLength)
    } else if (['file_read', 'file_write', 'file_list'].includes(tool.id)) {
      setFileMaxSize(DEFAULT_FILE_CONFIG.maxFileSizeKb)
      setFileRestrictWorkspace(DEFAULT_FILE_CONFIG.restrictToWorkspace)
    } else if (tool.id === 'shell_run') {
      setShellTimeout(DEFAULT_SHELL_CONFIG.timeoutSeconds)
    }
  }

  if (!isOpen) return null

  const renderPythonExecuteConfig = () => (
    <div className="space-y-6">
      {/* Timeout */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <Clock className="h-4 w-4 text-zinc-500" />
            Timeout
          </label>
          <span className="text-sm text-zinc-400">{pyTimeout}s</span>
        </div>
        <input
          type="range"
          min={5}
          max={120}
          step={5}
          value={pyTimeout}
          onChange={(e) => setPyTimeout(Number(e.target.value))}
          className="w-full accent-cachi-500"
        />
        <div className="flex justify-between text-xs text-zinc-500">
          <span>5s</span>
          <span>120s</span>
        </div>
        <p className="text-xs text-zinc-500">
          Maximum execution time before the code is terminated.
        </p>
      </div>

      {/* Max output */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <FileText className="h-4 w-4 text-zinc-500" />
            Max Output Length
          </label>
          <span className="text-sm text-zinc-400">{(pyMaxOutput / 1000).toFixed(0)}k chars</span>
        </div>
        <input
          type="range"
          min={1000}
          max={50000}
          step={1000}
          value={pyMaxOutput}
          onChange={(e) => setPyMaxOutput(Number(e.target.value))}
          className="w-full accent-cachi-500"
        />
        <div className="flex justify-between text-xs text-zinc-500">
          <span>1k</span>
          <span>50k</span>
        </div>
        <p className="text-xs text-zinc-500">
          Maximum characters of output to capture from code execution.
        </p>
      </div>
    </div>
  )

  const renderFileOperationsConfig = () => (
    <div className="space-y-6">
      {/* Max file size */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <FileText className="h-4 w-4 text-zinc-500" />
            Max File Size
          </label>
          <span className="text-sm text-zinc-400">{fileMaxSize} KB</span>
        </div>
        <input
          type="range"
          min={64}
          max={10240}
          step={64}
          value={fileMaxSize}
          onChange={(e) => setFileMaxSize(Number(e.target.value))}
          className="w-full accent-cachi-500"
        />
        <div className="flex justify-between text-xs text-zinc-500">
          <span>64 KB</span>
          <span>10 MB</span>
        </div>
        <p className="text-xs text-zinc-500">
          Maximum file size that can be read or written.
        </p>
      </div>

      {/* Restrict to workspace */}
      <div className="flex items-center justify-between rounded-lg border border-zinc-800 p-4">
        <div className="flex items-center gap-3">
          <FolderLock className="h-5 w-5 text-zinc-400" />
          <div>
            <h4 className="text-sm font-medium text-zinc-200">Restrict to Workspace</h4>
            <p className="text-xs text-zinc-500">Only allow operations within the workspace folder</p>
          </div>
        </div>
        <button
          onClick={() => setFileRestrictWorkspace(!fileRestrictWorkspace)}
          className={cn(
            'relative h-6 w-11 rounded-full transition-colors',
            fileRestrictWorkspace ? 'bg-cachi-600' : 'bg-zinc-700'
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
              fileRestrictWorkspace ? 'left-[22px]' : 'left-0.5'
            )}
          />
        </button>
      </div>
    </div>
  )

  const renderShellRunConfig = () => (
    <div className="space-y-6">
      {/* Timeout */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <Clock className="h-4 w-4 text-zinc-500" />
            Timeout
          </label>
          <span className="text-sm text-zinc-400">{shellTimeout}s</span>
        </div>
        <input
          type="range"
          min={5}
          max={120}
          step={5}
          value={shellTimeout}
          onChange={(e) => setShellTimeout(Number(e.target.value))}
          className="w-full accent-cachi-500"
        />
        <div className="flex justify-between text-xs text-zinc-500">
          <span>5s</span>
          <span>120s</span>
        </div>
        <p className="text-xs text-zinc-500">
          Maximum execution time before the shell command is terminated.
        </p>
      </div>
    </div>
  )

  const renderConfigForm = () => {
    switch (tool.id) {
      case 'python_execute':
        return renderPythonExecuteConfig()
      case 'file_read':
      case 'file_write':
      case 'file_list':
        return renderFileOperationsConfig()
      case 'shell_run':
        return renderShellRunConfig()
      default:
        return (
          <div className="py-8 text-center text-zinc-500">
            No configuration options available for this tool.
          </div>
        )
    }
  }

  const hasConfig = ['python_execute', 'file_read', 'file_write', 'file_list', 'shell_run'].includes(tool.id)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Configure {tool.name}</h2>
            <p className="text-sm text-zinc-500">{tool.description}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {renderConfigForm()}
        </div>

        {/* Footer */}
        <div className="flex justify-between border-t border-zinc-800 p-4">
          <button
            onClick={handleReset}
            disabled={!hasConfig}
            className="flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Defaults
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasConfig}
              className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
