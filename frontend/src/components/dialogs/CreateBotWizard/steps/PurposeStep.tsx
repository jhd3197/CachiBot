import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { cn } from '../../../../lib/utils'

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
  custom: "Describe exactly what you want your bot to help you with...",
}

export function PurposeStep() {
  const { form, updateForm } = useCreationStore()

  const placeholder = CATEGORY_EXAMPLES[form.purposeCategory] || "Describe what you want your bot to help you with..."

  return (
    <div className="space-y-6">
      {/* Category Selection */}
      <div>
        <label className="mb-3 block text-sm font-medium text-zinc-300">
          What's your bot for?
        </label>
        <div className="grid grid-cols-3 gap-2">
          {PURPOSE_CATEGORIES.map((category) => (
            <button
              key={category.id}
              onClick={() => updateForm({ purposeCategory: category.id })}
              className={cn(
                'flex flex-col items-start rounded-lg border p-3 text-left transition-all',
                form.purposeCategory === category.id
                  ? 'border-cachi-500 bg-cachi-500/10'
                  : 'border-zinc-800 bg-zinc-800/30 hover:border-zinc-700'
              )}
            >
              <span className="text-sm font-medium text-zinc-200">{category.label}</span>
              <span className="text-xs text-zinc-500 line-clamp-1">{category.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Purpose Description */}
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">
          What do you want your bot to do?
        </label>
        <textarea
          value={form.purposeDescription}
          onChange={(e) => updateForm({ purposeDescription: e.target.value })}
          placeholder={placeholder}
          rows={3}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
        />
        <p className="mt-2 text-xs text-zinc-500">
          The more specific you are, the better we can personalize your bot.
        </p>
      </div>
    </div>
  )
}
