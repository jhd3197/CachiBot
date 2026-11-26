/**
 * useHtmlEdit — click-to-edit state for one HTML artifact.
 *
 * While `active`, the hook:
 *   1. builds the edit iframe's srcDoc from the clean artifact source
 *      (tagged + bridge injected — the stored artifact stays untouched),
 *   2. listens for the bridge's postMessage events, accepting only messages
 *      whose `event.source` is exactly the edit iframe's contentWindow,
 *   3. applies typed patches to the clean source and persists every accepted
 *      edit through the artifacts store, and
 *   4. keeps a bounded undo/redo history of clean source strings.
 *
 * Version policy: manual edits write `content` only and never bump
 * `artifact.version`. The version counter tracks agent/plugin revisions
 * (artifact_update payloads); bumping it locally would fake agent revisions
 * and collide with the next server-sent version. A later agent update
 * replaces content wholesale — that is the documented way edits are lost.
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
import { useArtifactsStore } from '../stores/artifacts'
import type { Artifact } from '../types'

const HISTORY_LIMIT = 50

export type HtmlEditSaveStatus = 'idle' | 'saved' | 'error'

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
  const [targetOrigin] = useState(() => resolveTargetOrigin(window.location.origin))

  useEffect(() => {
    selectedIdRef.current = selection?.id ?? null
  }, [selection])

  // Enter/leave edit mode: (re)build the editable doc and reset edit state.
  useEffect(() => {
    pastRef.current = []
    futureRef.current = []
    scrollRef.current = { x: 0, y: 0 }
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
   * Persist one clean source: write through the store, verify the write by
   * reading it back, rebuild the srcDoc and refresh the selected element's
   * fields from the new source.
   */
  const persist = useCallback(
    (html: string) => {
      useArtifactsStore.getState().updateArtifact(artifact.id, { content: html })
      const persisted = useArtifactsStore.getState().getArtifact(artifact.id)?.content === html
      lastStoreContentRef.current = html
      setSaveStatus(persisted ? 'saved' : 'error')
      if (!persisted) setError('Could not save the edit')
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
    [artifact.id, targetOrigin]
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
  }
}
