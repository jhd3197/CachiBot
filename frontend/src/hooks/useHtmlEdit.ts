/**
 * useHtmlEdit — click-to-edit state for one HTML artifact.
 *
 * While `active`, the hook:
 *   1. builds the edit iframe's srcDoc from the clean artifact source
 *      (tagged + bridge injected — the stored artifact stays untouched),
 *   2. listens for the bridge's postMessage events, accepting only messages
 *      whose `event.source` is exactly the edit iframe's contentWindow,
 *   3. applies typed patches to the clean source and persists every accepted
 *      edit — immediately through the artifacts store (so the iframe stays
 *      responsive) and then through the server-side artifact store, and
 *   4. keeps a bounded undo/redo history of clean source strings.
 *
 * Version policy: server PUTs are the only version bump. The local write
 * keeps `artifact.version` untouched; when the PUT succeeds the response's
 * content + bumped version are adopted into the store (confirmed by reading
 * it back). Server saves are serialized through a one-slot queue that always
 * carries the newest full source, so rapid edits coalesce and Done can await
 * the in-flight save (flushSave). Without an active bot the edit stays
 * local-only and the status says so — a server save is never faked.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import type { Patch } from 'htmlstudio'
import {
  applyHtmlPatch,
  buildEditableDoc,
  getBreadcrumb,
  readEditableFields,
  resolveTargetOrigin,
  type HtmlEditableFields,
} from '../lib/htmlEdit'
import { saveArtifact } from '../api/artifacts'
import { useArtifactsStore } from '../stores/artifacts'
import { useBotStore } from '../stores/bots'
import type { Artifact } from '../types'

const HISTORY_LIMIT = 50

export type HtmlEditSaveStatus = 'idle' | 'saving' | 'saved' | 'error'

export interface HtmlEditSelection extends HtmlEditableFields {
  breadcrumb: string[]
}

export interface HtmlEditApi {
  iframeRef: RefObject<HTMLIFrameElement | null>
  srcDoc: string | null
  selection: HtmlEditSelection | null
  /** Last patch/persist failure, cleared on the next select or successful edit. */
  error: string | null
  saveStatus: HtmlEditSaveStatus
  canUndo: boolean
  canRedo: boolean
  applyEdit: (patch: Patch) => boolean
  undo: () => void
  redo: () => void
  /** On iframe load: restores pre-reload scroll and the selection outline. */
  handlePreviewLoad: () => void
  /**
   * Await the in-flight server save, re-queueing the current source first
   * when it changed since the last PUT. Done calls this before closing.
   */
  flushSave: () => Promise<void>
}

/** One queued server save — always the newest full source for one artifact. */
interface PendingServerSave {
  artifactId: string
  botId: string
  body: {
    content: string
    title?: string
    type?: string
    language?: string
    plugin?: string
    metadata?: Record<string, unknown>
    chatId?: string
    messageId?: string
    version?: number
  }
}

/** Field view + breadcrumb for one element, always derived from the clean source. */
function buildSelection(html: string, id: string): HtmlEditSelection | null {
  const fields = readEditableFields(html, id)
  if (!fields) return null
  return { ...fields, breadcrumb: getBreadcrumb(html, id) }
}

export function useHtmlEdit(artifact: Artifact, active: boolean): HtmlEditApi {
  const [srcDoc, setSrcDoc] = useState<string | null>(null)
  const [selection, setSelection] = useState<HtmlEditSelection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<HtmlEditSaveStatus>('idle')
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  /** Current clean working source while editing (untagged artifact HTML). */
  const sourceRef = useRef('')
  /** Last store content seen — distinguishes our own writes from external ones. */
  const lastStoreContentRef = useRef('')
  const pastRef = useRef<string[]>([])
  const futureRef = useRef<string[]>([])
  const scrollRef = useRef({ x: 0, y: 0 })
  const selectedIdRef = useRef<string | null>(null)
  /** Newest unsent server save — one slot, a newer edit supersedes the older. */
  const pendingPutRef = useRef<PendingServerSave | null>(null)
  /** In-flight drain of the save queue; Done awaits it via flushSave. */
  const drainPromiseRef = useRef<Promise<void> | null>(null)
  /** Last source the server confirmed, per artifact — the flush baseline. */
  const lastServerPutRef = useRef<{ artifactId: string; content: string } | null>(null)
  /** True while the working source holds edits the server has not confirmed. */
  const serverDirtyRef = useRef(false)
  const [targetOrigin] = useState(() => resolveTargetOrigin(window.location.origin))

  useEffect(() => {
    selectedIdRef.current = selection?.id ?? null
  }, [selection])

  // Enter/leave edit mode: (re)build the editable doc and reset edit state.
  useEffect(() => {
    pastRef.current = []
    futureRef.current = []
    scrollRef.current = { x: 0, y: 0 }
    serverDirtyRef.current = false
    setSelection(null)
    setError(null)
    setSaveStatus('idle')
    setCanUndo(false)
    setCanRedo(false)
    if (!active) {
      sourceRef.current = ''
      lastStoreContentRef.current = ''
      setSrcDoc(null)
      return
    }
    // Read from the store (not the prop) so this effect only re-runs when
    // edit mode or the artifact identity changes — never on content writes.
    // The store string is used as-is: the round-trip preserves comments and
    // tree shape, so element ids stay stable without rewriting the artifact
    // on enter (see applyHtmlPatch in lib/htmlEdit).
    const content = useArtifactsStore.getState().getArtifact(artifact.id)?.content ?? ''
    lastStoreContentRef.current = content
    sourceRef.current = content
    setSrcDoc(buildEditableDoc(content, targetOrigin))
  }, [active, artifact.id, targetOrigin])

  // If the content changes underneath us (an agent update raced edit mode),
  // drop local history and re-sync — never patch against stale source. Our
  // own writes land here too but match lastStoreContentRef, so they no-op.
  useEffect(() => {
    if (!active || artifact.content === lastStoreContentRef.current) return
    lastStoreContentRef.current = artifact.content
    sourceRef.current = artifact.content
    pastRef.current = []
    futureRef.current = []
    setCanUndo(false)
    setCanRedo(false)
    setSelection(null)
    setSrcDoc(buildEditableDoc(artifact.content, targetOrigin))
  }, [active, artifact.content, targetOrigin])

  /**
   * Drain the one-slot save queue: PUT the newest pending source, adopt the
   * server's content + bumped version, and keep going while newer edits
   * queued behind. Never rejects — a failed PUT surfaces as the error
   * status and the next queued save (full source) still converges.
   */
  const ensureDrain = useCallback((): Promise<void> => {
    if (drainPromiseRef.current) return drainPromiseRef.current
    const run = (async () => {
      while (pendingPutRef.current) {
        const job = pendingPutRef.current
        pendingPutRef.current = null
        try {
          const saved = await saveArtifact(job.botId, job.artifactId, job.body)
          lastServerPutRef.current = { artifactId: job.artifactId, content: job.body.content }
          const store = useArtifactsStore.getState()
          const local = store.getArtifact(job.artifactId)
          if (local) {
            if (local.content === job.body.content) {
              // Nothing newer landed while the PUT was in flight — adopt the
              // server's content and bumped version wholesale.
              store.updateArtifact(job.artifactId, {
                content: saved.content,
                version: saved.version,
              })
              if (sourceRef.current === job.body.content) serverDirtyRef.current = false
            } else if (saved.version > local.version) {
              // A newer local edit is queued behind this job: take the
              // version only when it does not shrink, content follows.
              store.updateArtifact(job.artifactId, { version: saved.version })
            }
          }
          // Confirm by reading the store back (a missing artifact was
          // cleared locally — the server save still happened).
          const after = useArtifactsStore.getState().getArtifact(job.artifactId)
          const confirmed = after === undefined || after.version >= saved.version
          setSaveStatus(pendingPutRef.current ? 'saving' : confirmed ? 'saved' : 'error')
          if (!confirmed) setError('Could not confirm the save')
        } catch (err) {
          setSaveStatus('error')
          setError(err instanceof Error ? err.message : 'Could not save to the server')
        }
      }
    })().finally(() => {
      drainPromiseRef.current = null
    })
    drainPromiseRef.current = run
    return run
  }, [])

  /**
   * Queue the newest full source for the server. The local store is already
   * written; this is the durable half. Without an active bot the edit stays
   * browser-local and the status says so — a server save is never faked.
   */
  const queueServerSave = useCallback(
    (html: string) => {
      const botId = artifact.botId ?? useBotStore.getState().activeBotId
      if (!botId) {
        setSaveStatus('error')
        setError('No active bot — the edit is saved in this browser only')
        return
      }
      const current = useArtifactsStore.getState().getArtifact(artifact.id)
      pendingPutRef.current = {
        artifactId: artifact.id,
        botId,
        body: {
          content: html,
          title: current?.title,
          type: current?.type,
          language: current?.language,
          plugin: current?.plugin,
          metadata: current?.metadata,
          chatId: current?.chatId,
          messageId: current?.messageId,
          version: current?.version,
        },
      }
      serverDirtyRef.current = true
      setSaveStatus('saving')
      void ensureDrain()
    },
    [artifact.botId, artifact.id, ensureDrain]
  )

  const flushSave = useCallback(async (): Promise<void> => {
    // Done was clicked: if the working source still differs from what the
    // server confirmed (e.g. the last PUT failed), send it again, then wait
    // until every queued save has settled.
    const current = sourceRef.current
    if (serverDirtyRef.current && current) {
      const lastPut = lastServerPutRef.current
      if (!lastPut || lastPut.artifactId !== artifact.id || lastPut.content !== current) {
        queueServerSave(current)
      }
    }
    while (drainPromiseRef.current) {
      await drainPromiseRef.current
    }
  }, [artifact.id, queueServerSave])

  /**
   * Persist one clean source: write through the local store immediately
   * (content only — the server PUT owns the version bump), verify the write
   * by reading it back, queue the server save, rebuild the srcDoc and
   * refresh the selected element's fields from the new source.
   */
  const persist = useCallback(
    (html: string) => {
      useArtifactsStore.getState().updateArtifact(artifact.id, { content: html })
      const persisted = useArtifactsStore.getState().getArtifact(artifact.id)?.content === html
      lastStoreContentRef.current = html
      if (!persisted) {
        setSaveStatus('error')
        setError('Could not save the edit')
      } else {
        queueServerSave(html)
      }
      const win = iframeRef.current?.contentWindow
      if (win) {
        try {
          scrollRef.current = { x: win.scrollX, y: win.scrollY }
        } catch {
          // Opaque origin (file:// desktop) — scroll restore is skipped.
        }
      }
      setSrcDoc(buildEditableDoc(html, targetOrigin))
      setSelection((prev) => (prev ? buildSelection(html, prev.id) : null))
    },
    [artifact.id, queueServerSave, targetOrigin]
  )

  const applyEdit = useCallback(
    (patch: Patch): boolean => {
      const current = sourceRef.current
      const result = applyHtmlPatch(current, patch)
      if (!result.ok) {
        setError(result.error ?? 'The edit could not be applied')
        return false
      }
      if (result.html === current) return true // no-op edit — nothing to save or reload
      pastRef.current = [...pastRef.current.slice(-(HISTORY_LIMIT - 1)), current]
      futureRef.current = []
      setCanUndo(true)
      setCanRedo(false)
      setError(null)
      sourceRef.current = result.html
      persist(result.html)
      return true
    },
    [persist]
  )

  const undo = useCallback(() => {
    const past = pastRef.current
    if (past.length === 0) return
    const previous = past[past.length - 1]
    pastRef.current = past.slice(0, -1)
    futureRef.current = [...futureRef.current, sourceRef.current]
    sourceRef.current = previous
    setCanUndo(pastRef.current.length > 0)
    setCanRedo(true)
    setError(null)
    persist(previous)
  }, [persist])

  const redo = useCallback(() => {
    const future = futureRef.current
    if (future.length === 0) return
    const next = future[future.length - 1]
    futureRef.current = future.slice(0, -1)
    pastRef.current = [...pastRef.current, sourceRef.current]
    sourceRef.current = next
    setCanUndo(true)
    setCanRedo(futureRef.current.length > 0)
    setError(null)
    persist(next)
  }, [persist])

  // Bridge events. Only the edit iframe may drive the editor: the source
  // window must be exactly its contentWindow and, when we post with a real
  // target origin, the event origin must match it.
  useEffect(() => {
    if (!active) return undefined
    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return
      if (targetOrigin !== '*' && event.origin !== targetOrigin) return
      const data = event.data as { channel?: unknown; type?: unknown; payload?: unknown } | null
      if (!data || data.channel !== 've') return
      if (data.type === 'select') {
        const payload = data.payload as { id?: unknown } | null
        const id = payload && typeof payload.id === 'string' ? payload.id : null
        setSelection(id ? buildSelection(sourceRef.current, id) : null)
        setError(null)
      } else if (data.type === 'dblclick-text') {
        // Inline contenteditable edit committed inside the preview.
        const payload = data.payload as { id?: unknown; value?: unknown } | null
        if (payload && typeof payload.id === 'string' && typeof payload.value === 'string') {
          applyEdit({ kind: 'set-text', id: payload.id, value: payload.value })
        }
      }
      // 'ready', 'hover' and 'select-multi' carry nothing the inspector uses.
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [active, targetOrigin, applyEdit])

  const handlePreviewLoad = useCallback(() => {
    const win = iframeRef.current?.contentWindow
    if (!win) return
    const { x, y } = scrollRef.current
    if (x !== 0 || y !== 0) {
      try {
        win.scrollTo(x, y)
      } catch {
        // Opaque origin (file:// desktop) — leave the scroll position alone.
      }
    }
    // The bridge does not persist its outline across reloads — re-apply it
    // for the current selection (ids are stable for structure-keeping edits).
    const id = selectedIdRef.current
    if (id) {
      win.postMessage({ channel: 've', type: 'highlight', payload: { id } }, targetOrigin)
    }
  }, [targetOrigin])

  return {
    iframeRef,
    srcDoc,
    selection,
    error,
    saveStatus,
    canUndo,
    canRedo,
    applyEdit,
    undo,
    redo,
    handlePreviewLoad,
    flushSave,
  }
}
