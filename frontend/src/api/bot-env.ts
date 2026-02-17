/**
 * Bot Environment API Client
 *
 * CRUD for per-bot environment variables, platform defaults, and skill configs.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EnvVar {
  key: string
  masked_value: string
  source: string
  updated_at: string
}

export interface ResolvedVar {
  masked_value?: string | null
  value?: string | number | null
  source: string
}

export interface ResolvedEnv {
  resolved: Record<string, ResolvedVar>
  skill_configs: Record<string, Record<string, ResolvedVar>>
}

export interface SkillConfigResponse {
  skill_name: string
  config: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

async function request<T>(
  url: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      return request<T>(url, options, false)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Bot Environment CRUD
// ---------------------------------------------------------------------------

/** List per-bot environment variable overrides (masked). */
export async function getBotEnvVars(botId: string): Promise<EnvVar[]> {
  const data = await request<{ variables: EnvVar[] }>(
    `${API_BASE}/bots/${botId}/environment`
  )
  return data.variables
}

/** Set or update a per-bot environment variable. */
export async function setBotEnvVar(
  botId: string,
  key: string,
  value: string
): Promise<void> {
  await request(`${API_BASE}/bots/${botId}/environment/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  })
}

/** Delete a per-bot environment variable override. */
export async function deleteBotEnvVar(
  botId: string,
  key: string
): Promise<void> {
  await request(`${API_BASE}/bots/${botId}/environment/${encodeURIComponent(key)}`, {
    method: 'DELETE',
  })
}

/** Get fully resolved config for a bot (all layers merged). */
export async function getResolvedEnv(botId: string): Promise<ResolvedEnv> {
  return request(`${API_BASE}/bots/${botId}/environment/resolved`)
}

/** Delete ALL per-bot overrides (reset to defaults). */
export async function resetBotEnv(botId: string): Promise<{ deleted: number }> {
  return request(`${API_BASE}/bots/${botId}/environment`, {
    method: 'DELETE',
  })
}

// ---------------------------------------------------------------------------
// Platform Environment CRUD (admin only)
// ---------------------------------------------------------------------------

/** List platform environment variable defaults (admin only). */
export async function getPlatformEnvVars(platform: string): Promise<EnvVar[]> {
  const data = await request<{ variables: EnvVar[] }>(
    `${API_BASE}/platforms/${platform}/environment`
  )
  return data.variables
}

/** Set a platform environment variable default (admin only). */
export async function setPlatformEnvVar(
  platform: string,
  key: string,
  value: string
): Promise<void> {
  await request(
    `${API_BASE}/platforms/${platform}/environment/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ value }),
    }
  )
}

/** Delete a platform environment variable default (admin only). */
export async function deletePlatformEnvVar(
  platform: string,
  key: string
): Promise<void> {
  await request(
    `${API_BASE}/platforms/${platform}/environment/${encodeURIComponent(key)}`,
    {
      method: 'DELETE',
    }
  )
}

// ---------------------------------------------------------------------------
// Skill Config CRUD
// ---------------------------------------------------------------------------

/** Get skill configuration for a bot. */
export async function getSkillConfig(
  botId: string,
  skillName: string
): Promise<SkillConfigResponse> {
  return request(
    `${API_BASE}/bots/${botId}/skills/${encodeURIComponent(skillName)}/config`
  )
}

/** Set skill configuration for a bot. */
export async function setSkillConfig(
  botId: string,
  skillName: string,
  config: Record<string, unknown>
): Promise<void> {
  await request(
    `${API_BASE}/bots/${botId}/skills/${encodeURIComponent(skillName)}/config`,
    {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }
  )
}

/** Delete skill configuration for a bot. */
export async function deleteSkillConfig(
  botId: string,
  skillName: string
): Promise<void> {
  await request(
    `${API_BASE}/bots/${botId}/skills/${encodeURIComponent(skillName)}/config`,
    {
      method: 'DELETE',
    }
  )
}
