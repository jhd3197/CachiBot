import { useState, useRef } from 'react'
import { Upload, FileJson, AlertCircle, Check, X } from 'lucide-react'
import { useCreationStore } from '../../../../stores/creation'
import { cn } from '../../../../lib/utils'
import type { BotIcon } from '../../../../types'

interface ImportedBot {
  name: string
  description?: string
  icon?: string
  color?: string
  model: string
  systemPrompt: string
  tools?: string[]
}

interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
  bot?: ImportedBot
}

function validateImportData(data: unknown): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (!data || typeof data !== 'object') {
    return { valid: false, errors: ['Invalid file format'], warnings: [] }
  }

  const obj = data as Record<string, unknown>

  // Check version
  if (!obj.version) {
    errors.push('Missing version field')
  } else if (obj.version !== '1.0') {
    errors.push(`Unsupported version: ${obj.version}`)
  }

  // Check bot data
  if (!obj.bot || typeof obj.bot !== 'object') {
    errors.push('Missing or invalid bot data')
    return { valid: false, errors, warnings }
  }

  const bot = obj.bot as Record<string, unknown>

  // Required fields
  if (!bot.name || typeof bot.name !== 'string') {
    errors.push('Missing bot name')
  }
  if (!bot.model || typeof bot.model !== 'string') {
    errors.push('Missing model')
  }
  if (!bot.systemPrompt || typeof bot.systemPrompt !== 'string') {
    errors.push('Missing system prompt')
  }

  // Warnings for missing optional fields
  if (!bot.description) {
    warnings.push('No description provided')
  }
  if (!bot.icon) {
    warnings.push('Using default icon')
  }
  if (!bot.color) {
    warnings.push('Using default color')
  }

  if (errors.length > 0) {
    return { valid: false, errors, warnings }
  }

  return {
    valid: true,
    errors: [],
    warnings,
    bot: {
      name: bot.name as string,
      description: bot.description as string | undefined,
      icon: bot.icon as string | undefined,
      color: bot.color as string | undefined,
      model: bot.model as string,
      systemPrompt: bot.systemPrompt as string,
      tools: (bot.tools as string[]) || [],
    },
  }
}

export function ImportStep() {
  const { updateForm } = useCreationStore()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [isDragging, setIsDragging] = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)

  const processFile = async (file: File) => {
    if (!file.name.endsWith('.json')) {
      setValidation({
        valid: false,
        errors: ['Please select a JSON file'],
        warnings: [],
      })
      return
    }

    setFileName(file.name)

    try {
      const text = await file.text()
      const data = JSON.parse(text)
      const result = validateImportData(data)
      setValidation(result)

      if (result.valid && result.bot) {
        updateForm({
          name: result.bot.name,
          description: result.bot.description || '',
          icon: (result.bot.icon as BotIcon) || 'bot',
          color: result.bot.color || '#3b82f6',
          model: result.bot.model,
          systemPrompt: result.bot.systemPrompt,
          tools: result.bot.tools || [],
        })
      }
    } catch {
      setValidation({
        valid: false,
        errors: ['Failed to parse JSON file'],
        warnings: [],
      })
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      processFile(file)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file) {
      processFile(file)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const clearImport = () => {
    setValidation(null)
    setFileName(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      {/* File drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors',
          isDragging
            ? 'border-cachi-500 bg-cachi-500/10'
            : validation?.valid
              ? 'border-green-500/50 bg-green-500/5'
              : validation && !validation.valid
                ? 'border-red-500/50 bg-red-500/5'
                : 'border-[var(--color-border-secondary)] hover:border-[var(--color-border-secondary)]'
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileSelect}
          className="hidden"
        />

        {validation?.valid ? (
          <>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-500/20">
              <Check className="h-7 w-7 text-green-400" />
            </div>
            <p className="mt-4 font-medium text-green-400">File validated successfully</p>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{fileName}</p>
          </>
        ) : validation && !validation.valid ? (
          <>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/20">
              <AlertCircle className="h-7 w-7 text-red-400" />
            </div>
            <p className="mt-4 font-medium text-red-400">Invalid file</p>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{fileName}</p>
          </>
        ) : (
          <>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-bg-secondary)]">
              <Upload className="h-7 w-7 text-[var(--color-text-secondary)]" />
            </div>
            <p className="mt-4 font-medium text-[var(--color-text-primary)]">
              Drop a bot file here or click to browse
            </p>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Supports .json export files</p>
          </>
        )}
      </div>

      {/* Validation messages */}
      {validation && (
        <div className="space-y-3">
          {validation.errors.length > 0 && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
              <h4 className="flex items-center gap-2 text-sm font-medium text-red-400">
                <X className="h-4 w-4" />
                Errors
              </h4>
              <ul className="mt-2 space-y-1">
                {validation.errors.map((error, i) => (
                  <li key={i} className="text-sm text-red-300">
                    {error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {validation.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
              <h4 className="flex items-center gap-2 text-sm font-medium text-amber-400">
                <AlertCircle className="h-4 w-4" />
                Warnings
              </h4>
              <ul className="mt-2 space-y-1">
                {validation.warnings.map((warning, i) => (
                  <li key={i} className="text-sm text-amber-300">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Bot preview */}
      {validation?.valid && validation.bot && (
        <div className="rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-4">
          <h4 className="flex items-center gap-2 text-sm font-medium text-[var(--color-text-primary)]">
            <FileJson className="h-4 w-4 text-[var(--color-text-secondary)]" />
            Imported Bot Preview
          </h4>
          <div className="mt-3 space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-[var(--color-text-secondary)]">Name:</span>
              <span className="text-sm text-[var(--color-text-primary)]">{validation.bot.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-[var(--color-text-secondary)]">Model:</span>
              <span className="font-mono text-xs text-[var(--color-text-primary)]">{validation.bot.model}</span>
            </div>
            {validation.bot.tools && validation.bot.tools.length > 0 && (
              <div className="flex justify-between">
                <span className="text-sm text-[var(--color-text-secondary)]">Tools:</span>
                <span className="text-sm text-[var(--color-text-primary)]">{validation.bot.tools.length}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Clear button */}
      {validation && (
        <button
          onClick={clearImport}
          className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-secondary)]"
        >
          Clear and try again
        </button>
      )}
    </div>
  )
}
