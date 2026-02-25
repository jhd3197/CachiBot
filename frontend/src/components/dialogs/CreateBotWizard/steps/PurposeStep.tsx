import { useState } from 'react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { cn } from '../../../../lib/utils'

const DEFAULT_VISIBLE = 6

// Category-specific placeholder examples
const CATEGORY_EXAMPLES: Record<string, string> = {
  fitness: "Help me plan my gym workouts, track my progress, and give me nutrition advice to build muscle",
  cooking: "Help me plan weekly meals, find recipes based on what's in my fridge, and track my calorie intake",
  finance: "Help me budget my monthly expenses, track spending, and give me tips to save more money",
  travel: "Help me plan trips, find good deals on flights and hotels, and create day-by-day itineraries",
  coding: "Help me debug Python code, review my pull requests, and explain complex concepts simply",
  writing: "Help me write blog posts about technology, improve my drafts, and come up with catchy titles",
  learning: "Help me study for my exams, explain difficult topics, and create flashcards to memorize",
  productivity: "Help me organize my tasks, set goals, and stay focused on what matters most",
  creative: "Help me brainstorm ideas for my art projects, give feedback on my designs, and inspire me",
  gaming: "Help me improve at competitive games, find the best builds, and discover new games to play",
  social: "Help me improve my conversation skills, give advice on dating, and be more confident socially",
  marketing: "Help me plan campaigns, optimize SEO, manage social media, and track analytics",
}

export function PurposeStep() {
  const { form, updateForm } = useCreationStore()
  const [expanded, setExpanded] = useState(false)

  const placeholder = CATEGORY_EXAMPLES[form.purposeCategory] || "Describe what you want your bot to help you with..."
  const visibleCategories = expanded ? PURPOSE_CATEGORIES : PURPOSE_CATEGORIES.slice(0, DEFAULT_VISIBLE)
  const hiddenCount = PURPOSE_CATEGORIES.length - DEFAULT_VISIBLE

  const toggleCategory = (id: string) => {
    updateForm({ purposeCategory: form.purposeCategory === id ? '' : id })
  }

  return (
    <div className="space-y-6">
      {/* Purpose Description (primary) */}
      <div>
        <label className="mb-2 block text-sm font-medium text-[var(--color-text-primary)]">
          What do you want your bot to do?
        </label>
        <textarea
          value={form.purposeDescription}
          onChange={(e) => updateForm({ purposeDescription: e.target.value })}
          placeholder={placeholder}
          rows={3}
          className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
        />
        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
          The more specific you are, the better we can personalize your bot.
        </p>
      </div>

      {/* Category Chips (optional) */}
      <div>
        <label className="mb-3 block text-sm font-medium text-[var(--color-text-secondary)]">
          Pick a category (optional)
        </label>
        <div className="flex flex-wrap gap-2">
          {visibleCategories.map((category) => (
            <button
              key={category.id}
              onClick={() => toggleCategory(category.id)}
              title={category.description}
              className={cn(
                'rounded-full border px-3 py-1.5 text-sm transition-all',
                form.purposeCategory === category.id
                  ? 'border-cachi-500 bg-cachi-500/15 text-cachi-400'
                  : 'border-[var(--color-border-primary)] bg-[var(--card-bg)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-secondary)]'
              )}
            >
              {category.label}
            </button>
          ))}
          {!expanded && hiddenCount > 0 && (
            <button
              onClick={() => setExpanded(true)}
              className="rounded-full border border-dashed border-[var(--color-border-secondary)] px-3 py-1.5 text-sm text-[var(--color-text-tertiary)] transition-colors hover:text-[var(--color-text-secondary)]"
            >
              +{hiddenCount} more
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
