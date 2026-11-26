/**
 * Click-to-edit helpers for HTML artifacts — a thin, framework-free wrapper
 * over the `htmlstudio` core (tag → bridge → patch → untag).
 *
 * The untagged HTML string is the single source of truth: the injected
 * bridge script and `data-ve-id` attributes exist only in the edit iframe's
 * srcDoc and are never written back to the artifact. Patches are applied by
 * re-tagging the clean source from scratch — `tagHtml` assigns deterministic
 * positional ids (`p-0-1-…`), so the ids the bridge reports always match the
 * ids produced by tagging the same clean string again.
 */

import { applyPatch, getParent, injectBridge, tagHtml } from 'htmlstudio'
import type { Patch } from 'htmlstudio'

const VE_ID_ATTR = 'data-ve-id'

/**
 * Removes exactly the ids `tagHtml` stamped (`data-ve-id="p-0-1-…"`, either
 * quote style, optional whitespace around `=`), consuming the separating
 * whitespace so no stray gaps remain. Everything else is left byte-for-byte:
 * HTML comments (including Outlook `<!--[if mso]>` conditionals that email
 * templates rely on), the doctype, text and scripts all survive — unlike
 * htmlstudio's untagHtml, which re-parses without comments and drops them.
 *
 * Known limit of the regex approach: it matches anywhere in the string, so
 * content that literally embeds a tagger-shaped `data-ve-id="p-…"` inside
 * another attribute's value or a script string would lose that occurrence
 * too. Constraining the match to `<…>` spans instead would be worse: a `>`
 * inside a quoted attribute value (e.g. `alt="a > b"`) would hide a real
 * stamped id and leak it into the stored artifact, breaking the invariant
 * that ids never reach `artifact.content`. Value-shape note: only
 * tagger-shaped (`p-<n>-<n>…`) ids are removed, so a source-authored
 * `data-ve-id` with any other value is preserved untouched.
 */
const VE_ID_PATTERN = /\s+data-ve-id\s*=\s*(?:"p-\d+(?:-\d+)*"|'p-\d+(?:-\d+)*')/g

export function untag(html: string): string {
  return html.replace(VE_ID_PATTERN, '')
}

export interface HtmlPatchResult {
  ok: boolean
  /** The clean (untagged) source after the patch; the input source on failure. */
  html: string
  error?: string
}

/**
 * postMessage target origin for the preview bridge. Sandboxed/file://
 * contexts (desktop) report the string 'null' — fall back to '*'.
 */
export function resolveTargetOrigin(origin: string): string {
  return origin === 'null' ? '*' : origin
}

/**
 * Build the edit iframe's srcDoc. A full document stays a full document:
 * tagHtml/injectBridge only stamp ids and append the bridge before `</body>`
 * (or at the end of a fragment) — nothing is wrapped or re-rooted. The
 * bridge exists only in this string; the patch pipeline below never sees it,
 * so it can never be saved into the artifact.
 */
export function buildEditableDoc(html: string, targetOrigin: string): string {
  return injectBridge(tagHtml(html), { targetOrigin })
}

/**
 * Apply one typed patch to the clean source. The source is re-tagged so the
 * patch targets the same positional ids the bridge reported; the result is
 * untagged again so the stored artifact stays clean.
 *
 * Id stability: tagHtml parses with comments and its positional walk counts
 * comment nodes (node-html-parser's CommentNode has a truthy rawTagName),
 * while the regex `untag` keeps them — so the tree the next tagHtml sees is
 * shaped exactly like the one the bridge ids came from, and ids stay stable
 * across edits, undo and redo. tagHtml/applyPatch do re-serialize the parse
 * tree, so the first edit normalizes the stored source: attribute values on
 * tagger-stamped (editable) elements become double-quoted, and void-tag
 * closing slashes are dropped (`<br/>` → `<br>`, the parser's default form).
 * Comments, doctype, text and script/style bodies are preserved verbatim,
 * and the serialized form is a fixed point — later edits change nothing but
 * the patched element.
 */
export function applyHtmlPatch(html: string, patch: Patch): HtmlPatchResult {
  const result = applyPatch(tagHtml(html), patch)
  if (!result.ok) return { ok: false, html, error: result.error }
  return { ok: true, html: untag(result.source) }
}

// -----------------------------------------------------------------------------
// Editable fields
// -----------------------------------------------------------------------------

export type HtmlEditableKind = 'text' | 'link' | 'image' | 'container'

/** Inspector-facing view of one selected element, read from the clean source. */
export interface HtmlEditableFields {
  id: string
  tag: string
  kind: HtmlEditableKind
  /** Text content — the editable label for text and link elements. */
  text: string
  href: string
  src: string
  alt: string
  /** Inline-style values ('' when unset). */
  color: string
  backgroundColor: string
  fontSize: string
  fontWeight: string
  textAlign: string
}

/** Mirrors the bridge's kind inference so both sides agree on what is editable. */
function kindOf(el: HTMLElement): HtmlEditableKind {
  const tag = el.tagName.toLowerCase()
  if (tag === 'a') return 'link'
  if (tag === 'img') return 'image'
  return el.children.length > 0 ? 'container' : 'text'
}

/**
 * Read the editable fields for one element straight from the clean source
 * (re-tag → DOMParser), so the inspector always shows what is actually
 * stored — never a value scraped from the live iframe DOM.
 */
export function readEditableFields(html: string, id: string): HtmlEditableFields | null {
  const doc = new DOMParser().parseFromString(tagHtml(html), 'text/html')
  const el = doc.querySelector<HTMLElement>(`[${VE_ID_ATTR}="${CSS.escape(id)}"]`)
  if (!el) return null
  const kind = kindOf(el)
  return {
    id,
    tag: el.tagName.toLowerCase(),
    kind,
    text: kind === 'text' || kind === 'link' ? (el.textContent ?? '').trim() : '',
    href: el.getAttribute('href') ?? '',
    src: el.getAttribute('src') ?? '',
    alt: el.getAttribute('alt') ?? '',
    color: el.style.color,
    backgroundColor: el.style.backgroundColor,
    fontSize: el.style.fontSize,
    fontWeight: el.style.fontWeight,
    textAlign: el.style.textAlign,
  }
}

/**
 * Ancestor tag chain for the inspector's breadcrumb, nearest ancestor last,
 * walked with htmlstudio's getParent over the tagged source. Only tagged
 * elements appear (body/html are never tagged), so the chain is a real
 * subset of the document, not a fabricated path.
 */
export function getBreadcrumb(html: string, id: string, maxDepth = 6): string[] {
  const tagged = tagHtml(html)
  const chain: string[] = []
  let currentId: string | null = id
  while (currentId && chain.length < maxDepth) {
    const parent = getParent(tagged, currentId)
    if (!parent) break
    chain.unshift(parent.tag)
    currentId = parent.id
  }
  return chain
}

// -----------------------------------------------------------------------------
// Value normalization for the inspector controls
// -----------------------------------------------------------------------------

/**
 * Normalize a CSS color to #rrggbb for `<input type="color">`. Handles hex
 * (#rgb/#rrggbb/#rrggbbaa — alpha dropped) and comma-form rgb()/rgba();
 * anything else (named colors, hsl, …) returns null and the raw value stays
 * editable in the hex text field.
 */
export function toHexColor(value: string): string | null {
  const v = value.trim().toLowerCase()
  const short = /^#([0-9a-f]{3})$/.exec(v)
  if (short) {
    const [r, g, b] = short[1]
    return `#${r}${r}${g}${g}${b}${b}`
  }
  const long = /^#([0-9a-f]{6})(?:[0-9a-f]{2})?$/.exec(v)
  if (long) return `#${long[1]}`
  const rgb = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)$/.exec(v)
  if (rgb) {
    const channel = (s: string) => Math.min(255, Number(s)).toString(16).padStart(2, '0')
    return `#${channel(rgb[1])}${channel(rgb[2])}${channel(rgb[3])}`
  }
  return null
}

/** True when an inline font-weight value renders bold (keyword or ≥ 600). */
export function isBoldFontWeight(value: string): boolean {
  const v = value.trim().toLowerCase()
  if (v === 'bold' || v === 'bolder') return true
  const n = Number(v)
  return Number.isFinite(n) && n >= 600
}

/** Real CSS validation for free-form style inputs (color, font-size). */
export function isValidCssValue(property: 'color' | 'font-size', value: string): boolean {
  return CSS.supports(property, value)
}
