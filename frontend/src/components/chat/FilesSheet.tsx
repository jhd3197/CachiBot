import { useEffect, useMemo, useRef, useState } from 'react'
import { X, Upload, Trash2, Folder, ChevronLeft } from 'lucide-react'
import { toast } from 'sonner'
import { getBotAssets, downloadChatAsset, getRoomAssets, uploadRoomAsset, downloadRoomAsset, deleteRoomAsset } from '../../api/assets'
import { getComputerWorkspace } from '../../api/computer'
import { getBotChats } from '../../api/client'
import { useChatStore } from '../../stores/bots'
import { useArtifactsStore } from '../../stores/artifacts'
import { useComputerStore } from '../../stores/computer'
import { useBotAccess } from '../../hooks/useBotAccess'
import { parseApiDate } from '../../lib/utils'
import { cn } from '../../lib/utils'
import type { Artifact, Asset, Bot, ComputerWorkspaceEntry } from '../../types'

interface FilesSheetProps {
  /** Bot scope (chat header): files from all of the bot's chats known to
   * the app (its backend chat list plus this browser's local chats). */
  bot?: Bot
  /** Room scope (room header): the room's shared files. */
  roomId?: string
  roomTitle?: string
  onClose: () => void
}

type SheetFilter = 'all' | 'bot' | 'user'

interface SheetItem {
  key: string
  /** Asset id (room rows can be deleted). */
  assetId?: string
  /** Sort key: epoch ms; undated items (artifacts) get -1 and sink last. */
  sortTime: number
  name: string
  /** Tile label — the file extension (HTML/CSS/PNG) or artifact type. */
  tile: string
  /** "date · size" from real metadata only; null when neither exists. */
  meta: string | null
  origin: 'bot' | 'user' | 'unknown'
  action:
    | { kind: 'download'; run: () => Promise<void> }
    | { kind: 'artifact'; artifactId: string }
}

// Cap for the chat-id list used to scope artifacts to this bot's chats.
const MAX_CHATS = 100

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${trimZero((bytes / 1024).toFixed(1))} KB`
  return `${trimZero((bytes / (1024 * 1024)).toFixed(1))} MB`
}

function trimZero(s: string): string {
  return s.replace(/\.0$/, '')
}

/** "Today" / "Yesterday" / weekday short within the week / "Nov 17". */
function dayLabel(date: Date): string {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const today = startOfDay(new Date())
  const day = startOfDay(date)
  if (day === today) return 'Today'
  if (day === today - 86400000) return 'Yesterday'
  if (day > today - 6 * 86400000) return date.toLocaleDateString([], { weekday: 'short' })
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function tileLabel(name: string, fallback = 'FILE'): string {
  const ext = name.includes('.') ? name.split('.').pop()!.trim() : ''
  if (!ext) return fallback
  return ext.slice(0, 4).toUpperCase()
}

function assetOrigin(asset: Asset): SheetItem['origin'] {
  if (asset.uploadedByBotId) return 'bot'
  if (asset.uploadedByUserId) return 'user'
  return 'unknown'
}

/**
 * Files sheet (design view 10): "What <Bot> made or you sent". Rows are chat
 * assets (uploaded by you or captured from files the bot wrote) and artifacts
 * the bot produced in this bot's chats (Open → the artifact panel). Real
 * metadata only — no date/size is invented when the source lacks it.
 */
export function FilesSheet({ bot, roomId, roomTitle, onClose }: FilesSheetProps) {
  const [items, setItems] = useState<SheetItem[] | null>(null)
  const [error, setError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [filter, setFilter] = useState<SheetFilter>('all')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // "On its computer": the bot's /workspace, listed live from the computer
  // (C4). Shown only while the computer feature is available AND the bot's
  // computer is awake; browsing never wakes it — asleep just hides this.
  const computerAvailable = useComputerStore((s) => s.status?.available === true)
  const computerState = useComputerStore((s) => (bot ? s.byBot[bot.id]?.state : undefined))
  const { canOperate } = useBotAccess(bot?.id ?? null)
  const [wsPath, setWsPath] = useState('')
  const [wsEntries, setWsEntries] = useState<ComputerWorkspaceEntry[] | null>(null)

  const computerLive = computerState === 'awake' || computerState === 'needs_you'

  useEffect(() => {
    if (!bot || roomId || !computerAvailable || !computerLive) {
      setWsEntries(null)
      return
    }
    let cancelled = false
    getComputerWorkspace(bot.id, wsPath)
      .then((res) => {
        if (!cancelled) setWsEntries(res.entries)
      })
      .catch(() => {
        if (!cancelled) setWsEntries(null)
      })
    return () => {
      cancelled = true
    }
  }, [bot, roomId, computerAvailable, computerLive, wsPath])

  useEffect(() => {
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setItems(null)
      setError(false)
      try {
        if (roomId) {
          const assets = await getRoomAssets(roomId)
          if (cancelled) return
          setItems(assets.map((a) => roomItem(a)))
          return
        }
        if (!bot) return
        // Rows come from one bot-level call; the chat lists are only needed
        // to scope artifacts (which carry a chatId) to this bot's chats.
        const [assets, serverChats, localChats] = await Promise.all([
          getBotAssets(bot.id),
          getBotChats(bot.id, true).catch(() => [] as Awaited<ReturnType<typeof getBotChats>>),
          Promise.resolve(useChatStore.getState().getChatsByBot(bot.id)),
        ])
        const byId = new Map<string, string>()
        for (const c of [...serverChats, ...localChats]) {
          if (!byId.has(c.id)) byId.set(c.id, c.updatedAt)
        }
        const chatIds = [...byId.entries()]
          .sort((a, b) => new Date(b[1]).getTime() - new Date(a[1]).getTime())
          .slice(0, MAX_CHATS)
          .map(([id]) => id)

        // Artifacts the bot produced in these chats (deduped against the
        // assets that already back them — document artifacts carry assetId).
        const chatIdSet = new Set(chatIds)
        const assetIds = new Set(assets.map((a) => a.id))
        const assetNames = new Map<string, Set<string>>()
        for (const a of assets) {
          const s = assetNames.get(a.ownerId) ?? new Set<string>()
          s.add(a.name.toLowerCase())
          assetNames.set(a.ownerId, s)
        }
        const artifacts = Object.values(useArtifactsStore.getState().artifacts).filter((a) => {
          if (!a.chatId || !chatIdSet.has(a.chatId)) return false
          const backing = a.metadata?.assetId
          if (typeof backing === 'string' && assetIds.has(backing)) return false
          if (assetNames.get(a.chatId)?.has(a.title.toLowerCase())) return false
          return true
        })

        const sheetItems: SheetItem[] = [
          ...assets.map((a) => botAssetItem(bot, a)),
          ...artifacts.map((a) => artifactItem(a)),
        ]
        sheetItems.sort((a, b) => b.sortTime - a.sortTime)
        if (cancelled) return
        setItems(sheetItems)
      } catch {
        if (!cancelled) setError(true)
      }
    }
    load()
    return () => { cancelled = true }
  }, [bot, roomId, reloadKey])

  const counts = useMemo(() => {
    const c = { bot: 0, user: 0 }
    for (const item of items ?? []) {
      if (item.origin === 'bot') c.bot += 1
      else if (item.origin === 'user') c.user += 1
    }
    return c
  }, [items])

  // Hide a chip that would always be empty (view 10); fall back to All.
  const showBotChip = counts.bot > 0
  const showUserChip = counts.user > 0
  const effectiveFilter =
    (filter === 'bot' && !showBotChip) || (filter === 'user' && !showUserChip) ? 'all' : filter

  const visible = useMemo(
    () => (items ?? []).filter((i) => effectiveFilter === 'all' || i.origin === effectiveFilter),
    [items, effectiveFilter]
  )

  const handleUpload = async (files: FileList | File[]) => {
    if (!roomId) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        const asset = await uploadRoomAsset(roomId, file)
        setItems((prev) => (prev ? [roomItem(asset), ...prev] : [roomItem(asset)]))
      }
    } catch {
      toast.error('Failed to upload file')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (assetId: string) => {
    if (!roomId) return
    try {
      await deleteRoomAsset(roomId, assetId)
      setItems((prev) => prev?.filter((i) => i.assetId !== assetId) ?? null)
    } catch {
      toast.error('Failed to delete file')
    }
  }

  const title = 'Files'
  const subtitle = roomId
    ? `Files shared in ${roomTitle || 'this room'}`
    : `What ${bot?.name ?? 'the bot'} made or you sent`

  return (
    <div className="v2-files-backdrop" onClick={onClose}>
      <section
        className="v2-files"
        role="dialog"
        aria-modal="true"
        aria-label="Files"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="v2-files__header">
          <h2>{title}</h2>
          <span className="v2-files__subtitle">{subtitle}</span>
          <span className="v2-files__header-actions">
            {roomId && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(e) => e.target.files && handleUpload(e.target.files)}
                />
                <button
                  type="button"
                  className="v2-btn v2-btn--secondary v2-files__upload"
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={14} strokeWidth={1.8} />
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
              </>
            )}
            <button type="button" className="v2-icon-btn" aria-label="Close" title="Close" onClick={onClose}>
              <X size={16} strokeWidth={1.8} />
            </button>
          </span>
        </div>

        {!error && items !== null && items.length > 0 && (
          <div className="v2-files__chips" role="group" aria-label="Filter files">
            <FilterChip active={effectiveFilter === 'all'} onClick={() => setFilter('all')}>
              All
            </FilterChip>
            {showBotChip && (
              <FilterChip active={effectiveFilter === 'bot'} onClick={() => setFilter('bot')}>
                {roomId ? 'Made by bots' : `Made by ${bot?.name ?? 'the bot'}`}
              </FilterChip>
            )}
            {showUserChip && (
              <FilterChip active={effectiveFilter === 'user'} onClick={() => setFilter('user')}>
                Sent by you
              </FilterChip>
            )}
          </div>
        )}

        <div className="v2-files__list">
          {items === null && !error && <div className="v2-files__empty">Loading files…</div>}
          {error && (
            <div className="v2-files__empty">
              Couldn’t load files.{' '}
              <button type="button" className="v2-files__action" onClick={() => setReloadKey((k) => k + 1)}>
                Try again
              </button>
            </div>
          )}
          {items !== null && !error && visible.length === 0 && (
            <div className="v2-files__empty">No files yet.</div>
          )}
          {visible.map((item) => (
            <div key={item.key} className="v2-files__row">
              <span className="v2-files__tile" aria-hidden="true">
                {item.tile}
              </span>
              <span className="v2-files__main">
                <span className="v2-files__name" title={item.name}>
                  {item.name}
                </span>
                {item.meta && <span className="v2-files__meta">{item.meta}</span>}
              </span>
              {roomId && item.action.kind === 'download' && (
                <button
                  type="button"
                  className="v2-files__delete"
                  aria-label={`Delete ${item.name}`}
                  title="Delete"
                  onClick={() => item.assetId && void handleDelete(item.assetId)}
                >
                  <Trash2 size={14} strokeWidth={1.8} />
                </button>
              )}
              <button
                type="button"
                className="v2-files__action"
                onClick={() => {
                  if (item.action.kind === 'artifact') {
                    onClose()
                    useArtifactsStore.getState().setActive(item.action.artifactId)
                  } else {
                    void item.action.run()
                  }
                }}
              >
                {item.action.kind === 'artifact' ? 'Open' : 'Download'}
              </button>
            </div>
          ))}
        </div>

        {/* The bot's /workspace on its computer (design 10 "Open on
            computer"). Real listing from the computer; hidden entirely when
            the computer is off/asleep or the feature is unavailable. */}
        {wsEntries !== null && bot && (
          <div className="v2-files__workspace">
            <div className="v2-files__workspace-head">
              <h3>On its computer</h3>
              {wsPath && (
                <button
                  type="button"
                  className="v2-files__action v2-files__workspace-up"
                  onClick={() => setWsPath(wsPath.split('/').slice(0, -1).join('/'))}
                >
                  <ChevronLeft size={13} strokeWidth={1.8} />
                  Back
                </button>
              )}
            </div>
            {wsPath && <p className="v2-files__workspace-path">/{wsPath}</p>}
            {wsEntries.length === 0 ? (
              <p className="v2-files__empty">No files here yet.</p>
            ) : (
              wsEntries.map((entry) => (
                <div key={`${entry.kind}:${entry.path}`} className="v2-files__row">
                  <span className="v2-files__tile" aria-hidden="true">
                    {entry.kind === 'folder' ? <Folder size={14} strokeWidth={1.8} /> : tileLabel(entry.name)}
                  </span>
                  <span className="v2-files__main">
                    <span className="v2-files__name" title={entry.name}>
                      {entry.name}
                    </span>
                    {entry.size !== null && (
                      <span className="v2-files__meta">{formatBytes(entry.size)}</span>
                    )}
                  </span>
                  {entry.kind === 'folder' ? (
                    <button
                      type="button"
                      className="v2-files__action"
                      onClick={() => setWsPath(entry.path)}
                    >
                      Open
                    </button>
                  ) : (
                    canOperate && (
                      <button
                        type="button"
                        className="v2-files__action"
                        onClick={() =>
                          void useComputerStore
                            .getState()
                            .openEditor(bot.id, entry.path)
                            .then(() => toast.success(`Opened ${entry.name} on its computer`))
                            .catch((err) =>
                              toast.error(err instanceof Error ? err.message : 'Could not open it')
                            )
                        }
                      >
                        Open on computer
                      </button>
                    )
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      className={cn('v2-files__chip', active && 'v2-files__chip--active')}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function metaOf(date: Date | null, size: number | null): string | null {
  const parts: string[] = []
  if (date) parts.push(dayLabel(date))
  if (size !== null) parts.push(formatBytes(size))
  return parts.length > 0 ? parts.join(' · ') : null
}

function botAssetItem(bot: Bot, asset: Asset): SheetItem {
  const date = asset.createdAt ? parseApiDate(asset.createdAt) : null
  return {
    key: `chat:${asset.id}`,
    assetId: asset.id,
    sortTime: date?.getTime() ?? -1,
    name: asset.name,
    tile: tileLabel(asset.name),
    meta: metaOf(date, asset.sizeBytes),
    origin: assetOrigin(asset),
    action: {
      kind: 'download',
      run: async () => {
        const blob = await downloadChatAsset(bot.id, asset.ownerId, asset.id)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = asset.originalFilename || asset.name
        a.click()
        URL.revokeObjectURL(url)
      },
    },
  }
}

function artifactItem(artifact: Artifact): SheetItem {
  const fileSize = artifact.metadata?.fileSize
  return {
    key: `artifact:${artifact.id}`,
    sortTime: -1,
    name: artifact.title,
    tile: tileLabel(artifact.title, artifact.type.toUpperCase().slice(0, 4)),
    // Artifacts carry no timestamp; size only when the emitter provided one.
    meta: metaOf(null, typeof fileSize === 'number' ? fileSize : null),
    origin: 'bot',
    action: { kind: 'artifact', artifactId: artifact.id },
  }
}

function roomItem(asset: Asset): SheetItem {
  const date = asset.createdAt ? parseApiDate(asset.createdAt) : null
  return {
    key: `room:${asset.id}`,
    assetId: asset.id,
    sortTime: date?.getTime() ?? -1,
    name: asset.name,
    tile: tileLabel(asset.name),
    meta: metaOf(date, asset.sizeBytes),
    origin: assetOrigin(asset),
    action: {
      kind: 'download',
      run: async () => {
        const blob = await downloadRoomAsset(asset.ownerId, asset.id)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = asset.originalFilename || asset.name
        a.click()
        URL.revokeObjectURL(url)
      },
    },
  }
}
