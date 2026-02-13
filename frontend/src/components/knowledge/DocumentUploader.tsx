/**
 * Document Uploader Component
 *
 * Drag-and-drop file upload for bot knowledge base.
 */

import { useCallback, useState } from 'react'
import { Upload, AlertCircle } from 'lucide-react'
import { useKnowledgeStore } from '../../stores/knowledge'

interface DocumentUploaderProps {
  botId: string
}

const ALLOWED_TYPES = ['.pdf', '.txt', '.md', '.docx']
const MAX_SIZE_MB = 10

export function DocumentUploader({ botId }: DocumentUploaderProps) {
  const { uploadDocument, uploadingBots, error, clearError } = useKnowledgeStore()
  const [isDragging, setIsDragging] = useState(false)

  const isUploading = uploadingBots.has(botId)

  const handleFile = useCallback(
    async (file: File) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()

      if (!ALLOWED_TYPES.includes(ext)) {
        alert(`File type not allowed. Allowed: ${ALLOWED_TYPES.join(', ')}`)
        return
      }

      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        alert(`File too large. Maximum: ${MAX_SIZE_MB}MB`)
        return
      }

      clearError()

      try {
        await uploadDocument(botId, file)
      } catch {
        // Error handled by store
      }
    },
    [botId, uploadDocument, clearError]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFile(file)
      }
    },
    [handleFile]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleClick = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = ALLOWED_TYPES.join(',')
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        handleFile(file)
      }
    }
    input.click()
  }, [handleFile])

  return (
    <div className="space-y-2">
      <div
        onClick={!isUploading ? handleClick : undefined}
        onDrop={!isUploading ? handleDrop : undefined}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-colors
          ${isDragging ? 'border-green-500 bg-green-500/10' : 'border-zinc-700'}
          ${isUploading ? 'opacity-50 cursor-wait' : 'cursor-pointer hover:border-zinc-500'}
        `}
      >
        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-500 border-t-transparent" />
            <p className="text-sm text-zinc-400">Uploading...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-8 w-8 text-zinc-500" />
            <p className="text-sm text-zinc-300">
              {isDragging ? 'Drop file here' : 'Drag & drop or click to upload'}
            </p>
            <p className="text-xs text-zinc-500">
              PDF, TXT, MD, or DOCX files up to {MAX_SIZE_MB}MB
            </p>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}
    </div>
  )
}
