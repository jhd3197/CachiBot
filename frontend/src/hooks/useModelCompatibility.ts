import { useMemo } from 'react'
import { useModelsStore } from '../stores/models'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  groq: 'Groq',
  grok: 'xAI Grok',
  openrouter: 'OpenRouter',
  moonshot: 'Moonshot AI',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  azure: 'Azure OpenAI',
}

export type CompatibilityStatus = 'loading' | 'compatible' | 'alternative' | 'unavailable' | 'no_model'

export interface ModelCompatibility {
  status: CompatibilityStatus
  templateModel: string
  provider: string
  providerLabel: string
  alternatives: string[]
  defaultModel: string
}

function providerLabel(key: string): string {
  return PROVIDER_LABELS[key] || key.charAt(0).toUpperCase() + key.slice(1)
}

export function useModelCompatibility(modelId: string | undefined): ModelCompatibility {
  const { groups, defaultModel, loading } = useModelsStore()

  return useMemo(() => {
    const base: ModelCompatibility = {
      status: 'no_model',
      templateModel: modelId || '',
      provider: '',
      providerLabel: '',
      alternatives: [],
      defaultModel,
    }

    if (!modelId) return base

    if (loading) return { ...base, status: 'loading' }

    // Parse provider/model-name
    const slashIdx = modelId.indexOf('/')
    const provider = slashIdx > 0 ? modelId.slice(0, slashIdx) : ''

    base.provider = provider
    base.providerLabel = provider ? providerLabel(provider) : ''

    if (!provider) {
      // No provider prefix — check all groups for an exact match
      for (const items of Object.values(groups)) {
        if (items.some((m) => m.id === modelId)) {
          return { ...base, status: 'compatible' }
        }
      }
      return { ...base, status: 'unavailable' }
    }

    const providerModels = groups[provider]

    if (!providerModels || providerModels.length === 0) {
      return { ...base, status: 'unavailable' }
    }

    // Exact match
    if (providerModels.some((m) => m.id === modelId)) {
      return { ...base, status: 'compatible' }
    }

    // Provider exists but model not found — list alternatives
    return {
      ...base,
      status: 'alternative',
      alternatives: providerModels.map((m) => m.id),
    }
  }, [modelId, groups, defaultModel, loading])
}
