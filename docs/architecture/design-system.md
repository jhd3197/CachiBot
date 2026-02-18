# CachiBotV2 Design System

> Single source of truth for the CachiBotV2 frontend styling system.
> Last updated: 2026-02-17

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Design Tokens](#3-design-tokens)
4. [Dark Mode System](#4-dark-mode-system)
5. [Component Reference](#5-component-reference)
6. [Mixins Reference](#6-mixins-reference)
7. [Development Rules](#7-development-rules)
8. [Migration Checklist](#8-migration-checklist)
9. [Appendices](#appendices)

---

## 1. Introduction

### What This Document Is

This document defines every design token, component pattern, mixin, and development rule that governs the CachiBotV2 frontend. It is the authoritative reference for anyone writing or reviewing UI code in this project.

### Why It Exists

The CachiBotV2 frontend was originally built with Tailwind CSS utility classes applied directly in JSX. Over time, this approach produced measurable maintenance problems:

- **3,492 className attributes** scattered across 90 TSX files.
- **951 dark-mode prefixes** (`dark:`) duplicated across 60 files, each one a manual override that must stay in sync.
- **7 different focus-ring strategies** instead of one.
- **4 different page background colors** in light mode.
- **134 occurrences** of the exact string `text-zinc-500 dark:text-zinc-400` copy-pasted across 29 files.
- A `Button` component exists but **91% of buttons in the codebase ignore it** (347 raw `<button>` elements vs. 33 `<Button>` usages).

The project is migrating from Tailwind to a LESS-based design system. LESS variables and CSS custom properties replace scattered utility strings with a centralized, auditable, theme-aware token layer. This document captures the target system in full.

---

## 2. Architecture Overview

### 2.1 Folder Structure

```
frontend/
  src/
    styles/
      index.less              # Single entry point — imported in main.tsx
      variables.less           # LESS variables (colors, spacing, typography, etc.)
      theme.less               # CSS custom properties for light/dark mode
      base.less                # Reset, global defaults, scrollbars, selection
      mixins.less              # Reusable parametric mixins
      utilities.less           # Utility classes (.sr-only, .truncate, .line-clamp-*, .scrollbar-none)
      components/
        buttons.less           # .btn and all variants
        inputs.less            # .input, .textarea, .select, .chat-input
        cards.less             # .card and all variants
        badges.less            # .badge and .badge-status
        dialogs.less           # .dialog, .stepper
        sidebar.less           # .sidebar-item, .rail-btn, .nav-btn
        tables.less            # Table styling
        context-menu.less      # .context-menu
        stepper.less           # Dialog stepper (horizontal, vertical, compact)
        tooltip.less           # .tooltip
      layout/
        app-shell.less         # Top-level flex layout, 3-panel structure
        pages.less             # .page-container, .page-header, .page-content
        auth.less              # .layout-auth, .layout-split
      vendor/
        monaco-overrides.less  # Monaco editor theme overrides
```

### 2.2 Import Chain

`index.less` imports files in dependency order. Every subsequent file can reference variables and mixins from the files above it:

```less
// index.less
@import './variables.less';   // 1. Raw LESS variables (no output)
@import './theme.less';       // 2. CSS custom properties (light + dark)
@import './base.less';        // 3. Global resets and defaults
@import './mixins.less';      // 4. Parametric mixins (no output)

// 5. Layout
@import './layout/app-shell.less';
@import './layout/pages.less';
@import './layout/auth.less';

// 6. Components
@import './components/buttons.less';
@import './components/inputs.less';
@import './components/cards.less';
@import './components/badges.less';
@import './components/dialogs.less';
@import './components/sidebar.less';
@import './components/tables.less';
@import './components/context-menu.less';
@import './components/stepper.less';
@import './components/tooltip.less';

// 7. Utilities
@import './utilities.less';

// 8. Vendor overrides
@import './vendor/monaco-overrides.less';
```

### 2.3 Vite Configuration

Vite has built-in LESS support — no plugin required. After migration, the `postcss.config.js` and `tailwind.config.js` files are removed.

```ts
// vite.config.ts (relevant section)
import path from 'path'

export default defineConfig({
  css: {
    preprocessorOptions: {
      less: {
        additionalData: `
          @import "${path.resolve(__dirname, 'src/styles/variables.less')}";
          @import "${path.resolve(__dirname, 'src/styles/mixins.less')}";
        `,
        javascriptEnabled: true,
      },
    },
  },
})
```

Import in `main.tsx`:

```tsx
import './styles/index.less'
```

During the coexistence period, both imports can coexist:

```tsx
import './index.css'          // Tailwind (keep during migration)
import './styles/index.less'  // LESS (add immediately)
```

---

## 3. Design Tokens

### 3.1 Colors — Neutral Palette (Zinc)

| LESS Variable  | Hex       | Usage                              |
|----------------|-----------|------------------------------------|
| `@zinc-50`     | `#fafafa` | Lightest background                |
| `@zinc-100`    | `#f4f4f5` | Secondary background (light mode)  |
| `@zinc-200`    | `#e4e4e7` | Card borders (light mode)          |
| `@zinc-300`    | `#d4d4d8` | Input borders (light mode)         |
| `@zinc-400`    | `#a1a1aa` | Secondary text (dark mode)         |
| `@zinc-500`    | `#71717a` | Muted text, placeholders           |
| `@zinc-600`    | `#52525b` | Secondary text (light mode)        |
| `@zinc-700`    | `#3f3f46` | Borders (dark mode)                |
| `@zinc-800`    | `#27272a` | Secondary background (dark mode)   |
| `@zinc-900`    | `#18181b` | Primary background (dark mode)     |
| `@zinc-950`    | `#09090b` | Deepest dark background            |

### 3.2 Colors — Semantic Palettes

Each semantic color has a full scale from 50 to 950. Key stops:

| Palette    | 50        | 500       | 600       | 700       | Primary Use                |
|------------|-----------|-----------|-----------|-----------|----------------------------|
| **Red**    | `#fef2f2` | `#ef4444` | `#dc2626` | `#b91c1c` | Danger, destructive actions |
| **Green**  | `#f0fdf4` | `#22c55e` | `#16a34a` | `#15803d` | Success, confirmations      |
| **Yellow** | `#fefce8` | `#eab308` | `#ca8a04` | `#a16207` | Warnings, attention         |
| **Blue**   | `#eff6ff` | `#3b82f6` | `#2563eb` | `#1d4ed8` | Information, links          |
| **Purple** | `#faf5ff` | `#a855f7` | `#9333ea` | `#7c3aed` | Special states, branding    |
| **Orange** | `#fff7ed` | `#f97316` | `#ea580c` | `#c2410c` | Secondary warnings          |
| **Cyan**   | `#ecfeff` | `#06b6d4` | `#0891b2` | `#0e7490` | Informational highlights    |
| **Pink**   | `#fdf2f8` | `#ec4899` | `#db2777` | `#be185d` | Decorative accents          |

### 3.3 Colors — Theme-Aware CSS Custom Properties

These are defined in `theme.less` and switch automatically between light and dark mode. **Always use these in component styles instead of raw LESS variables.**

#### Backgrounds

| CSS Custom Property     | Light Value       | Dark Value  |
|-------------------------|-------------------|-------------|
| `--color-bg-app`        | `@zinc-100`       | `@zinc-950` |
| `--color-bg-primary`    | `#ffffff` (white) | `@zinc-900` |
| `--color-bg-secondary`  | `@zinc-100`       | `@zinc-800` |
| `--color-bg-tertiary`   | `@zinc-50`        | `@zinc-800` |
| `--color-bg-inset`      | `@zinc-100`       | `@zinc-900` |
| `--color-bg-overlay`    | `rgba(0,0,0,0.6)` | `rgba(0,0,0,0.7)` |

#### Text

| CSS Custom Property      | Light Value | Dark Value  |
|--------------------------|-------------|-------------|
| `--color-text-primary`   | `@zinc-900` | `@zinc-100` |
| `--color-text-secondary` | `@zinc-500` | `@zinc-400` |
| `--color-text-tertiary`  | `@zinc-400` | `@zinc-600` |
| `--color-text-inverted`  | `white`     | `white`     |

#### Borders

Only two border tokens exist. Use `--color-border-primary` for cards, dividers, and separators. Use `--color-border-secondary` for input borders and stronger separators.

| CSS Custom Property        | Light Value | Dark Value  |
|----------------------------|-------------|-------------|
| `--color-border-primary`   | `@zinc-200` | `@zinc-800` |
| `--color-border-secondary` | `@zinc-300` | `@zinc-700` |
| `--color-border-focus`     | `var(--accent-500)` | `var(--accent-500)` |

#### Interactive States

| CSS Custom Property | Light Value | Dark Value  |
|---------------------|-------------|-------------|
| `--color-hover-bg`  | `@zinc-100` | `@zinc-800` |
| `--color-active-bg` | `@zinc-200` | `@zinc-700` |
| `--color-selected-bg` | `@zinc-200` | `@zinc-700` |

#### Status Colors

Each status has three sub-tokens: `-bg`, `-text`, and `-border`.

| Base Token          | Light -bg     | Light -text   | Dark -bg                      | Dark -text    |
|---------------------|---------------|---------------|-------------------------------|---------------|
| `--color-success`   | `@green-50`   | `@green-700`  | `rgba(34, 197, 94, 0.1)`     | `@green-400`  |
| `--color-warning`   | `@yellow-50`  | `@yellow-700` | `rgba(234, 179, 8, 0.1)`     | `@yellow-400` |
| `--color-danger`    | `@red-50`     | `@red-700`    | `rgba(239, 68, 68, 0.1)`     | `@red-400`    |
| `--color-info`      | `@blue-50`    | `@blue-700`   | `rgba(59, 130, 246, 0.1)`    | `@blue-400`   |

#### Component-Level Tokens

| Token Group      | Properties                                                             |
|------------------|------------------------------------------------------------------------|
| `--btn-*`        | `--btn-secondary-bg`, `--btn-secondary-text`, `--btn-secondary-hover`, `--btn-secondary-border`, `--btn-ghost-hover`, `--btn-ghost-text`, `--btn-ghost-text-hover` |
| `--input-*`      | `--input-bg`, `--input-border`, `--input-text`, `--input-placeholder`  |
| `--card-*`       | `--card-bg`, `--card-border`, `--card-shadow`                          |
| `--label-*`      | `--label-text`                                                         |
| `--code-*`       | `--code-bg`, `--code-text`                                             |
| `--scrollbar-*`  | `--scrollbar-thumb`, `--scrollbar-thumb-hover`                         |

### 3.4 Colors — Accent (Dynamic)

Accent colors are set at runtime by JavaScript (`stores/ui.ts`) when the user picks a theme color. They are injected as CSS custom properties on `:root`.

| CSS Custom Property | Description          |
|---------------------|----------------------|
| `--accent-50`       | Lightest accent tint |
| `--accent-100` – `--accent-400` | Intermediate tints |
| `--accent-500`      | **Primary accent**   |
| `--accent-600`      | Hover / active shade |
| `--accent-700`      | Button hover target  |
| `--accent-800` – `--accent-950` | Deep shades |

In LESS, reference them as `var(--accent-500)`, etc. These cannot be LESS variables because they are dynamic.

**Note:** When setting accent colors in JS, also set RGB triplet variants (e.g., `--accent-600-rgb`) for use with `rgba()` opacity variations.

### 3.5 Spacing

| LESS Variable | Value      | px  |
|---------------|------------|-----|
| `@sp-0`       | `0`        | 0   |
| `@sp-0.5`     | `0.125rem` | 2   |
| `@sp-1`       | `0.25rem`  | 4   |
| `@sp-1.5`     | `0.375rem` | 6   |
| `@sp-2`       | `0.5rem`   | 8   |
| `@sp-2.5`     | `0.625rem` | 10  |
| `@sp-3`       | `0.75rem`  | 12  |
| `@sp-3.5`     | `0.875rem` | 14  |
| `@sp-4`       | `1rem`     | 16  |
| `@sp-5`       | `1.25rem`  | 20  |
| `@sp-6`       | `1.5rem`   | 24  |
| `@sp-8`       | `2rem`     | 32  |
| `@sp-10`      | `2.5rem`   | 40  |
| `@sp-12`      | `3rem`     | 48  |
| `@sp-16`      | `4rem`     | 64  |
| `@sp-20`      | `5rem`     | 80  |
| `@sp-24`      | `6rem`     | 96  |

### 3.6 Typography

#### Font Families

| LESS Variable | Value                                           |
|---------------|-------------------------------------------------|
| `@font-sans`  | `'Inter', system-ui, -apple-system, sans-serif` |
| `@font-mono`  | `'JetBrains Mono', 'Fira Code', ui-monospace, monospace` |

#### Font Sizes

| LESS Variable | Value      | px |
|---------------|------------|----|
| `@text-xs`    | `0.75rem`  | 12 |
| `@text-sm`    | `0.875rem` | 14 |
| `@text-base`  | `1rem`     | 16 |
| `@text-lg`    | `1.125rem` | 18 |
| `@text-xl`    | `1.25rem`  | 20 |
| `@text-2xl`   | `1.5rem`   | 24 |
| `@text-3xl`   | `1.875rem` | 30 |

#### Font Weights

| LESS Variable    | Value |
|------------------|-------|
| `@font-normal`   | `400` |
| `@font-medium`   | `500` |
| `@font-semibold` | `600` |
| `@font-bold`     | `700` |

#### Line Heights

| LESS Variable    | Value  |
|------------------|--------|
| `@leading-none`  | `1`    |
| `@leading-tight` | `1.25` |
| `@leading-snug`  | `1.375`|
| `@leading-normal`| `1.5`  |
| `@leading-relaxed`| `1.625`|

### 3.7 Border Radius

| LESS Variable  | Value      | Tailwind Equivalent |
|----------------|------------|---------------------|
| `@radius-none` | `0`        | `rounded-none`      |
| `@radius-sm`   | `0.25rem`  | `rounded`           |
| `@radius-md`   | `0.375rem` | `rounded-md`        |
| `@radius-lg`   | `0.5rem`   | `rounded-lg`        |
| `@radius-xl`   | `0.75rem`  | `rounded-xl`        |
| `@radius-2xl`  | `1rem`     | `rounded-2xl`       |
| `@radius-full` | `9999px`   | `rounded-full`      |

### 3.8 Shadows

| LESS Variable | Value |
|---------------|-------|
| `@shadow-sm`  | `0 1px 2px 0 rgba(0, 0, 0, 0.05)` |
| `@shadow-md`  | `0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)` |
| `@shadow-lg`  | `0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)` |
| `@shadow-xl`  | `0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)` |
| `@shadow-2xl` | `0 25px 50px -12px rgba(0, 0, 0, 0.25)` |

### 3.9 Z-Index Scale

| LESS Variable  | Value | Usage                    |
|----------------|-------|--------------------------|
| `@z-dropdown`  | `30`  | Dropdowns, context menus |
| `@z-sticky`    | `40`  | Sticky headers           |
| `@z-modal`     | `50`  | Dialog/modal panels      |
| `@z-popover`   | `60`  | Popovers above modals    |
| `@z-tooltip`   | `70`  | Tooltip layer            |
| `@z-toast`     | `80`  | Toast notifications      |

### 3.10 Transitions

| LESS Variable      | Value |
|--------------------|-------|
| `@transition-fast`   | `150ms ease` |
| `@transition-normal` | `200ms ease` |
| `@transition-slow`   | `300ms ease` |
| `@transition-colors` | `color 150ms ease, background-color 150ms ease, border-color 150ms ease` |

### 3.11 Breakpoints

| LESS Variable | Value    |
|---------------|----------|
| `@screen-sm`  | `640px`  |
| `@screen-md`  | `768px`  |
| `@screen-lg`  | `1024px` |
| `@screen-xl`  | `1280px` |
| `@screen-2xl` | `1536px` |

### 3.12 Layout Constants

| LESS Variable              | Value  | Usage                |
|----------------------------|--------|----------------------|
| `@sidebar-width-collapsed` | `4rem` | Bot rail (64px)      |
| `@sidebar-width-expanded`  | `16rem`| Sidebar panel (256px)|
| `@header-height`           | `3rem` | Top header (48px)    |
| `@title-bar-height`        | `2rem` | Electron title bar   |

### 3.13 Dialog Sizes

| LESS Variable  | Value  | Tailwind Equivalent |
|----------------|--------|---------------------|
| `@dialog-sm`   | `28rem`| `max-w-md`          |
| `@dialog-md`   | `32rem`| `max-w-lg`          |
| `@dialog-lg`   | `42rem`| `max-w-2xl`         |
| `@dialog-xl`   | `56rem`| `max-w-4xl`         |
| `@dialog-full` | `90vw` | Custom              |

### 3.14 Component Heights

| LESS Variable | Value    | Tailwind Equivalent |
|---------------|----------|---------------------|
| `@height-sm`  | `2rem`   | `h-8` (32px)       |
| `@height-md`  | `2.5rem` | `h-10` (40px)      |
| `@height-lg`  | `3rem`   | `h-12` (48px)      |

---

## 4. Dark Mode System

### 4.1 How It Works

The dark mode system uses CSS custom properties toggled by a `.dark` class on the `<html>` element. A single set of custom properties is defined in `theme.less` with two value sets:

```less
// theme.less
:root {
  --color-bg-primary: #ffffff;
  --color-text-primary: @zinc-900;
  --color-border-primary: @zinc-200;
  // ... all light-mode values
}

.dark {
  --color-bg-primary: @zinc-900;
  --color-text-primary: @zinc-100;
  --color-border-primary: @zinc-800;
  // ... all dark-mode values
}
```

Components reference only the custom properties:

```less
.card {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-primary);
}
```

When `.dark` is added to `<html>`, every component updates automatically. **No per-element `dark:` prefixes are needed.** This eliminates the 951 `dark:` variants currently scattered across the codebase.

### 4.2 Flash-of-Unstyled-Content (FOUC) Prevention

The `index.html` file contains a synchronous IIFE in the `<head>` that runs before React loads:

```html
<script>
  (function() {
    try {
      var stored = localStorage.getItem('cachibot-ui');
      var theme = stored ? JSON.parse(stored).state.theme : 'system';
      var isDark = theme === 'dark' ||
        (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (isDark) document.documentElement.classList.add('dark');
    } catch (e) {}
  })();
</script>
```

This reads the user's saved theme preference from the Zustand persisted store in `localStorage` and applies `.dark` immediately, before the first paint. **This IIFE must be preserved.**

### 4.3 Cascading Example

When the user toggles from light to dark mode:

1. JavaScript adds `.dark` to `document.documentElement`.
2. The CSS custom property `--color-bg-primary` changes from `#ffffff` to `#18181b` (zinc-900).
3. Every component using `background: var(--color-bg-primary)` updates instantly.
4. **No component file is touched. No className changes needed.**

---

## 5. Component Reference

### 5.1 Buttons

**Classes:** `.btn`, with modifiers for variant and size.

#### Variants

| Class           | Description                                            |
|-----------------|--------------------------------------------------------|
| `.btn--primary`   | Accent-colored fill, white text. Primary CTA.        |
| `.btn--secondary` | Neutral fill (zinc-100 / zinc-800 dark).             |
| `.btn--ghost`     | Transparent background, hover reveals fill.          |
| `.btn--danger`    | Red fill, white text. Destructive actions.           |
| `.btn--icon`      | Square button sized for a single icon (no text).     |
| `.btn--cta`       | Large gradient accent button for splash/onboarding.  |
| `.btn--dashed`    | Dashed border, transparent fill. "Add new" actions.  |
| `.btn-close`      | Dialog/panel close button (top-right X icon).        |
| `.filter-pill`    | Small toggleable chip for list filtering.            |

#### Sizes

| Class      | Height | Padding  | Font Size  |
|------------|--------|----------|------------|
| `.btn--sm` | 32px   | 0 12px   | `@text-sm` |
| `.btn--md` | 40px   | 0 16px   | `@text-sm` |
| `.btn--lg` | 48px   | 0 24px   | `@text-base`|

#### Behavior

- **Hover:** background darkens (accent-600 → accent-700 for primary).
- **Focus:** unified `outline: 2px solid var(--accent-500); outline-offset: 2px`.
- **Disabled:** `opacity: 0.5; pointer-events: none`.

#### Usage

```jsx
// DO: Use semantic button classes
<button className="btn btn--primary btn--md">Save Changes</button>
<button className="btn btn--ghost btn--sm">Cancel</button>
<button className="btn btn--icon btn--sm"><X size={16} /></button>

// DON'T: Create raw buttons with ad-hoc styles
<button className="bg-blue-500 text-white px-4 py-2 rounded">Save</button>
```

### 5.2 Inputs

**Classes:** `.input`, `.input-search`, `.textarea`, `.select`, `.input-api-key`, `.chat-input`.

| Class            | Description                                                      |
|------------------|------------------------------------------------------------------|
| `.input`         | Standard single-line text input.                                 |
| `.input--sm`     | Compact input variant.                                           |
| `.input--lg`     | Large input variant.                                             |
| `.input-search`  | Input with built-in search icon padding on the left.             |
| `.textarea`      | Multi-line text area with consistent border and padding.         |
| `.select`        | Native `<select>` styled to match the input look.               |
| `.input-api-key` | Monospaced input for API keys and tokens.                        |
| `.chat-input`    | Full-width chat message input with larger padding and radius.    |

#### Common Properties

- Background: `var(--input-bg)`
- Border: `1px solid var(--input-border)`
- Border-radius: `@radius-lg`
- **Focus:** `border-color: transparent; box-shadow: 0 0 0 2px var(--accent-500)` (unified)
- Placeholder: `var(--input-placeholder)`

#### Form Field Pattern

```less
.form-field {
  &__label { /* .text-label styling */ }
  &__help  { /* caption below input */ }
  &__error { /* red error text below input */ }
}
```

#### Usage

```jsx
// DO
<input type="text" className="input" placeholder="Enter name..." />
<textarea className="textarea" rows={4} />
<select className="select"><option>Choose...</option></select>

// DON'T
<input className="w-full px-3 py-2 border border-zinc-300 rounded-lg dark:bg-zinc-800 ..." />
```

### 5.3 Cards

**Classes:** `.card`, with variant modifiers.

| Class              | Description                                              |
|--------------------|----------------------------------------------------------|
| `.card`            | Base card: rounded-xl, bordered, background, shadow.     |
| `.card--auth`      | Centered card for login/setup pages.                     |
| `.card--table`     | Card wrapping a data table. No inner padding.            |
| `.card--info`      | Informational callout card (muted background).           |
| `.card--onboarding`| Wizard-step card with larger radius and shadow.          |
| `.card--tool`      | Tool/skill card with hover state. Compact padding.       |
| `.card--danger`    | Red-bordered card for destructive-action zones.          |

#### Sub-elements

| Class           | Description                           |
|-----------------|---------------------------------------|
| `.card__header`   | Flex-between header row.            |
| `.card__title`    | Card heading text.                  |
| `.card__subtitle` | Card secondary text.                |
| `.card__footer`   | Footer with border-top separator.   |

#### Special Card Types

| Class          | Description                                              |
|----------------|----------------------------------------------------------|
| `.task-card`   | Kanban board card with hover and drag handle.            |
| `.result-card` | Execution result with left border accent.                |
| `.list-item`   | Compact clickable list row with icon, content, actions.  |

#### Usage

```jsx
// DO
<div className="card card--auth">
  <h3 className="card__title">Login</h3>
</div>

// DON'T
<div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 shadow">
```

### 5.4 Badges

**Classes:** `.badge` with color modifiers, and `.badge-status`.

#### Color Variants

| Class              | Usage                       |
|--------------------|-----------------------------|
| `.badge--neutral`  | Default/inactive states     |
| `.badge--accent`   | Highlighted, themed items   |
| `.badge--success`  | Completed, online, active   |
| `.badge--warning`  | Pending, needs attention    |
| `.badge--danger`   | Failed, error, offline      |
| `.badge--info`     | Informational tags          |

#### Shape Variants

| Modifier        | Description                |
|-----------------|----------------------------|
| (default)       | Rounded corners (`@radius-sm`) |
| `.badge--pill`  | Fully rounded (`@radius-full`) |

#### Usage

```jsx
// DO
<span className="badge badge--success">Active</span>
<span className="badge badge--danger badge--pill">Failed</span>

// DON'T
<span className="inline-flex items-center px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
```

### 5.5 Dialogs

**Classes:** `.dialog` with sub-elements and the `.stepper` component.

#### Structure

| Class               | Description                                            |
|---------------------|--------------------------------------------------------|
| `.dialog__backdrop` | Full-screen overlay: fixed, black/60, backdrop-blur.   |
| `.dialog__panel`    | Centered content container. Sized by modifier.         |
| `.dialog__header`   | Top section with title and close button.               |
| `.dialog__body`     | Scrollable content area (max-height: 60vh).            |
| `.dialog__footer`   | Bottom action bar with button alignment.               |

#### Panel Sizes

| Modifier              | Max-width              |
|-----------------------|------------------------|
| `.dialog__panel--sm`  | `@dialog-sm` (28rem)   |
| `.dialog__panel--md`  | `@dialog-md` (32rem)   |
| `.dialog__panel--lg`  | `@dialog-lg` (42rem)   |
| `.dialog__panel--xl`  | `@dialog-xl` (56rem)   |
| `.dialog__panel--full`| `@dialog-full` (90vw)  |

#### Stepper

| Class                        | Description                              |
|------------------------------|------------------------------------------|
| `.stepper--horizontal`       | Steps laid out in a row.                 |
| `.stepper--vertical`         | Steps laid out in a column.              |
| `.stepper--compact`          | Minimal dot indicators.                  |
| `.stepper__step--active`     | Currently active step.                   |
| `.stepper__step--completed`  | Completed step (checkmark).              |
| `.stepper__step--upcoming`   | Future step (muted).                     |

#### Usage

```jsx
// DO: Use the Dialog component
<Dialog open={isOpen} onClose={handleClose} size="lg">
  <DialogHeader title="Settings" onClose={handleClose} />
  <div className="dialog__body">{/* content */}</div>
  <DialogFooter>
    <button className="btn btn--secondary btn--md">Cancel</button>
    <button className="btn btn--primary btn--md">Save</button>
  </DialogFooter>
</Dialog>

// DON'T: Build inline modals
<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
```

### 5.6 Sidebar and Navigation

| Class                    | Description                                          |
|--------------------------|------------------------------------------------------|
| `.sidebar-item`          | Row in the expanded sidebar. Icon + label + badge.   |
| `.sidebar-item--active`  | Currently selected sidebar item.                     |
| `.rail-btn`              | Icon-only button in the collapsed bot rail.          |
| `.rail-btn--active`      | Currently selected rail button.                      |
| `.nav-btn`               | Navigation button in the header area.                |
| `.nav-btn--active`       | Currently active nav button.                         |
| `.context-menu`          | Dropdown menu container.                             |
| `.context-menu__item`    | Individual menu option.                              |
| `.context-menu__divider` | Horizontal separator between groups.                 |
| `.tooltip`               | Small text popup on hover.                           |

### 5.7 Layout

| Class             | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `.page-container` | Outer wrapper for a full page view (`flex-col`, full height).  |
| `.page-header`    | Top area with title, subtitle, and action buttons.             |
| `.page-content`   | Main scrollable content area below the header.                 |
| `.layout-auth`    | Centered single-column layout for auth pages.                  |
| `.layout-split`   | Two-column layout (list panel + detail panel).                 |

#### Usage

```jsx
// DO
<div className="page-container">
  <div className="page-header">
    <h1 className="text-page-title">Users</h1>
    <button className="btn btn--primary btn--sm">Add User</button>
  </div>
  <div className="page-content">
    {/* page body */}
  </div>
</div>
```

### 5.8 Typography

| Class                   | Size        | Weight         | Color                        | Usage              |
|-------------------------|-------------|----------------|------------------------------|--------------------|
| `.text-page-title`      | `@text-xl`  | `@font-bold`   | `--color-text-primary`       | Main page headings |
| `.text-section-heading` | `@text-sm`  | `@font-medium` | `--color-text-primary`       | Section titles     |
| `.text-dialog-title`    | `@text-lg`  | `@font-bold`   | `--color-text-primary`       | Dialog headings    |
| `.text-card-title`      | `@text-sm`  | `@font-medium` | `--color-text-primary`       | Card headings      |
| `.text-body`            | `@text-sm`  | `@font-normal` | `--color-text-primary`       | Default body text  |
| `.text-label`           | `@text-sm`  | `@font-medium` | `--color-text-secondary`     | Form labels, meta  |
| `.text-caption`         | `@text-xs`  | `@font-normal` | `--color-text-tertiary`      | Small helper text  |
| `.text-error`           | `@text-sm`  | `@font-normal` | `var(--color-danger-text)`   | Validation errors  |
| `.text-tagline`         | `@text-sm`  | `@font-normal` | `--color-text-secondary`     | Auth page taglines |
| `.text-mono`            | `@text-sm`  | `@font-normal` | inherited (mono family)      | Code, API keys     |

---

## 6. Mixins Reference

All mixins are defined in `mixins.less`. They generate no CSS output until called.

### 6.1 Layout Mixins

| Mixin             | Output                                                              |
|-------------------|----------------------------------------------------------------------|
| `.flex-center()`  | `display: flex; align-items: center; justify-content: center`        |
| `.flex-between()` | `display: flex; align-items: center; justify-content: space-between` |
| `.flex-col()`     | `display: flex; flex-direction: column`                              |

### 6.2 Text Mixins

| Mixin                 | Output                                                  |
|-----------------------|---------------------------------------------------------|
| `.truncate()`         | `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` |
| `.line-clamp(@lines)` | Webkit line clamp for multi-line truncation             |

### 6.3 Scroll Mixins

| Mixin              | Output                                          |
|--------------------|-------------------------------------------------|
| `.scrollbar-none()`| Hides scrollbar on all browsers                 |
| `.scrollbar-thin()`| Thin styled scrollbar using theme custom props  |

### 6.4 Interaction Mixins

| Mixin                  | Output                                                   |
|------------------------|----------------------------------------------------------|
| `.transition-colors()` | `transition: @transition-colors`                         |
| `.transition-all()`    | `transition: all @transition-fast`                       |
| `.focus-ring()`        | `outline: 2px solid var(--accent-500); outline-offset: 2px` |
| `.focus-ring-inset()`  | `box-shadow: 0 0 0 2px var(--accent-500)` (no offset)   |

### 6.5 Responsive Mixins

| Mixin                  | Output                                |
|------------------------|---------------------------------------|
| `.screen-sm(@rules)`   | `@media (min-width: @screen-sm) { }` |
| `.screen-md(@rules)`   | `@media (min-width: @screen-md) { }` |
| `.screen-lg(@rules)`   | `@media (min-width: @screen-lg) { }` |
| `.screen-xl(@rules)`   | `@media (min-width: @screen-xl) { }` |

### 6.6 Component Mixins

| Mixin                       | Parameters                | Generates                                       |
|-----------------------------|---------------------------|-------------------------------------------------|
| `.button(@variant, @size)`  | variant name, size name   | Complete button with hover/focus/disabled states |
| `.button-base()`            | none                      | Base button structure (no colors)                |
| `.button-variant(@variant)` | `primary`, `secondary`, `ghost`, `danger`, `icon` | Color layer only |
| `.button-size(@size)`       | `sm`, `md`, `lg`          | Size layer only                                  |
| `.input-base()`             | none                      | Full input styling                               |
| `.input-with-icon(@side)`   | `left` or `right`         | Input with icon padding                          |
| `.textarea-base()`          | none                      | Multi-line input variant                         |
| `.select-base()`            | none                      | Styled native select                             |
| `.card(@variant)`           | `default`, `auth`, `info`, `table`, `onboarding`, `tool`, `danger` | Card variant |
| `.card-base()`              | none                      | Base card structure                              |
| `.badge(@color, @shape)`    | color name, shape name    | Badge with colored bg/text                       |
| `.badge-base()`             | none                      | Base badge structure                             |
| `.badge-status(@status)`    | status name               | Status-colored badge                             |
| `.dialog-backdrop()`        | none                      | Fixed overlay with blur                          |
| `.dialog-panel(@size)`      | `sm`, `md`, `lg`, `xl`, `full` | Centered panel                              |
| `.dialog-header()`          | none                      | Header with flex-between                         |
| `.dialog-body()`            | none                      | Scrollable body section                          |
| `.dialog-footer()`          | none                      | Footer with border-top                           |
| `.sidebar-item(@variant)`   | `nav`, `rail`, `chat`     | Sidebar row with hover/active                    |
| `.page-container()`         | none                      | Page wrapper                                     |
| `.page-header()`            | none                      | Flex-between header row                          |
| `.page-title()`             | none                      | Page title typography                            |
| `.page-content()`           | none                      | Scrollable content area                          |
| `.table-base()`             | none                      | Full-width table                                 |
| `.table-header-cell()`      | none                      | Uppercase, small, muted th                       |
| `.table-cell()`             | none                      | Standard td with border                          |
| `.table-row-hover()`        | none                      | Hover background on tr                           |
| `.context-menu()`           | none                      | Dropdown menu container                          |
| `.context-menu-item()`      | none                      | Menu item with hover                             |
| `.tooltip()`                | none                      | Positioned tooltip                               |

---

## 7. Development Rules

These rules are **mandatory** for all frontend work after the migration is complete.

### Rule 1: No Raw Hex Colors

Never write a hex color directly in a `.less` file or inline style. Always reference a LESS variable or CSS custom property.

```less
// WRONG
.my-element { color: #71717a; }

// RIGHT
.my-element { color: var(--color-text-tertiary); }
```

### Rule 2: No `dark:` Prefixes

The theme system handles dark mode automatically through CSS custom properties. Never add Tailwind-style `dark:` overrides.

```jsx
// WRONG
<div className="bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100">

// RIGHT
<div className="card">
// .card uses var(--color-bg-primary) and var(--color-text-primary)
// which switch automatically.
```

### Rule 3: No Inline Tailwind Utilities

After migration, Tailwind is removed. All styling lives in LESS files.

```jsx
// WRONG
<div className="flex items-center justify-between p-4 border-b border-zinc-200">

// RIGHT
<div className="page-header">
```

### Rule 4: Always Use the Button Component

Never create a raw `<button>` element with ad-hoc styles. Use the `.btn` class system or the `<Button>` React component.

### Rule 5: Always Use the Dialog Component

Never build an inline modal with fixed positioning and backdrop. Use the `<Dialog>` component which handles accessibility, escape-to-close, backdrop click, scroll lock, and portal rendering.

### Rule 6: Use the Standard Focus Ring

Never create custom focus styles. Use the `.focus-ring()` mixin or rely on the base styles.

```less
// WRONG
.my-button:focus {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.5);
}

// RIGHT
.my-button {
  .focus-ring();
}
```

### Rule 7: How to Add a New Color Token

1. Add the LESS variable to `variables.less` in the appropriate palette section.
2. If the color needs light/dark variants, add CSS custom properties to both `:root` and `.dark` blocks in `theme.less`.
3. Reference the CSS custom property (not the LESS variable) in component styles.
4. Document the new token in this file.

### Rule 8: How to Add a New Component Style

1. Create a new `.less` file in `styles/components/` (or add to an existing one if it's a variant).
2. Import the new file in `index.less` in the correct position.
3. Use existing LESS variables, CSS custom properties, and mixins. Do not introduce new raw values.
4. Follow BEM naming: `.block`, `.block__element`, `.block--modifier`.
5. Document the component in Section 5 of this file.

### Rule 9: How to Modify the Theme

1. To change a color mapping, edit `theme.less`. Change the value in `:root` (light) and/or `.dark`.
2. To add a new theme-aware property, add it to both `:root` and `.dark`.
3. Test both themes after any change.
4. Never modify `variables.less` to fix a theme issue — the raw palette stays stable. Theme mapping belongs in `theme.less`.

---

## 8. Migration Checklist (Quick Reference)

### 8.1 Common Tailwind → LESS Translations

| Tailwind                                                    | LESS Replacement                              |
|-------------------------------------------------------------|-----------------------------------------------|
| `flex items-center justify-center`                          | `.flex-center()` mixin                        |
| `flex items-center justify-between`                         | `.flex-between()` mixin                       |
| `flex flex-col`                                             | `.flex-col()` mixin                           |
| `text-sm font-medium text-zinc-600 dark:text-zinc-400`     | `.text-label` class                           |
| `text-zinc-500 dark:text-zinc-400`                          | `color: var(--color-text-secondary)`          |
| `text-xl font-bold` / `text-2xl font-bold`                 | `.text-page-title` class                      |
| `bg-white dark:bg-zinc-900`                                | `background: var(--color-bg-primary)`         |
| `bg-zinc-50 dark:bg-zinc-800`                              | `background: var(--color-bg-secondary)`       |
| `border-zinc-200 dark:border-zinc-700` / `dark:border-zinc-800` | `border-color: var(--color-border-primary)` |
| `border-zinc-300 dark:border-zinc-700`                     | `border-color: var(--color-border-secondary)` |
| `rounded-lg`                                                | `border-radius: @radius-lg`                   |
| `rounded-xl`                                                | `border-radius: @radius-xl`                   |
| `rounded-full`                                              | `border-radius: @radius-full`                 |
| `p-4`                                                       | `padding: @sp-4`                              |
| `px-3 py-2`                                                 | `padding: @sp-2 @sp-3`                        |
| `gap-2`                                                     | `gap: @sp-2`                                  |
| `h-10 px-4 text-sm` (button)                               | `.btn--md` (built into button mixin)          |
| `truncate`                                                  | `.truncate()` mixin                           |
| `transition-colors`                                         | `.transition-colors()` mixin                  |
| `focus:ring-2 focus:ring-*-500`                             | `.focus-ring()` mixin                         |
| `disabled:opacity-50 disabled:pointer-events-none`          | Built into `.btn` base                        |
| `z-50`                                                      | `z-index: @z-modal`                           |
| `animate-spin`                                              | `.animate-spin()` mixin                       |

### 8.2 What to Replace

- All `className` strings containing Tailwind utilities
- All `dark:` prefixed classes (replaced by theme custom properties)
- All `cn()` calls (replace with simple string concatenation or direct class names)
- The `clsx` and `tailwind-merge` dependencies
- The `postcss.config.js` and `tailwind.config.js` files
- The PostCSS, Tailwind, and Autoprefixer dev dependencies

### 8.3 What to Keep

- The `<Button>` React component — update internals to use `.btn` classes
- The `<Dialog>` React component — update internals to use `.dialog` classes
- All React component logic, state management, and event handlers
- The Zustand stores, API layer, and routing
- The `index.html` IIFE for dark-mode FOUC prevention

### 8.4 Patterns to Watch For

1. **Conditional classes in `cn()`**: Convert to conditional class application.
   ```jsx
   // Before
   cn('text-sm', isActive && 'text-accent-500 font-bold')
   // After
   className={`text-body ${isActive ? 'sidebar-item--active' : ''}`}
   ```

2. **Responsive prefixes** (`sm:`, `md:`, `lg:`): Convert to `@media` queries using LESS breakpoint mixins.

3. **Arbitrary values** (`w-[280px]`, `max-w-[90vw]`): Replace with LESS layout constants or explicit values.

4. **Color opacity** (`bg-black/60`, `zinc-800/50`): Use `rgba()` or LESS `fade()` function.

5. **Animation classes** (`animate-spin`, `animate-pulse`): Use the corresponding LESS animation mixins defined in `mixins.less`.

---

## Appendices

### Appendix A: File Count Summary

| Category         | LESS Files | Patterns |
|------------------|------------|----------|
| Button variants  | 1          | 11       |
| Input variants   | 1          | 6        |
| Card variants    | 1          | 9        |
| Badge variants   | 1          | 7        |
| Dialog + Stepper | 2          | 12       |
| Sidebar/Nav      | 1          | 8        |
| Layout           | 3          | 7        |
| Typography       | (in utilities) | 10   |
| Utilities        | 1          | 6        |
| **Total**        | **~14**    | **72**   |

### Appendix B: Files to Remove Post-Migration

| File                 | Reason                         |
|----------------------|--------------------------------|
| `tailwind.config.js` | Tailwind no longer used       |
| `postcss.config.js`  | PostCSS no longer needed      |
| `index.css`          | Replaced by `index.less`      |
| `lib/utils.ts` (`cn` function) | No Tailwind class merging |

### Appendix C: Dependencies to Remove Post-Migration

| Package          | Type | Reason                       |
|------------------|------|------------------------------|
| `tailwindcss`    | dev  | Replaced by LESS             |
| `postcss`        | dev  | No longer needed             |
| `autoprefixer`   | dev  | Vite handles this            |
| `tailwind-merge` | prod | No Tailwind classes to merge |
| `clsx`           | prod | Simple concatenation suffices|

### Appendix D: Migration Phases

| Phase | Scope                     | Files | Risk   |
|-------|---------------------------|-------|--------|
| 0     | Foundation (infrastructure)| ~16   | None   |
| 1     | Shared components          | ~12   | Low    |
| 2a    | Auth pages                 | ~6    | Low    |
| 2b-c  | Layout                     | ~4    | Medium |
| 2d    | Simple views               | ~6    | Low    |
| 2e    | Medium views               | ~6    | Medium |
| 2f-g  | Complex views              | ~3    | High   |
| 2h    | Dialogs                    | ~28   | Medium |
| 2i    | Feature modules            | ~30   | Low-Med|
| 3     | Cleanup (remove Tailwind)  | ~6    | Medium |
| **Total** |                       | **~100** |     |
