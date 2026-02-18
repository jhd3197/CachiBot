# Apply CachiBotV2 Design System Styles

Style frontend components using the project's LESS-based design system. Use this skill when writing, modifying, or migrating component styles.

## Instructions

1. **Read the design system** — Before writing any styles, read `docs/architecture/design-system.md` in full. This is the single source of truth for all tokens, classes, mixins, and rules.

2. **Read the relevant LESS files** — Before modifying a component, read the existing styles in `frontend/src/styles/` to understand what classes and patterns already exist. Key files:
   - `variables.less` — LESS variables (colors, spacing, typography, radii, shadows, z-index, transitions, breakpoints, layout constants)
   - `theme.less` — CSS custom properties for light/dark mode
   - `mixins.less` — Reusable parametric mixins
   - `components/` — Component-level styles (buttons, inputs, cards, badges, dialogs, sidebar, etc.)
   - `layout/` — App shell, pages, auth layouts
   - `utilities.less` — Utility classes (.sr-only, .truncate, .line-clamp-*, .scrollbar-none)

3. **Read the component being modified** — Read the TSX file to understand its current className usage before making changes.

## Mandatory Rules

Follow these rules from the design system. Violations are bugs.

- **No raw hex colors.** Always use a LESS variable (`@zinc-500`) or CSS custom property (`var(--color-text-secondary)`). Prefer CSS custom properties for anything theme-aware.
- **No `dark:` prefixes.** The theme system handles dark mode through CSS custom properties that switch via `.dark` on `<html>`. Never add Tailwind-style `dark:` overrides.
- **No inline Tailwind utilities.** All styling lives in LESS files. Components use semantic class names.
- **Always use `.btn` classes for buttons.** Never create raw `<button>` elements with ad-hoc styles.
- **Always use the `<Dialog>` component for modals.** Never build inline modals with fixed positioning.
- **Use `.focus-ring()` mixin for focus styles.** Never create custom focus outlines.
- **Follow BEM naming** for new classes: `.block`, `.block__element`, `.block--modifier`.

## How to Style a Component

### New component styles

1. Create a `.less` file in `frontend/src/styles/components/` (or add to an existing file if it's a variant of an existing component).
2. Import the new file in `frontend/src/styles/index.less` in the correct position (after mixins, within the components section).
3. Use existing LESS variables, CSS custom properties, and mixins. Do not introduce new raw values.
4. In the TSX file, apply the semantic class names.

### Migrating from Tailwind

When converting a component from Tailwind utilities to the design system:

1. Read the TSX file to catalog all `className` strings.
2. Map each Tailwind pattern to its LESS equivalent using Section 8 of the design system doc.
3. Check if a component class already exists (e.g., `.card`, `.btn--primary`, `.input`).
4. For layout patterns, use mixins: `.flex-center()`, `.flex-between()`, `.flex-col()`.
5. For colors, use CSS custom properties: `var(--color-bg-primary)`, `var(--color-text-secondary)`, etc.
6. Replace `cn()` / `clsx()` calls with simple string concatenation or template literals.
7. Replace `dark:` prefixed classes — the CSS custom properties handle this automatically.

### Common translations

| Tailwind | LESS Replacement |
|----------|-----------------|
| `flex items-center justify-center` | `.flex-center()` mixin |
| `flex items-center justify-between` | `.flex-between()` mixin |
| `text-sm font-medium text-zinc-600 dark:text-zinc-400` | `.text-label` class |
| `text-zinc-500 dark:text-zinc-400` | `color: var(--color-text-secondary)` |
| `bg-white dark:bg-zinc-900` | `background: var(--color-bg-primary)` |
| `border-zinc-200 dark:border-zinc-800` | `border-color: var(--color-border-primary)` |
| `rounded-lg` | `border-radius: @radius-lg` |
| `p-4` | `padding: @sp-4` |
| `gap-2` | `gap: @sp-2` |
| `z-50` | `z-index: @z-modal` |
| `transition-colors` | `.transition-colors()` mixin |
| `focus:ring-2 focus:ring-*` | `.focus-ring()` mixin |
| `truncate` | `.truncate()` mixin |
| `animate-spin` | `.animate-spin()` mixin |

## Adding New Tokens

1. Add the LESS variable to `variables.less` in the appropriate section.
2. If theme-aware, add CSS custom properties to both `:root` and `.dark` in `theme.less`.
3. Reference the CSS custom property (not the LESS variable) in component styles.

## Available Component Classes

Before creating new styles, check if one of these already covers the need:

- **Buttons:** `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--ghost`, `.btn--danger`, `.btn--icon`, `.btn--cta`, `.btn--dashed`, `.btn-close`, `.filter-pill` with sizes `.btn--sm`, `.btn--md`, `.btn--lg`
- **Inputs:** `.input`, `.input--sm`, `.input--lg`, `.input-search`, `.textarea`, `.select`, `.input-api-key`, `.chat-input`
- **Cards:** `.card`, `.card--auth`, `.card--table`, `.card--info`, `.card--onboarding`, `.card--tool`, `.card--danger`, with `.card__header`, `.card__title`, `.card__subtitle`, `.card__footer`
- **Badges:** `.badge`, `.badge--neutral`, `.badge--accent`, `.badge--success`, `.badge--warning`, `.badge--danger`, `.badge--info`, `.badge--pill`
- **Dialogs:** `.dialog__backdrop`, `.dialog__panel`, `.dialog__header`, `.dialog__body`, `.dialog__footer`, with sizes `--sm`, `--md`, `--lg`, `--xl`, `--full`
- **Navigation:** `.sidebar-item`, `.rail-btn`, `.nav-btn`, `.context-menu`, `.tooltip` (each with `--active` modifiers)
- **Layout:** `.page-container`, `.page-header`, `.page-content`, `.layout-auth`, `.layout-split`
- **Typography:** `.text-page-title`, `.text-section-heading`, `.text-dialog-title`, `.text-card-title`, `.text-body`, `.text-label`, `.text-caption`, `.text-error`, `.text-tagline`, `.text-mono`
