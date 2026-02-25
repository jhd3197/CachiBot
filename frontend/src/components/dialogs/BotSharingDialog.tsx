import { useState, useEffect } from 'react'
import { Share2, X, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../common/Button'
import {
  getBotAccess,
  shareBotWithGroup,
  updateBotAccess,
  revokeBotAccess,
  listGroups,
} from '../../api/groups'
import type { BotAccessRecord, BotAccessLevel, Group } from '../../types'

interface BotSharingDialogProps {
  botId: string
  botName: string
  open: boolean
  onClose: () => void
}

export function BotSharingDialog({ botId, botName, open, onClose }: BotSharingDialogProps) {
  const [records, setRecords] = useState<BotAccessRecord[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)

  // Share form
  const [selectedGroupId, setSelectedGroupId] = useState('')
  const [selectedLevel, setSelectedLevel] = useState<BotAccessLevel>('viewer')
  const [sharing, setSharing] = useState(false)

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open, botId])

  const loadData = async () => {
    setLoading(true)
    try {
      const [accessRecords, availableGroups] = await Promise.all([
        getBotAccess(botId),
        listGroups(),
      ])
      setRecords(accessRecords)
      setGroups(availableGroups)
    } catch {
      toast.error('Failed to load sharing data')
    } finally {
      setLoading(false)
    }
  }

  const handleShare = async () => {
    if (!selectedGroupId) {
      toast.error('Select a group')
      return
    }

    setSharing(true)
    try {
      const record = await shareBotWithGroup(botId, {
        group_id: selectedGroupId,
        access_level: selectedLevel,
      })
      setRecords([...records, record])
      setSelectedGroupId('')
      setSelectedLevel('viewer')
      toast.success('Bot shared with group')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to share bot'
      toast.error(message)
    } finally {
      setSharing(false)
    }
  }

  const handleUpdateLevel = async (groupId: string, level: BotAccessLevel) => {
    try {
      await updateBotAccess(botId, groupId, { access_level: level })
      setRecords(
        records.map((r) =>
          r.group_id === groupId ? { ...r, access_level: level } : r,
        ),
      )
      toast.success('Access level updated')
    } catch {
      toast.error('Failed to update access level')
    }
  }

  const handleRevoke = async (groupId: string, groupName: string | null) => {
    if (!confirm(`Revoke access for group "${groupName || groupId}"?`)) return

    try {
      await revokeBotAccess(botId, groupId)
      setRecords(records.filter((r) => r.group_id !== groupId))
      toast.success('Access revoked')
    } catch {
      toast.error('Failed to revoke access')
    }
  }

  if (!open) return null

  // Groups not already shared with
  const sharedGroupIds = new Set(records.map((r) => r.group_id))
  const availableGroups = groups.filter((g) => !sharedGroupIds.has(g.id))

  const levelColors: Record<BotAccessLevel, string> = {
    viewer: 'bg-blue-500/20 text-blue-300',
    operator: 'bg-amber-500/20 text-amber-300',
    editor: 'bg-green-500/20 text-green-300',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-[var(--color-bg-dialog)] rounded-xl border border-[var(--color-border-primary)] w-full max-w-lg mx-4 max-h-[80vh] flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-primary)]">
          <div className="flex items-center gap-2">
            <Share2 className="h-5 w-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Share "{botName}"</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-[var(--color-hover-bg)] rounded-lg transition-colors text-[var(--color-text-secondary)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-secondary)]" />
            </div>
          ) : (
            <>
              {/* Share with group form */}
              {availableGroups.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-[var(--color-text-primary)]">Share with group</h3>
                  <div className="flex gap-2">
                    <select
                      value={selectedGroupId}
                      onChange={(e) => setSelectedGroupId(e.target.value)}
                      className="flex-1 px-3 py-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border-secondary)] rounded-lg text-[var(--color-text-primary)] text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select a group...</option>
                      {availableGroups.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name} ({g.member_count} members)
                        </option>
                      ))}
                    </select>
                    <select
                      value={selectedLevel}
                      onChange={(e) => setSelectedLevel(e.target.value as BotAccessLevel)}
                      className="w-28 px-3 py-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border-secondary)] rounded-lg text-[var(--color-text-primary)] text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="viewer">Viewer</option>
                      <option value="operator">Operator</option>
                      <option value="editor">Editor</option>
                    </select>
                    <Button onClick={handleShare} disabled={sharing || !selectedGroupId}>
                      {sharing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Share'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Current access records */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-[var(--color-text-primary)]">
                  Current access ({records.length})
                </h3>
                {records.length === 0 ? (
                  <p className="text-sm text-[var(--color-text-secondary)] py-4 text-center">
                    Not shared with any groups yet
                  </p>
                ) : (
                  <div className="space-y-2">
                    {records.map((record) => (
                      <div
                        key={record.id}
                        className="flex items-center justify-between px-3 py-2.5 bg-[var(--card-bg)] rounded-lg border border-[var(--color-border-primary)]"
                      >
                        <div>
                          <div className="text-sm font-medium text-[var(--color-text-primary)]">
                            {record.group_name || record.group_id}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <select
                            value={record.access_level}
                            onChange={(e) =>
                              handleUpdateLevel(
                                record.group_id,
                                e.target.value as BotAccessLevel,
                              )
                            }
                            className={`px-2 py-1 rounded text-xs font-medium border-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 ${levelColors[record.access_level]}`}
                          >
                            <option value="viewer">Viewer</option>
                            <option value="operator">Operator</option>
                            <option value="editor">Editor</option>
                          </select>
                          <button
                            onClick={() => handleRevoke(record.group_id, record.group_name)}
                            className="p-1 text-[var(--color-text-secondary)] hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Access level legend */}
              <div className="space-y-2 pt-2 border-t border-[var(--color-border-primary)]">
                <h4 className="text-xs font-medium text-[var(--color-text-secondary)] uppercase">Access Levels</h4>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="text-[var(--color-text-secondary)]">
                    <span className={`inline-block px-1.5 py-0.5 rounded ${levelColors.viewer} mr-1`}>
                      Viewer
                    </span>
                    Read-only
                  </div>
                  <div className="text-[var(--color-text-secondary)]">
                    <span className={`inline-block px-1.5 py-0.5 rounded ${levelColors.operator} mr-1`}>
                      Operator
                    </span>
                    Chat & run
                  </div>
                  <div className="text-[var(--color-text-secondary)]">
                    <span className={`inline-block px-1.5 py-0.5 rounded ${levelColors.editor} mr-1`}>
                      Editor
                    </span>
                    Full config
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--color-border-primary)]">
          <Button variant="ghost" onClick={onClose} className="w-full">
            Done
          </Button>
        </div>
      </div>
    </div>
  )
}
