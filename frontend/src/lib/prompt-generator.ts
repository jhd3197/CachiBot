import type { CreationFlowData, Bot } from '../types'

/**
 * Style presets with their corresponding instructions.
 */
const STYLE_INSTRUCTIONS: Record<string, string> = {
  Professional:
    'Maintain a professional, business-appropriate tone. Be clear, concise, and focused.',
  Casual: 'Be friendly and approachable. Use everyday language and a warm conversational style.',
  Playful: 'Be fun and lighthearted. Bring energy and enthusiasm to conversations.',
  Technical: 'Be precise and detailed. Use domain-specific terminology when appropriate.',
}

/**
 * Emoji usage instructions.
 */
const EMOJI_INSTRUCTIONS: Record<string, string> = {
  yes: 'Feel free to use emojis to express yourself and add personality.',
  no: 'Do not use emojis in your responses. Keep text-only.',
  sometimes: 'Use emojis sparingly, only when they genuinely add value to the message.',
}

/**
 * Language names for system prompt.
 */
const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English',
  es: 'Spanish',
  pt: 'Portuguese',
  fr: 'French',
  de: 'German',
  it: 'Italian',
}

/**
 * Generate a system prompt from bot personality configuration.
 *
 * Keeps the prompt concise (under 500 tokens as per research recommendations)
 * while capturing the essential personality traits.
 */
export function generateSystemPrompt(data: CreationFlowData): string {
  const parts: string[] = []

  // Core identity
  parts.push(`You are ${data.name}, an AI assistant.`)

  // Purpose
  if (data.purposeDescription) {
    parts.push(`Your purpose: ${data.purposeDescription}`)
  }
  if (data.purposeCategory && data.purposeCategory !== 'Other') {
    parts.push(`You specialize in ${data.purposeCategory.toLowerCase()}-related tasks.`)
  }

  // Communication style
  if (data.communicationStyle) {
    const preset = STYLE_INSTRUCTIONS[data.communicationStyle]
    if (preset) {
      parts.push(preset)
    } else {
      // Custom style description
      parts.push(`Communication style: ${data.communicationStyle}`)
    }
  }

  // Emoji usage
  if (data.useEmojis) {
    parts.push(EMOJI_INSTRUCTIONS[data.useEmojis])
  }

  // Language instruction (if detected and not English)
  if (data.detectedLanguage && data.detectedLanguage !== 'en') {
    const langName = LANGUAGE_NAMES[data.detectedLanguage] || data.detectedLanguage
    parts.push(`Always respond in ${langName} unless the user explicitly requests another language.`)
  }

  // Closing guidance
  parts.push('Be helpful, honest, and stay true to your personality.')

  return parts.join('\n\n')
}

/**
 * Regenerate system prompt from bot's personality configuration.
 * Returns null if bot has no personality data (legacy bots).
 */
export function regenerateSystemPrompt(bot: Bot): string | null {
  if (!bot.personality) {
    return null
  }

  return generateSystemPrompt({
    name: bot.name,
    nameSuggestions: [],
    purposeCategory: bot.personality.purposeCategory,
    purposeDescription: bot.personality.purposeDescription,
    communicationStyle: bot.personality.communicationStyle,
    useEmojis: bot.personality.useEmojis,
    detectedLanguage: null,
  })
}
