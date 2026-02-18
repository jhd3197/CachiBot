/**
 * Document List Component
 *
 * Displays uploaded documents with status, retry, delete confirmation, and chunk preview.
 */

import { useEffect, useState } from 'react'
import { FileText, Trash2, Clock, CheckCircle, XCircle, RefreshCw, RotateCcw, Eye } from 'lucide-react'
import { useKnowledgeStore, type DocumentResponse } from '../../stores/knowledge'

interface DocumentListProps {
  botId: string
  onViewChunks?: (documentId: string, filename: string) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function StatusIcon({ status }: { status: DocumentResponse['status'] }) {
  switch (status) {
    case 'processing':
      return <Clock className="h-4 w-4 text-yellow-500 animate-pulse" />
    case 'ready':
      return <CheckCircle className="h-4 w-4 text-green-500" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />
  }
}

export function DocumentList({ botId, onViewChunks }: DocumentListProps) {
  const {
    loadDocuments,
    deleteDocument,
    refreshDocument,
    retryDocument,
    getDocuments,
    loadingDocuments,
  } = useKnowledgeStore()

  const documents = getDocuments(botId)
  const isLoading = loadingDocuments[botId]
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)
  const [retrying, setRetrying] = useState<string | null>(null)

  useEffect(() => {
    loadDocuments(botId)
  }, [botId, loadDocuments])

  // Poll processing documents
  useEffect(() => {
    const processingDocs = documents.filter((d) => d.status === 'processing')
    if (processingDocs.length === 0) return

    const interval = setInterval(() => {
      processingDocs.forEach((doc) => {
        refreshDocument(botId, doc.id)
      })
    }, 3000)

    return () => clearInterval(interval)
  }, [botId, documents, refreshDocument])

  const handleDelete = async (documentId: string) => {
    await deleteDocument(botId, documentId)
    setConfirmingDelete(null)
  }

  const handleRetry = async (documentId: string) => {
    setRetrying(documentId)
    try {
      await retryDocument(botId, documentId)
    } finally {
      setRetrying(null)
    }
  }

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--color-text-secondary)]">
        <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No documents uploaded yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div key={doc.id}>
          <div className="flex items-center gap-3 p-3 bg-[var(--card-bg)] rounded-lg">
            <FileText className="h-5 w-5 text-[var(--color-text-secondary)] flex-shrink-0" />

            <div
              className={`flex-1 min-w-0 ${doc.status === 'ready' && onViewChunks ? 'cursor-pointer hover:opacity-80' : ''}`}
              onClick={() => {
                if (doc.status === 'ready' && onViewChunks) {
                  onViewChunks(doc.id, doc.filename)
                }
              }}
            >
              <p className="text-sm text-[var(--color-text-primary)] truncate">{doc.filename}</p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {formatSize(doc.file_size)}
                {doc.chunk_count > 0 && ` - ${doc.chunk_count} chunks`}
                {' - '}
                {formatDate(doc.uploaded_at)}
              </p>
            </div>

            <StatusIcon status={doc.status} />

            {/* View chunks button for ready documents */}
            {doc.status === 'ready' && onViewChunks && (
              <button
                onClick={() => onViewChunks(doc.id, doc.filename)}
                className="p-1.5 rounded hover:bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
                title="View chunks"
              >
                <Eye className="h-4 w-4" />
              </button>
            )}

            {/* Retry button for failed documents */}
            {doc.status === 'failed' && (
              <button
                onClick={() => handleRetry(doc.id)}
                disabled={retrying === doc.id}
                className="p-1.5 rounded hover:bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)] hover:text-yellow-400 transition-colors disabled:opacity-50"
                title="Retry processing"
              >
                <RotateCcw className={`h-4 w-4 ${retrying === doc.id ? 'animate-spin' : ''}`} />
              </button>
            )}

            {/* Delete button */}
            <button
              onClick={() => setConfirmingDelete(doc.id)}
              className="p-1.5 rounded hover:bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)] hover:text-red-400 transition-colors"
              title="Delete document"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          {/* Inline delete confirmation */}
          {confirmingDelete === doc.id && (
            <div className="flex items-center gap-2 mt-1 ml-8 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
              <span className="text-xs text-red-400 flex-1">Delete "{doc.filename}"?</span>
              <button
                onClick={() => handleDelete(doc.id)}
                className="px-2 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-500"
              >
                Delete
              </button>
              <button
                onClick={() => setConfirmingDelete(null)}
                className="px-2 py-1 text-xs rounded border border-[var(--color-border-secondary)] text-[var(--color-text-primary)] hover:bg-[var(--color-hover-bg)]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
