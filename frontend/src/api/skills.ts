/**
 * Skills API Client for CachiBot
 *
 * Handles skill CRUD operations and bot skill activation.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { SkillDefinition } from '../types'

const API_BASE = '/api'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  // Handle 401 by trying to refresh token
  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      // Retry with new token
      return request<T>(endpoint, options, false)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(
      data.detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// =============================================================================
// SKILL ENDPOINTS
// =============================================================================

/**
 * Get all available skills
 */
export async function getSkills(): Promise<SkillDefinition[]> {
  return request('/skills')
}

/**
 * Get a specific skill by ID
 */
export async function getSkill(id: string): Promise<SkillDefinition> {
  return request(`/skills/${id}`)
}

/**
 * Create a new local skill from markdown content
 */
export async function createSkill(
  content: string,
  filename?: string
): Promise<SkillDefinition> {
  return request('/skills', {
    method: 'POST',
    body: JSON.stringify({ content, filename }),
  })
}

/**
 * Delete a skill by ID
 */
export async function deleteSkill(id: string): Promise<void> {
  return request(`/skills/${id}`, { method: 'DELETE' })
}

/**
 * Install a skill from a URL or skills.sh identifier
 */
export async function installSkill(url: string): Promise<SkillDefinition> {
  return request('/skills/install', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

/**
 * Refresh skills by rescanning local directories
 */
export async function refreshSkills(): Promise<SkillDefinition[]> {
  return request('/skills/refresh', { method: 'POST' })
}

// =============================================================================
// BOT SKILL ENDPOINTS
// =============================================================================

/**
 * Get all activated skills for a bot
 */
export async function getBotSkills(botId: string): Promise<SkillDefinition[]> {
  return request(`/bots/${botId}/skills`)
}

/**
 * Get just the IDs of activated skills for a bot
 */
export async function getBotSkillIds(botId: string): Promise<string[]> {
  return request(`/bots/${botId}/skills/ids`)
}

/**
 * Activate a skill for a bot
 */
export async function activateSkill(
  botId: string,
  skillId: string
): Promise<{ status: string; skill_id: string }> {
  return request(`/bots/${botId}/skills`, {
    method: 'POST',
    body: JSON.stringify({ skillId }),
  })
}

/**
 * Deactivate a skill for a bot
 */
export async function deactivateSkill(
  botId: string,
  skillId: string
): Promise<void> {
  return request(`/bots/${botId}/skills/${skillId}`, { method: 'DELETE' })
}

export { ApiError }
