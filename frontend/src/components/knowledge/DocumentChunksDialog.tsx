import { useEffect } from 'react'
import { RefreshCw, FileText } from 'lucide-react'
import { Dialog, DialogHeader, DialogContent } from '../common/Dialog'
import { useKnowledgeStore } from '../../stores/knowledge'

interface DocumentChunksDialogProps {
  botId: string
  documentId: string
  filename: string
  open: boolean
  onClose: () => void
}

export function DocumentChunksDialog({
  botId,
  documentId,
  filename,
  open,
  onClose,
}: DocumentChunksDialogProps) {
  const { documentChunks, loadingChunks, loadDocumentChunks } = useKnowledgeStore()

  const chunks = documentChunks[documentId] ?? []
  const isLoading = loadingChunks[documentId] ?? false

  useEffect(() => {
    if (open && botId && documentId) {
      loadDocumentChunks(botId, documentId)
    }
  }, [open, botId, documentId, loadDocumentChunks])

  return (
    <Dialog open={open} onClose={onClose} size="xl">
      <DialogHeader title={`Chunks: ${filename}`} onClose={onClose} />
      <DialogContent className="max-h-[60vh] overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
            <RefreshCw className="h-6 w-6 animate-spin" />
            <p className="mt-3 text-sm">Loading chunks...</p>
          </div>
        ) : chunks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
            <FileText className="h-8 w-8" />
            <p className="mt-3 text-sm">No chunks found for this document.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {chunks.map((chunk) => (
              <div
                key={chunk.id}
                className="rounded-lg border border-zinc-800 bg-zinc-800/50 p-4"
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="inline-flex items-center rounded-md bg-cachi-600/20 px-2 py-0.5 text-xs font-medium text-cachi-400">
                    #{chunk.chunk_index}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
                  {chunk.content}
                </p>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
