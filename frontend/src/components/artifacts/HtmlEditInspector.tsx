/**
 * HtmlEditInspector — the side panel for HTML click-to-edit mode.
 *
 * Every control acts on the real selected element: values are read from the
 * clean artifact source (via the useHtmlEdit selection) and committed as
 * typed htmlstudio patches. Text-style inputs keep a local draft and commit
 * on Enter/blur (Escape reverts); the color swatch commits debounced because
 * the native picker fires continuously while dragging.
 */

import { useEffect, useId, useRef, useState } from 'react'
import { AlignCenter, AlignLeft, AlignRight, Bold, Redo2, Undo2 } from 'lucide-react'
import type { Patch } from 'htmlstudio'
import { cn } from '../../lib/utils'
import { isBoldFontWeight, isValidCssValue, toHexColor } from '../../lib/htmlEdit'
import type { HtmlEditSaveStatus, HtmlEditSelection } from '../../hooks/useHtmlEdit'

interface HtmlEditInspectorProps {
  selection: HtmlEditSelection | null
  error: string | null
  saveStatus: HtmlEditSaveStatus
  canUndo: boolean
  canRedo: boolean
  onPatch: (patch: Patch) => boolean
  onUndo: () => void
  onRedo: () => void
  onDone: () => void
}

const ALIGN_OPTIONS = [
  { value: 'left', label: 'Align left', Icon: AlignLeft },
  { value: 'center', label: 'Align center', Icon: AlignCenter },
  { value: 'right', label: 'Align right', Icon: AlignRight },
] as const

export function HtmlEditInspector({
  selection,
  error,
  saveStatus,
  canUndo,
  canRedo,
  onPatch,
  onUndo,
  onRedo,
  onDone,
}: HtmlEditInspectorProps) {
  return (
    <aside className="html-edit" aria-label="Edit element">
      <div className="html-edit__head">
        <span className="html-edit__title">Edit element</span>
        <div className="html-edit__history">
          <button
            type="button"
            className="html-edit__icon-btn"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo"
          >
            <Undo2 className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            className="html-edit__icon-btn"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo"
          >
            <Redo2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {selection ? (
        <div className="html-edit__body">
          <div
            className="html-edit__crumb"
            title={[...selection.breadcrumb, selection.tag].join(' > ')}
          >
            {selection.breadcrumb.map((tag, i) => (
              <span key={i} className="html-edit__crumb-ancestor">
                {tag}
              </span>
            ))}
            <span className="html-edit__crumb-current">{selection.tag}</span>
          </div>

          {selection.kind === 'text' && (
            <DraftField
              label="Text"
              value={selection.text}
              multiline
              onCommit={(value) => onPatch({ kind: 'set-text', id: selection.id, value })}
            />
          )}

          {selection.kind === 'link' && (
            <>
              <DraftField
                label="Text"
                value={selection.text}
                onCommit={(value) =>
                  onPatch({ kind: 'set-link', id: selection.id, href: selection.href, text: value })
                }
              />
              <DraftField
                label="Link URL"
                value={selection.href}
                placeholder="https://…"
                onCommit={(value) =>
                  onPatch({ kind: 'set-link', id: selection.id, href: value.trim(), text: selection.text })
                }
              />
            </>
          )}

          {selection.kind === 'image' && (
            <>
              <DraftField
                label="Image URL"
                value={selection.src}
                placeholder="https://…"
                onCommit={(value) =>
                  onPatch({ kind: 'set-image', id: selection.id, src: value.trim(), alt: selection.alt })
                }
              />
              <DraftField
                label="Alt text"
                value={selection.alt}
                onCommit={(value) =>
                  onPatch({ kind: 'set-image', id: selection.id, src: selection.src, alt: value })
                }
              />
            </>
          )}

          {selection.kind !== 'image' && (
            <div className="html-edit__styles">
              <ColorField
                label="Color"
                value={selection.color}
                onCommit={(value) => onPatch({ kind: 'set-style', id: selection.id, styles: { color: value } })}
              />
              <ColorField
                label="Background"
                value={selection.backgroundColor}
                onCommit={(value) =>
                  onPatch({ kind: 'set-style', id: selection.id, styles: { 'background-color': value } })
                }
              />
              <DraftField
                label="Font size"
                value={selection.fontSize}
                placeholder="e.g. 18px"
                validate={(value) => isValidCssValue('font-size', value)}
                invalidHint="Not a valid CSS size"
                onCommit={(value) =>
                  onPatch({ kind: 'set-style', id: selection.id, styles: { 'font-size': value.trim() } })
                }
              />
              <div className="html-edit__field">
                <span className="html-edit__label">Style</span>
                <div className="html-edit__tools">
                  <button
                    type="button"
                    className={cn('html-edit__tool', isBoldFontWeight(selection.fontWeight) && 'html-edit__tool--active')}
                    aria-pressed={isBoldFontWeight(selection.fontWeight)}
                    title="Bold"
                    onClick={() =>
                      onPatch({
                        kind: 'set-style',
                        id: selection.id,
                        styles: { 'font-weight': isBoldFontWeight(selection.fontWeight) ? '' : 'bold' },
                      })
                    }
                  >
                    <Bold className="h-3.5 w-3.5" />
                  </button>
                  {ALIGN_OPTIONS.map(({ value, label, Icon }) => (
                    <button
                      key={value}
                      type="button"
                      className={cn('html-edit__tool', selection.textAlign === value && 'html-edit__tool--active')}
                      aria-pressed={selection.textAlign === value}
                      title={label}
                      onClick={() =>
                        onPatch({
                          kind: 'set-style',
                          id: selection.id,
                          styles: { 'text-align': selection.textAlign === value ? '' : value },
                        })
                      }
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {error ? (
            <p className="html-edit__error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="html-edit__empty">Click an element in the preview to edit it</p>
      )}

      <div className="html-edit__foot">
        {saveStatus !== 'idle' && (
          <span className={cn('html-edit__status', saveStatus === 'error' && 'html-edit__status--error')}>
            {saveStatus === 'saved' ? 'Saved' : saveStatus === 'saving' ? 'Saving…' : 'Not saved'}
          </span>
        )}
        <button type="button" className="v2-btn v2-btn--secondary" onClick={onDone}>
          Done
        </button>
      </div>
    </aside>
  )
}

// -----------------------------------------------------------------------------
// Draft-commit fields (local — every commit maps to one patch)
// -----------------------------------------------------------------------------

interface DraftFieldProps {
  label: string
  value: string
  placeholder?: string
  multiline?: boolean
  validate?: (value: string) => boolean
  invalidHint?: string
  onCommit: (value: string) => void
}

function DraftField({ label, value, placeholder, multiline, validate, invalidHint, onCommit }: DraftFieldProps) {
  const [draft, setDraft] = useState(value)
  const [invalid, setInvalid] = useState(false)
  const inputId = useId()

  // Re-sync when the stored value changes (new selection, undo/redo).
  useEffect(() => {
    setDraft(value)
    setInvalid(false)
  }, [value])

  const commit = () => {
    if (draft === value) return
    if (validate && draft.trim() !== '' && !validate(draft.trim())) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    onCommit(draft)
  }

  const revert = () => {
    setDraft(value)
    setInvalid(false)
  }

  return (
    <div className="html-edit__field">
      <label className="html-edit__label" htmlFor={inputId}>
        {label}
      </label>
      {multiline ? (
        <textarea
          id={inputId}
          className={cn('html-edit__input', 'html-edit__input--area', invalid && 'html-edit__input--invalid')}
          value={draft}
          placeholder={placeholder}
          rows={3}
          onChange={(e) => {
            setDraft(e.target.value)
            setInvalid(false)
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Escape') revert()
          }}
        />
      ) : (
        <input
          id={inputId}
          className={cn('html-edit__input', invalid && 'html-edit__input--invalid')}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => {
            setDraft(e.target.value)
            setInvalid(false)
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur()
            if (e.key === 'Escape') revert()
          }}
        />
      )}
      {invalid && invalidHint ? <span className="html-edit__hint">{invalidHint}</span> : null}
    </div>
  )
}

interface ColorFieldProps {
  label: string
  value: string
  onCommit: (value: string) => void
}

function ColorField({ label, value, onCommit }: ColorFieldProps) {
  const [draft, setDraft] = useState(value)
  const [invalid, setInvalid] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inputId = useId()

  // Re-sync when the stored value changes — unless a swatch commit is in
  // flight (the picker is mid-drag and owns the draft).
  useEffect(() => {
    if (timerRef.current) return
    setDraft(value)
    setInvalid(false)
  }, [value])

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    },
    []
  )

  const commitText = () => {
    const next = draft.trim()
    if (next === value.trim()) return
    if (next !== '' && !isValidCssValue('color', next)) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    onCommit(next)
  }

  const handleSwatch = (next: string) => {
    setDraft(next)
    setInvalid(false)
    // The native picker fires continuously while dragging — debounce so the
    // preview reloads once per pause, not per pointer move.
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      onCommit(next)
    }, 300)
  }

  return (
    <div className="html-edit__field">
      <label className="html-edit__label" htmlFor={inputId}>
        {label}
      </label>
      <div className="html-edit__color-row">
        <input
          type="color"
          className="html-edit__swatch"
          value={toHexColor(draft) ?? '#000000'}
          onChange={(e) => handleSwatch(e.target.value)}
          title={`${label} picker`}
        />
        <input
          id={inputId}
          className={cn('html-edit__input', invalid && 'html-edit__input--invalid')}
          value={draft}
          placeholder="#rrggbb"
          onChange={(e) => {
            setDraft(e.target.value)
            setInvalid(false)
          }}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur()
            if (e.key === 'Escape') {
              setDraft(value)
              setInvalid(false)
            }
          }}
        />
      </div>
      {invalid ? <span className="html-edit__hint">Not a valid CSS color</span> : null}
    </div>
  )
}
