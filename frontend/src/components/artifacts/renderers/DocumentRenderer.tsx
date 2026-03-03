/**
 * Document renderer — handles PDF (iframe), PPTX, DOCX, XLSX (download card).
 */

import { Download, FileText, FileSpreadsheet, Presentation } from 'lucide-react'
import type { Artifact } from '../../../types'

interface DocumentRendererProps {
  artifact: Artifact
}

const DOC_TYPE_CONFIG: Record<string, { icon: typeof FileText; label: string }> = {
  pdf: { icon: FileText, label: 'PDF Document' },
  pptx: { icon: Presentation, label: 'PowerPoint Presentation' },
  docx: { icon: FileText, label: 'Word Document' },
  xlsx: { icon: FileSpreadsheet, label: 'Excel Spreadsheet' },
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentRenderer({ artifact }: DocumentRendererProps) {
  const meta = artifact.metadata ?? {}
  const documentType = (meta.documentType as string) ?? ''
  const downloadUrl = (meta.downloadUrl as string) ?? artifact.content
  const fileName = (meta.fileName as string) ?? artifact.title
  const fileSize = (meta.fileSize as number) ?? 0

  // PDF: render in iframe (browsers natively support PDF viewing)
  if (documentType === 'pdf') {
    return (
      <div className="artifact-document artifact-document--pdf">
        <iframe
          className="artifact-document__iframe"
          src={downloadUrl}
          title={fileName}
        />
        <div className="artifact-document__bar">
          <a
            href={downloadUrl}
            download={fileName}
            className="artifact-document__download-btn"
          >
            <Download className="h-3.5 w-3.5" />
            Download PDF
          </a>
        </div>
      </div>
    )
  }

  // PPTX / DOCX / XLSX: download card
  const config = DOC_TYPE_CONFIG[documentType] ?? DOC_TYPE_CONFIG.docx
  const Icon = config.icon

  return (
    <div className="artifact-document artifact-document--card">
      <div className="artifact-document__card-icon">
        <Icon className="h-8 w-8" />
      </div>
      <div className="artifact-document__card-info">
        <span className="artifact-document__card-name">{fileName}</span>
        <span className="artifact-document__card-meta">
          {config.label}
          {fileSize > 0 && ` \u00b7 ${formatFileSize(fileSize)}`}
        </span>
      </div>
      <a
        href={downloadUrl}
        download={fileName}
        className="artifact-document__download-btn"
      >
        <Download className="h-4 w-4" />
        Download
      </a>
    </div>
  )
}
