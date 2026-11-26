/**
 * "View changes" for a side task (design 11b/11c): the unified diff between
 * the side task's work and its base — while it runs, what it is about to
 * bring back (worktree vs base, incl. uncommitted changes); once merged, the
 * commit range the latest bring-in added. Renders the real diff from
 * GET /side-tasks/{id}/diff: file list with per-file stats on one side, the
 * selected file's hunks on the other. Binary files are listed without a
 * preview; a cut diff says it was truncated. Mobile: stacked layout with a
 * horizontally scrollable file strip.
 */

import { useEffect, useMemo, useState } from 'react'
import { FileDiff, X } from 'lucide-react'
import { getSideTaskDiff } from '../../api/side-tasks'
import { StatusLine } from '../common/StatusLine'
import { cn } from '../../lib/utils'
import type { SideTaskDiff } from '../../types'

/** Split a unified diff into per-file chunks keyed by path. */
function parseChunks(diff: string): Map<string, string> {
  const chunks = new Map<string, string>()
  const markers = [...diff.matchAll(/^diff --git a\/(.*?) b\/(.*?)$/gm)]
  markers.forEach((marker, index) => {
    const path = marker[2]
    const start = marker.index ?? 0
    const end = index + 1 < markers.length ? (markers[index + 1].index ?? diff.length) : diff.length
    chunks.set(path, diff.slice(start, end))
  })
  return chunks
}

function chunkLineClass(line: string): string {
  if (line.startsWith('+++') || line.startsWith('---')) return 'side-diff__line--meta'
  if (line.startsWith('@@')) return 'side-diff__line--hunk'
  if (line.startsWith('+')) return 'side-diff__line--add'
  if (line.startsWith('-')) return 'side-diff__line--del'
  if (line.startsWith('diff --git') || line.startsWith('index ') || line.startsWith('new file')) {
    return 'side-diff__line--meta'
  }
  return ''
}

const STATUS_LABEL: Record<string, string> = {
  added: 'A',
  modified: 'M',
  deleted: 'D',
}

function shortSha(sha: string | null | undefined): string | null {
  return sha ? sha.slice(0, 7) : null
}

interface SideTaskDiffDialogProps {
  botId: string
  sideTaskId: string
  title: string
  onClose: () => void
}

export function SideTaskDiffDialog({ botId, sideTaskId, title, onClose }: SideTaskDiffDialogProps) {
  const [data, setData] = useState<SideTaskDiff | null>(null)
  const [failed, setFailed] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getSideTaskDiff(botId, sideTaskId)
      .then((diff) => {
        if (cancelled) return
        setData(diff)
        setSelected(diff.files[0]?.path ?? null)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [botId, sideTaskId])

  const chunks = useMemo(() => (data ? parseChunks(data.diff) : new Map<string, string>()), [data])

  const range = data
    ? [shortSha(data.base), shortSha(data.head) ?? 'worktree'].filter(Boolean).join(' → ')
    : ''

  return (
    <div className="side-diff__backdrop" role="presentation" onClick={onClose}>
      <div
        className="side-diff"
        role="dialog"
        aria-label={`Changes for ${title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="side-diff__header">
          <FileDiff size={16} strokeWidth={1.8} className="side-diff__header-icon" />
          <span className="side-diff__title">Changes · {title}</span>
          {range && <span className="side-diff__range">{range}</span>}
          {data?.truncated && <span className="side-diff__truncated">Truncated</span>}
          <button type="button" className="side-diff__close" aria-label="Close" onClick={onClose}>
            <X size={16} strokeWidth={1.8} />
          </button>
        </div>

        {!data && !failed && (
          <StatusLine pending>Loading the changes…</StatusLine>
        )}
        {failed && <p className="v2-status-line">Couldn&apos;t load the changes.</p>}

        {data && data.files.length === 0 && (
          <p className="v2-status-line">No changes to show.</p>
        )}

        {data && data.files.length > 0 && (
          <div className="side-diff__body">
            <div className="side-diff__files" role="listbox" aria-label="Changed files">
              {data.files.map((file) => (
                <button
                  key={file.path}
                  type="button"
                  role="option"
                  aria-selected={selected === file.path}
                  className={cn('side-diff__file', selected === file.path && 'side-diff__file--active')}
                  onClick={() => setSelected(file.path)}
                >
                  <span className={cn('side-diff__file-status', `side-diff__file-status--${file.status}`)}>
                    {STATUS_LABEL[file.status] ?? 'M'}
                  </span>
                  <span className="side-diff__file-path">{file.path}</span>
                  {file.binary ? (
                    <span className="side-diff__file-stats side-diff__file-stats--binary">binary</span>
                  ) : (
                    <span className="side-diff__file-stats">
                      {file.additions !== null && file.additions > 0 && (
                        <span className="side-diff__add">+{file.additions}</span>
                      )}
                      {file.deletions !== null && file.deletions > 0 && (
                        <span className="side-diff__del">−{file.deletions}</span>
                      )}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <div className="side-diff__hunks">
              {data.truncated && (
                <p className="side-diff__truncated-note">
                  The diff is large — showing the first part only.
                </p>
              )}
              {selected &&
                (() => {
                  const file = data.files.find((f) => f.path === selected)
                  if (!file) return null
                  if (file.binary) {
                    return <p className="side-diff__binary-note">Binary file — no preview.</p>
                  }
                  const chunk = chunks.get(selected)
                  if (!chunk) return <p className="side-diff__binary-note">No diff for this file.</p>
                  return (
                    <pre className="side-diff__pre">
                      {chunk.split('\n').map((line, i) => (
                        <span key={i} className={cn('side-diff__line', chunkLineClass(line))}>
                          {line || ' '}
                        </span>
                      ))}
                    </pre>
                  )
                })()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
