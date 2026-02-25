import { useEffect, useState, useCallback, useRef } from 'react'
import { Upload, Download, Trash2, File, Image, FileText, Film, Music, Archive } from 'lucide-react'
import { getRoomAssets, uploadRoomAsset, downloadRoomAsset, deleteRoomAsset } from '../../api/assets'
import { getChatAssets, uploadChatAsset, downloadChatAsset, deleteChatAsset } from '../../api/assets'
import { useRoomStore } from '../../stores/rooms'
import { useChatAssetStore } from '../../stores/chat-assets'
import type { Asset, AssetOwnerType } from '../../types'

interface AssetsViewProps {
  ownerType: AssetOwnerType
  ownerId: string
  botId?: string
}

function getFileIcon(contentType: string) {
  if (contentType.startsWith('image/')) return <Image size={16} />
  if (contentType.startsWith('video/')) return <Film size={16} />
  if (contentType.startsWith('audio/')) return <Music size={16} />
  if (contentType.includes('pdf') || contentType.includes('text')) return <FileText size={16} />
  if (contentType.includes('zip') || contentType.includes('tar') || contentType.includes('gz')) return <Archive size={16} />
  return <File size={16} />
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AssetsView({ ownerType, ownerId, botId }: AssetsViewProps) {
  const { roomAssets, setRoomAssets, addRoomAsset, deleteRoomAsset: delRoomAsset } = useRoomStore()
  const { assets: chatAssets, setAssets: setChatAssets, addAsset: addChatAsset, deleteAsset: delChatAsset } = useChatAssetStore()

  const assets = ownerType === 'room'
    ? (roomAssets[ownerId] || [])
    : (chatAssets[ownerId] || [])

  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        let data: Asset[]
        if (ownerType === 'room') {
          data = await getRoomAssets(ownerId)
          if (!cancelled) setRoomAssets(ownerId, data)
        } else {
          data = await getChatAssets(botId || '', ownerId)
          if (!cancelled) setChatAssets(ownerId, data)
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [ownerType, ownerId, botId, setRoomAssets, setChatAssets])

  const handleUpload = useCallback(async (files: FileList | File[]) => {
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        let asset: Asset
        if (ownerType === 'room') {
          asset = await uploadRoomAsset(ownerId, file)
          addRoomAsset(ownerId, asset)
        } else {
          asset = await uploadChatAsset(botId || '', ownerId, file)
          addChatAsset(ownerId, asset)
        }
      }
    } catch {
      // ignore
    } finally {
      setUploading(false)
    }
  }, [ownerType, ownerId, botId, addRoomAsset, addChatAsset])

  const handleDownload = useCallback(async (asset: Asset) => {
    try {
      let blob: Blob
      if (ownerType === 'room') {
        blob = await downloadRoomAsset(ownerId, asset.id)
      } else {
        blob = await downloadChatAsset(botId || '', ownerId, asset.id)
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = asset.originalFilename
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore
    }
  }, [ownerType, ownerId, botId])

  const handleDelete = useCallback(async (assetId: string) => {
    try {
      if (ownerType === 'room') {
        await deleteRoomAsset(ownerId, assetId)
        delRoomAsset(ownerId, assetId)
      } else {
        await deleteChatAsset(botId || '', ownerId, assetId)
        delChatAsset(ownerId, assetId)
      }
    } catch {
      // ignore
    }
  }, [ownerType, ownerId, botId, delRoomAsset, delChatAsset])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files)
    }
  }, [handleUpload])

  return (
    <div className="assets-view">
      <div className="assets-header">
        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          Assets
        </span>
        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
          {assets.length} file{assets.length !== 1 ? 's' : ''}
        </span>
        <div style={{ marginLeft: 'auto' }}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
          <button
            className="btn btn--primary btn--sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
          >
            <Upload size={14} />
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </div>

      {/* Drop zone */}
      <div
        className={`assets-upload-zone ${dragOver ? 'assets-upload-zone--active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload size={20} style={{ color: 'var(--color-text-tertiary)' }} />
        <span>Drop files here or click to upload</span>
      </div>

      {/* File list */}
      {loading ? (
        <div className="tasks-empty">Loading assets...</div>
      ) : assets.length === 0 ? (
        <div className="tasks-empty">No assets yet</div>
      ) : (
        <div className="asset-list">
          {assets.map((asset) => (
            <div key={asset.id} className="asset-item">
              <div className="asset-item__icon">
                {asset.contentType.startsWith('image/') ? (
                  <div className="asset-item__thumbnail">
                    <Image size={20} />
                  </div>
                ) : (
                  getFileIcon(asset.contentType)
                )}
              </div>
              <div className="asset-item__name">
                <span title={asset.originalFilename}>{asset.name}</span>
              </div>
              <div className="asset-item__meta">
                <span>{formatSize(asset.sizeBytes)}</span>
                <span>{new Date(asset.createdAt).toLocaleDateString()}</span>
              </div>
              <div className="asset-item__actions">
                <button onClick={() => handleDownload(asset)} title="Download">
                  <Download size={14} />
                </button>
                <button onClick={() => handleDelete(asset.id)} title="Delete">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
