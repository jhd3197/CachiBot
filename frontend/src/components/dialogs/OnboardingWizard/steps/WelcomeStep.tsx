import { Bot, Sparkles, Key, Palette } from 'lucide-react'

export function WelcomeStep() {
  return (
    <div className="flex flex-col items-center py-8 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-accent-600/20">
        <Bot className="h-10 w-10 text-accent-500" />
      </div>

      <h2 className="text-2xl font-bold text-zinc-100">Welcome to CachiBot</h2>
      <p className="mt-2 max-w-md text-zinc-400">
        Your security-focused AI agent platform. Let's get you set up in a few quick steps.
      </p>

      <div className="mt-8 grid w-full max-w-sm gap-3">
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/50 p-3 text-left">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/20">
            <Key className="h-4 w-4 text-blue-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200">Connect a Provider</p>
            <p className="text-xs text-zinc-500">Add an API key to get started</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/50 p-3 text-left">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-purple-500/20">
            <Sparkles className="h-4 w-4 text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200">Pick a Model</p>
            <p className="text-xs text-zinc-500">Choose your default AI model</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/50 p-3 text-left">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-500/20">
            <Palette className="h-4 w-4 text-orange-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200">Personalize</p>
            <p className="text-xs text-zinc-500">Set your theme and preferences</p>
          </div>
        </div>
      </div>
    </div>
  )
}
