import { useState } from 'react'
import { Send, Loader2, User, Bot, MessageCircle } from 'lucide-react'
import { useCreationStore, PURPOSE_CATEGORIES } from '../../../../stores/creation'
import { previewBot } from '../../../../api/client'
import { cn } from '../../../../lib/utils'

export function PreviewStep() {
  const {
    form,
    previewMessages,
    isPreviewLoading,
    addPreviewMessage,
    clearPreviewMessages,
    setPreviewLoading,
  } = useCreationStore()

  const [input, setInput] = useState('')

  // Dynamic sample messages based on category
  const categoryLabel = PURPOSE_CATEGORIES.find(c => c.id === form.purposeCategory)?.label || 'general'
  const sampleMessages = [
    `Hey ${form.name}, what can you help me with?`,
    "What makes you different from other assistants?",
    `Give me a quick tip about ${categoryLabel.toLowerCase()}`,
  ]

  const sendMessage = async (message: string) => {
    if (!message.trim() || isPreviewLoading) return

    addPreviewMessage('user', message)
    setInput('')
    setPreviewLoading(true)

    try {
      const result = await previewBot({
        system_prompt: form.systemPrompt,
        test_message: message,
      })
      addPreviewMessage('assistant', result.response)
    } catch {
      addPreviewMessage('assistant', `Hey! I'm ${form.name}. How can I help you today?`)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  return (
    <div className="flex h-[400px] flex-col">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <MessageCircle className="h-4 w-4 text-cachi-400" />
        <span className="text-sm font-medium text-zinc-300">Chat with {form.name}</span>
      </div>

      {/* Chat area */}
      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        {previewMessages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-cachi-500/10">
              <Bot className="h-7 w-7 text-cachi-400" />
            </div>
            <p className="text-lg font-medium text-zinc-300">{form.name}</p>
            <p className="mt-1 text-sm text-zinc-500">
              See how your bot responds before creating it
            </p>
          </div>
        ) : (
          previewMessages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'flex gap-3',
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              {msg.role === 'assistant' && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cachi-600/20">
                  <Bot className="h-4 w-4 text-cachi-400" />
                </div>
              )}
              <div
                className={cn(
                  'max-w-[80%] rounded-2xl px-4 py-2.5',
                  msg.role === 'user'
                    ? 'bg-cachi-600 text-white'
                    : 'bg-zinc-800 text-zinc-100'
                )}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === 'user' && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-700">
                  <User className="h-4 w-4 text-zinc-300" />
                </div>
              )}
            </div>
          ))
        )}
        {isPreviewLoading && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cachi-600/20">
              <Bot className="h-4 w-4 text-cachi-400" />
            </div>
            <div className="rounded-2xl bg-zinc-800 px-4 py-2.5">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            </div>
          </div>
        )}
      </div>

      {/* Sample messages */}
      {previewMessages.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {sampleMessages.map((msg, i) => (
            <button
              key={i}
              onClick={() => sendMessage(msg)}
              className="rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
            >
              {msg}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Message ${form.name}...`}
          disabled={isPreviewLoading}
          className="h-10 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isPreviewLoading || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-cachi-600 text-white hover:bg-cachi-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>

      {previewMessages.length > 0 && (
        <button
          onClick={clearPreviewMessages}
          className="mt-2 text-xs text-zinc-500 hover:text-zinc-400"
        >
          Clear conversation
        </button>
      )}
    </div>
  )
}
