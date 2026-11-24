/**
 * REST API client for the bot's computer (Mini Vela).
 *
 * C1 exposed status/state: the Docker probe summary, the per-bot computer
 * status, and wake/sleep/stop. C2 adds the live surface: the preview and
 * per-window frames (image bytes with ETag/304), the windows list with the
 * activity line, watch heartbeats, take over / hand back / person input, and
 * the needs-you answer. Everything returns real backend state — no
 * placeholders — and the views (C4) stay hidden while
 * `DockerProbeSummary.available` is false.
 *
 * Access: viewers can read and watch; control actions require
 * operator-or-higher (the server enforces it, matching the side-tasks
 * pattern).
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type {
  BotComputer,
  ComputerFrame,
  ComputerInput,
  ComputerViewsResponse,
  ComputerWatchResponse,
  ComputerWorkspaceResponse,
  DockerProbeSummary,
} from '../types'

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

async function request<T>(endpoint: string, options: RequestInit = {}, retry = true): Promise<T> {
  const url = `${API_BASE}${endpoint}`

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

  return response.json()
}

/**
 * Fetch image bytes (preview or window frame) with the ETag contract:
 * pass the ETag you hold and a 304 answers null (your bytes are current).
 * A 409/404 (computer asleep, nothing to show) throws ApiError — callers
 * decide; nothing is faked.
 */
async function frameRequest(
  endpoint: string,
  etag: string | null,
  retry = true
): Promise<ComputerFrame | null> {
  const headers: Record<string, string> = { ...getAuthHeader() }
  if (etag) {
    headers['If-None-Match'] = etag
  }
  const response = await fetch(`${API_BASE}${endpoint}`, { headers })

  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      return frameRequest(endpoint, etag, false)
    }
  }

  if (response.status === 304) {
    return null
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(
      data.detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  const blob = await response.blob()
  const responseEtag = response.headers.get('ETag')
  return {
    blob,
    etag: responseEtag,
    revision: responseEtag ? responseEtag.replace(/"/g, '') : null,
  }
}

/** Docker probe summary — the UI hides every computer surface when unavailable. */
export async function getComputerStatus(): Promise<DockerProbeSummary> {
  return request('/computer/status')
}

/** Current state of one bot's computer. */
export async function getBotComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer`)
}

/** Turn the computer on (background work; watch `computer_update` events). */
export async function wakeComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/wake`, { method: 'POST' })
}

/** Stop the container, keep the volumes. */
export async function sleepComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/sleep`, { method: 'POST' })
}

/** Stop the computer and mark it off (volumes kept). */
export async function stopComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/stop`, { method: 'POST' })
}

/**
 * The live preview image: the full-desktop frame when the computer's Vela
 * offers it, else the focused/top window's frame. Pass the ETag of the frame
 * you hold; null means 304 (unchanged). Never wakes the computer.
 */
export async function getComputerPreview(
  botId: string,
  etag: string | null = null
): Promise<ComputerFrame | null> {
  return frameRequest(`/bots/${botId}/computer/preview`, etag)
}

/** The open windows (app + title) and the activity line. */
export async function getComputerViews(botId: string): Promise<ComputerViewsResponse> {
  return request(`/bots/${botId}/computer/views`)
}

/** One window's frame, proxied. Pass its ETag; null means 304 (unchanged). */
export async function getComputerViewFrame(
  botId: string,
  viewId: string,
  etag: string | null = null
): Promise<ComputerFrame | null> {
  return frameRequest(`/bots/${botId}/computer/views/${viewId}/frame`, etag)
}

/** A watch heartbeat: the caller counts as watching (~30 s TTL), keeping the
 * computer awake. Send while the computer is on screen; the server forwards
 * it to Vela so its watcher count is right. */
export async function watchComputer(botId: string): Promise<ComputerWatchResponse> {
  return request(`/bots/${botId}/computer/watch`, { method: 'POST' })
}

/** Take over the computer (operator+): the bot waits while you drive. */
export async function takeoverComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/takeover`, { method: 'POST' })
}

/** Hand the computer back (operator+): releases the control lease. */
export async function handbackComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/handback`, { method: 'POST' })
}

/** Send one piece of person input (operator+, only while you hold the
 * take-over): click/right click, scroll, type, key. */
export async function sendComputerInput(
  botId: string,
  input: ComputerInput
): Promise<{ ok: boolean }> {
  return request(`/bots/${botId}/computer/input`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

/** Answer a needs-you (operator+): take over, or skip (the documented
 * closest refusal — an approval is denied; a needs-person pause stops the run). */
export async function respondComputerNeedsYou(
  botId: string,
  action: 'takeover' | 'skip'
): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/needs-you/respond`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
}

/** List one folder of the bot's /workspace (viewer+). Browsing never boots
 * the computer: while it is asleep this throws (409) and callers hide the
 * section. Entries come straight from the computer — nothing is invented. */
export async function getComputerWorkspace(
  botId: string,
  path = ''
): Promise<ComputerWorkspaceResponse> {
  const query = path ? `?path=${encodeURIComponent(path)}` : ''
  return request(`/bots/${botId}/computer/workspace${query}`)
}

/** Open a workspace file in the computer's editor (operator+, design 10).
 * The UI offers the action only while the computer is awake. */
export async function openComputerEditor(botId: string, path: string): Promise<{ ok: boolean }> {
  return request(`/bots/${botId}/computer/editor/open`, {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}
