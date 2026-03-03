# Phase 2: Bot Marketplace - Research

**Researched:** 2026-02-28
**Domain:** React wizard UI integration + existing marketplace infrastructure
**Confidence:** HIGH

## Summary

Phase 2 is primarily a UI integration task, not a net-new feature build. The entire marketplace infrastructure already exists in the codebase — backend routes, frontend components, API client functions, and install logic are all implemented and operational. The gap is entirely in the wizard integration layer.

The `MethodSelectStep` already renders a marketplace mini-preview with popular templates and a "See all" button that opens `MarketplaceBrowser` as a nested dialog. However, it does not present "Browse Templates" as a first-class method card alongside "AI Assisted" and "Blank" — the current three method cards are `ai-assisted`, `blank`, and `import`. The `WizardMethod` type in `creation.ts` only has `'ai-assisted' | 'blank' | 'import'`. The `MarketplaceBrowser` is launched as a _separate_ dialog from inside the wizard, not as a wizard step/method.

**MKTB-01** (browse with categories/search/preview) and **MKTB-02** (one-click create from template) are already fully satisfied by the existing `MarketplaceBrowser` + `BotDetailPanel` + `installMarketplaceTemplate` flow. **MKTB-03** (Browse Templates option alongside AI Assisted and Blank in the creation flow) is the missing piece — the marketplace entry point needs to be elevated from a supplementary mini-preview section to a first-class method card in the wizard.

**Primary recommendation:** Add a "Browse Templates" method card to `MethodSelectStep` that directly opens `MarketplaceBrowser` with the bots tab. The install flow through `BotDetailPanel` → `installMarketplaceTemplate` already handles one-click creation and bot addition to the store. No backend changes required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MKTB-01 | User can browse bot templates with categories, search, and previews from the bot creation flow | Already fully implemented in `MarketplaceBrowser` — categories sidebar, search input, template cards, `BotDetailPanel` preview. Already accessible from `MethodSelectStep`. Gap: not surfaced as a method card. |
| MKTB-02 | User can create a new bot from a marketplace template with one click | Already fully implemented: `BotDetailPanel.handleInstall()` calls `installMarketplaceTemplate()` → POST `/api/marketplace/templates/{id}/install` → backend creates bot in DB → frontend `addBot()` + `setActiveBot()`. All wired. |
| MKTB-03 | "Browse Templates" option is available alongside "AI Assisted" and "Blank" in bot creation | NOT YET DONE. The current `METHODS` array in `MethodSelectStep` has `ai-assisted`, `blank`, `import`. The marketplace exists only as a mini-preview section below. Need a "Browse Templates" card in the main methods grid. |
</phase_requirements>

## Standard Stack

### Core (already in place — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | project version | Component rendering | Already used |
| Zustand | project version | State management | Already used for `useCreationStore`, `useBotStore` |
| lucide-react | project version | Icons | Already used throughout |
| `creation.ts` store | local | Wizard state + step flows | Already handles all method routing |
| `MarketplaceBrowser` | local | Full marketplace UI | Already implemented |
| `installMarketplaceTemplate` | local | One-click install API call | Already implemented |

### No New Dependencies Needed

The entire feature set requires zero new package installations. Everything is already wired.

## Architecture Patterns

### Current Bot Creation Flow

```
CreateBotDialog
  └── CreateBotWizard (index.tsx)
        ├── useCreationStore (creation.ts)
        │     ├── WizardMethod: 'ai-assisted' | 'blank' | 'import'
        │     └── STEP_FLOWS: method → step array
        └── MethodSelectStep (steps/MethodSelectStep.tsx)
              ├── METHODS array: [ai-assisted, blank, import]
              ├── marketplace mini-preview (supplementary, below methods)
              └── MarketplaceBrowser (opens as separate nested Dialog)
```

### Existing Marketplace Install Flow

```
MarketplaceBrowser (Dialog, size="xxl")
  ├── Sidebar: categories + tab switcher
  └── Main: search + BotCard grid
        └── BotDetailPanel (on card click)
              ├── Template details (stats, tools, system prompt, model compat)
              └── "Install Template" button
                    └── installMarketplaceTemplate(templateId)
                          └── POST /api/marketplace/templates/{id}/install
                                └── creates Bot in DB
                                    returns { bot_id }
                          └── addBot(newBot) + setActiveBot(bot_id)
                          └── onInstalled(bot_id) → close wizard
```

### Pattern 1: Method Card (existing pattern in MethodSelectStep)

The METHODS array defines method cards. Each card has an `id: WizardMethod`, name, description, icon, and color. Cards auto-advance to the next step via `handleSelect()`.

```typescript
// From MethodSelectStep.tsx
const METHODS: {
  id: WizardMethod
  name: string
  description: string
  icon: typeof Wand2
  color: string
  badge?: string
}[] = [
  { id: 'ai-assisted', name: 'AI-Assisted', ... badge: 'Recommended' },
  { id: 'blank', name: 'Start Blank', ... },
  { id: 'import', name: 'Import', ... },
]
```

"Browse Templates" does NOT need to be a `WizardMethod` that advances through wizard steps. It opens a dialog instead of advancing. The existing pattern of `marketplaceOpen` state + `setMarketplaceOpen` is the right pattern — just needs to be presented as a card.

### Pattern 2: handleMarketplaceInstalled (already wired)

When a bot is installed from within `MethodSelectStep`, the wizard closes cleanly:

```typescript
// Already in MethodSelectStep.tsx
const handleMarketplaceInstalled = () => {
  close()
  setTimeout(reset, 200)
}
```

This is already correct behavior: install from marketplace → close wizard → bot is active.

### Pattern 3: Grid layout in MethodSelectStep

Current layout:
- Row 1: `ai-assisted` (full width, primary card)
- Row 2: `grid-cols-2` for `blank` and `import`
- Row 3: "Popular from Marketplace" mini-preview section

To add "Browse Templates" as a first-class method alongside `blank` and `import`, the row 2 grid needs to expand to 3 columns, or "Browse Templates" takes its own row, or the layout restructures.

The requirement says "alongside AI Assisted and Blank" — suggesting it appears in the same methods grid, not as a sub-section below. Most natural interpretation: it becomes a 3rd card alongside blank and import in the 2-column grid → making it a 3-column grid, OR it takes its own half-width slot.

### Anti-Patterns to Avoid

- **Adding 'marketplace' as a WizardMethod:** The wizard step flow system is built around method → step array. "Browse Templates" launches a dialog, not a step sequence. Don't add it to `WizardMethod` or `STEP_FLOWS` — it will break step resolution logic.
- **Duplicating install logic:** The `BotDetailPanel.handleInstall()` already calls `addBot` + `setActiveBot`. Don't add extra bot-creation logic in MethodSelectStep.
- **Removing the mini-preview section:** The "Popular from Marketplace" preview is a good discovery UX for templates that exist — it should stay (or can be replaced by the Browse Templates card, but confirm intent).

## What's Already Built (Don't Rebuild)

| Problem | Don't Build | Already Exists | Where |
|---------|-------------|---------------|-------|
| Browse bot templates | Custom browser | `MarketplaceBrowser` | `frontend/src/components/marketplace/MarketplaceBrowser.tsx` |
| Template categories | Custom categories UI | `MarketplaceBrowser` sidebar with categories | Same file |
| Template search | Custom search | `MarketplaceBrowser` search input | Same file |
| Template preview | Custom detail view | `BotDetailPanel` | `frontend/src/components/marketplace/BotDetailPanel.tsx` |
| One-click install | Custom install flow | `installMarketplaceTemplate()` + `BotDetailPanel.handleInstall()` | `frontend/src/api/client.ts:1418` + `BotDetailPanel.tsx:29` |
| Backend install endpoint | New endpoint | `POST /api/marketplace/templates/{id}/install` | `cachibot/api/routes/marketplace.py:421` |
| Bot creation from template | New creation path | `BotDetailPanel` fully handles this | `BotDetailPanel.tsx` |
| Model compatibility display | Custom compat UI | `useModelCompatibility` hook | `frontend/src/hooks/useModelCompatibility.ts` |
| Remote marketplace fetch | Custom fetch | Fully implemented with caching | `client.ts:1280-1370` |

**Key insight:** This phase is a UI polish / discoverability task. The underlying machinery is complete. Work is entirely in `MethodSelectStep.tsx`.

## Common Pitfalls

### Pitfall 1: Treating "Browse Templates" as a wizard step

**What goes wrong:** Adding `'marketplace'` to `WizardMethod` and `STEP_FLOWS` causes `getNextStep()` to break for non-marketplace flows, and the stepper renders incorrectly for a flow that has no steps.

**Why it happens:** The wizard step system assumes every method maps to a step sequence. Marketplace doesn't — it's a dialog, not a step.

**How to avoid:** Keep marketplace as a dialog trigger, not a method. The `handleSelect()` function that advances the wizard should NOT be called for "Browse Templates". Instead, clicking the "Browse Templates" card sets `marketplaceOpen = true`.

**Warning signs:** If you see `WIZARD_STEPS` needing a `'marketplace'` key, you've gone down the wrong path.

### Pitfall 2: Post-install navigation

**What goes wrong:** After installing from marketplace, the bot is created and `setActiveBot()` is called, but the wizard doesn't close or the creation store is left in a dirty state.

**Why it happens:** The install happens inside `BotDetailPanel` via `onInstalled()` callback. The callback chain must properly close `MarketplaceBrowser` AND the wizard.

**How to avoid:** The existing `handleMarketplaceInstalled` in `MethodSelectStep` already calls `close()` + `reset()`. Ensure `MarketplaceBrowser`'s `onClose` and `onInstalled` both lead to the same cleanup. Verify `setCreateBotOpen(false)` is also called in `CreateBotDialog`'s sync effect.

**Warning signs:** After install, the wizard dialog is still visible, or the newly installed bot isn't active.

### Pitfall 3: Grid layout breakage at small sizes

**What goes wrong:** Adding a 3rd card to the `grid-cols-2` grid at row 2 makes it `grid-cols-3`, which becomes cramped at small dialog widths.

**Why it happens:** The dialog is `size="xl"`. Three equal-width cards may be too narrow.

**How to avoid:** Either make "Browse Templates" a full-width card (similar to `ai-assisted`), or use a 3-column grid only if the cards are short enough. Look at existing card widths to judge. Alternatively, demote `import` to a link/text button and promote marketplace to a card.

**Warning signs:** Text truncation or icon misalignment in the method cards section.

## Code Examples

Verified patterns from the existing codebase:

### Opening MarketplaceBrowser from MethodSelectStep (already there)

```typescript
// From MethodSelectStep.tsx — existing pattern to follow
const [marketplaceOpen, setMarketplaceOpen] = useState(false)

const handleMarketplaceInstalled = () => {
  close()
  setTimeout(reset, 200)
}

// Dialog invocation at bottom of JSX
<MarketplaceBrowser
  open={marketplaceOpen}
  onClose={() => setMarketplaceOpen(false)}
  onInstalled={handleMarketplaceInstalled}
  onRoomInstalled={handleRoomInstalled}
/>
```

### Adding a "Browse Templates" card (new work needed)

```typescript
// Pattern: Non-method card that opens marketplace
<button
  onClick={() => setMarketplaceOpen(true)}   // opens dialog, does NOT call handleSelect()
  className={cn(
    'relative flex items-center gap-3 rounded-xl border p-4 text-left transition-all',
    'border-[var(--color-border-primary)] bg-[var(--card-bg)] hover:border-[var(--color-border-secondary)] hover:bg-[var(--color-hover-bg)]'
  )}
>
  <div
    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
    style={{ backgroundColor: '#3b82f620' }}
  >
    <Store className="h-5 w-5" style={{ color: '#3b82f6' }} />
  </div>
  <div>
    <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Browse Templates</h3>
    <p className="text-xs text-[var(--color-text-secondary)]">Pick from curated bot templates</p>
  </div>
</button>
```

### Backend install endpoint (already exists, no changes needed)

```python
# cachibot/api/routes/marketplace.py:421
@router.post("/templates/{template_id}/install", response_model=InstallResponse)
async def install_template(template_id: str, user: User = Depends(get_current_user)) -> InstallResponse:
    # Creates bot in DB, returns { bot_id, name, installed, message }
```

### Frontend install call (already exists, no changes needed)

```typescript
// frontend/src/api/client.ts:1418
export async function installMarketplaceTemplate(templateId: string): Promise<InstallTemplateResponse> {
  return request(`/marketplace/templates/${templateId}/install`, { method: 'POST' })
}
```

## State of the Art

| Old Approach | Current Approach | Status | Impact |
|--------------|------------------|--------|--------|
| Marketplace as separate page/route | Marketplace as Dialog | Already done | Dialog integrates naturally with wizard |
| Bot creation only via wizard steps | Install via template detail panel | Already done | One-click is fully supported |
| Browse Templates as mini-preview supplementary section | Browse Templates as first-class method card | MISSING — this is Phase 2's work | Makes template discovery a primary creation path |

## Open Questions

1. **Layout of method cards after adding Browse Templates**
   - What we know: Current layout is 1 primary + 2-column grid (blank + import)
   - What's unclear: Should Browse Templates be 3rd in the 2-column grid (making it `grid-cols-3`), or should it take a full-width slot below the primary, or should `import` be demoted to make room?
   - Recommendation: Make Browse Templates the 3rd option in the same `grid-cols-2` grid by expanding to `grid-cols-3`, or give it its own full row. Evaluate based on card content length — description text is longer for Browse Templates.

2. **Fate of the "Popular from Marketplace" mini-preview section**
   - What we know: Currently shows 3 popular templates with skeleton loading
   - What's unclear: If Browse Templates gets a method card, does the mini-preview section still add value, or is it redundant?
   - Recommendation: Keep it. It provides discovery without requiring a click. The method card and the preview serve different purposes (entry point vs discovery).

3. **`onInstalled` callback type**
   - What we know: `MarketplaceBrowser.onInstalled` receives `(botId: string)` — `BotDetailPanel` calls `onInstalled(result.bot_id)` after install
   - What's unclear: Does `MethodSelectStep`'s `handleMarketplaceInstalled` need to receive and use the `botId`?
   - Recommendation: Current `handleMarketplaceInstalled` ignores the botId and just closes the wizard. This is correct — `BotDetailPanel` already calls `setActiveBot()` directly. No change needed.

## Sources

### Primary (HIGH confidence)

- Direct code read: `frontend/src/components/dialogs/CreateBotWizard/steps/MethodSelectStep.tsx` — current methods, marketplace state, handlers
- Direct code read: `frontend/src/stores/creation.ts` — `WizardMethod` type, `STEP_FLOWS`, wizard navigation
- Direct code read: `frontend/src/components/dialogs/CreateBotWizard/index.tsx` — wizard rendering, `WIZARD_STEPS`, `FlowKey`
- Direct code read: `frontend/src/components/marketplace/MarketplaceBrowser.tsx` — full marketplace UI implementation
- Direct code read: `frontend/src/components/marketplace/BotDetailPanel.tsx` — install flow implementation
- Direct code read: `cachibot/api/routes/marketplace.py` — backend install endpoint, template CRUD
- Direct code read: `frontend/src/api/client.ts:1237-1430` — `MarketplaceTemplate`, `InstallTemplateResponse`, API functions

### Secondary (MEDIUM confidence)

- Code inspection: `frontend/src/components/views/RoomsView.tsx` — confirms "Browse Templates" button pattern used elsewhere in the app

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — entire stack already exists, no new libraries
- Architecture: HIGH — all patterns verified by direct code reading
- Pitfalls: HIGH — identified from actual code structure (step flow system, dialog layering)
- Gap analysis: HIGH — verified by comparing REQUIREMENTS.md to actual code

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable codebase, UI-only work)
