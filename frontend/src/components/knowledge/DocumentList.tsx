/**
 * Document List Component
 *
 * Displays uploaded documents with status and delete action.
 */

import { useEffect } from 'react'
import { FileText, Trash2, Clock, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { useKnowledgeStore, type DocumentResponse } from '../../stores/knowledge'

interface DocumentListProps {
  botId: string
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

export function DocumentList({ botId }: DocumentListProps) {
  const {
    loadDocuments,
    deleteDocument,
    refreshDocument,
    getDocuments,
    loadingDocuments,
  } = useKnowledgeStore()

  const documents = getDocuments(botId)
  const isLoading = loadingDocuments[botId]

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

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="h-5 w-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500">
        <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No documents uploaded yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg"
        >
          <FileText className="h-5 w-5 text-zinc-400 flex-shrink-0" />

          <div className="flex-1 min-w-0">
            <p className="text-sm text-zinc-200 truncate">{doc.filename}</p>
            <p className="text-xs text-zinc-500">
              {formatSize(doc.file_size)}
              {doc.chunk_count > 0 && ` - ${doc.chunk_count} chunks`}
              {' - '}
              {formatDate(doc.uploaded_at)}
            </p>
          </div>

          <StatusIcon status={doc.status} />

          <button
            onClick={() => deleteDocument(botId, doc.id)}
            className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-red-400 transition-colors"
            title="Delete document"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
