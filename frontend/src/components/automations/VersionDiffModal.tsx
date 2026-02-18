import { X } from 'lucide-react'

interface VersionDiffModalProps {
  open: boolean
  onClose: () => void
  oldVersion: number
  newVersion: number
  oldCode: string
  newCode: string
}

export function VersionDiffModal({
  open,
  onClose,
  oldVersion,
  newVersion,
  oldCode,
  newCode,
}: VersionDiffModalProps) {
  if (!open) return null

  const oldLines = oldCode.split('\n')
  const newLines = newCode.split('\n')

  return (
    <div className="version-diff">
      <div className="version-diff__panel">
        {/* Header */}
        <div className="version-diff__header">
          <h2 className="version-diff__title">
            Version {oldVersion} vs Version {newVersion}
          </h2>
          <button onClick={onClose} className="btn-close">
            <X size={16} />
          </button>
        </div>

        {/* Diff content - side by side */}
        <div className="version-diff__body">
          {/* Old version */}
          <div className="version-diff__side version-diff__side--old">
            <div className="version-diff__side-header version-diff__side-header--old">
              v{oldVersion}
            </div>
            <pre className="version-diff__code">
              {oldLines.map((line, i) => (
                <div key={i} className="version-diff__line">
                  <span className="version-diff__line-num">{i + 1}</span>
                  <span className="version-diff__line-text">{line}</span>
                </div>
              ))}
            </pre>
          </div>

          {/* New version */}
          <div className="version-diff__side">
            <div className="version-diff__side-header version-diff__side-header--new">
              v{newVersion}
            </div>
            <pre className="version-diff__code">
              {newLines.map((line, i) => (
                <div key={i} className="version-diff__line">
                  <span className="version-diff__line-num">{i + 1}</span>
                  <span className="version-diff__line-text">{line}</span>
                </div>
              ))}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
