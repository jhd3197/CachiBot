/**
 * Models API client
 */

const API_BASE = '/api'

export interface ModelInfo {
  id: string
  provider: string
  context_window: number | null
  max_output_tokens: number | null
  supports_tool_use: boolean
  supports_vision: boolean
  supports_structured_output: boolean
  is_reasoning: boolean
  pricing: {
    input: number | null
    output: number | null
  } | null
}

export interface ModelsGrouped {
  [provider: string]: ModelInfo[]
}

/**
 * Get all available models grouped by provider
 */
export async function getModels(): Promise<ModelsGrouped> {
  const response = await fetch(`${API_BASE}/models`)
  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.statusText}`)
  }
  const data = await response.json()
  return data.groups || {}
}

/**
 * Get the current default model
 */
export async function getDefaultModel(): Promise<string> {
  const response = await fetch(`${API_BASE}/models/default`)
  if (!response.ok) {
    throw new Error(`Failed to fetch default model: ${response.statusText}`)
  }
  const data = await response.json()
  return data.model
}

/**
 * Set the default model
 */
export async function setDefaultModel(model: string): Promise<void> {
  const response = await fetch(`${API_BASE}/models/default`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
  if (!response.ok) {
    throw new Error(`Failed to set default model: ${response.statusText}`)
  }
}
