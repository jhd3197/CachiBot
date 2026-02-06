/**
 * Simple language detection based on character patterns and common words.
 * Returns ISO 639-1 language code or null if uncertain.
 *
 * This is a lightweight client-side heuristic. For production,
 * consider using a library like franc or server-side detection.
 */

// Common words/patterns for language detection
const LANGUAGE_PATTERNS: Record<string, { words: RegExp[]; chars?: RegExp }> = {
  es: {
    words: [/\b(el|la|los|las|un|una|que|de|en|es|por|para|con|como|pero|este|esta)\b/gi],
    chars: /[ñáéíóúü]/i,
  },
  pt: {
    words: [/\b(o|a|os|as|um|uma|que|de|em|por|para|com|como|mas|este|esta|isso|nao|não)\b/gi],
    chars: /[ãõç]/i,
  },
  fr: {
    words: [/\b(le|la|les|un|une|que|de|en|est|pour|avec|comme|mais|ce|cette|je|tu|il)\b/gi],
    chars: /[éèêëàâîïôùûç]/i,
  },
  de: {
    words: [/\b(der|die|das|ein|eine|und|ist|mit|für|aber|ich|du|sie|wir)\b/gi],
    chars: /[äöüß]/i,
  },
  it: {
    words: [/\b(il|la|lo|gli|le|un|una|che|di|in|per|con|come|ma|questo|questa)\b/gi],
  },
  en: {
    words: [/\b(the|a|an|is|are|was|were|be|been|have|has|had|do|does|did|will|would|could|should|can|may|might|must|shall|this|that|these|those|i|you|he|she|it|we|they)\b/gi],
  },
}

/**
 * Detect the most likely language from a text sample.
 * Accumulates evidence across multiple texts for better accuracy.
 */
export function detectLanguage(texts: string[]): string | null {
  const combined = texts.join(' ').toLowerCase()

  if (combined.length < 10) {
    return null // Not enough text
  }

  const scores: Record<string, number> = {}

  for (const [lang, { words, chars }] of Object.entries(LANGUAGE_PATTERNS)) {
    let score = 0

    // Check for language-specific characters (strong signal)
    if (chars && chars.test(combined)) {
      score += 3
    }

    // Check for common words
    for (const pattern of words) {
      const matches = combined.match(pattern)
      if (matches) {
        score += matches.length
      }
    }

    scores[lang] = score
  }

  // Find language with highest score
  let maxLang: string | null = null
  let maxScore = 0

  for (const [lang, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score
      maxLang = lang
    }
  }

  // Require minimum confidence (at least 2 matches)
  return maxScore >= 2 ? maxLang : null
}

/**
 * Get language display name from ISO code.
 */
export function getLanguageName(code: string): string {
  const names: Record<string, string> = {
    en: 'English',
    es: 'Spanish',
    pt: 'Portuguese',
    fr: 'French',
    de: 'German',
    it: 'Italian',
  }
  return names[code] || code.toUpperCase()
}
