/**
 * REST API Client for Execution Logs (per-bot + admin)
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

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

  // Handle CSV export (plain text response)
  const contentType = response.headers.get('content-type')
  if (contentType?.includes('text/csv')) {
    return response.text() as unknown as T
  }

  return response.json()
}

// =============================================================================
// EXECUTION LOG TYPES
// =============================================================================

export interface ExecutionLog {
  id: string
  executionType: string
  sourceType: string
  sourceId: string | null
  sourceName: string
  botId: string
  userId: string | null
  chatId: string | null
  trigger: string
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  status: string
  output: string | null
  error: string | null
  exitCode: number | null
  creditsConsumed: number
  tokensUsed: number
  promptTokens: number
  completionTokens: number
  llmCalls: number
  workId: string | null
  workJobId: string | null
}

export interface LogLine {
  id: string
  seq: number
  timestamp: string
  level: string
  content: string
  data: Record<string, unknown> | null
}

export interface ExecutionStats {
  totalRuns: number
  successCount: number
  errorCount: number
  avgDurationMs: number
  totalCredits: number
  totalTokens: number
}

export interface ErrorSpotlight {
  errorType: string
  count: number
  lastSeen: string
  botIds: string[]
}

export interface CostEntry {
  botId: string
  botName: string
  totalCredits: number
  totalTokens: number
  executionCount: number
}

// =============================================================================
// PER-BOT EXECUTION LOG API
// =============================================================================

export interface ListExecutionsParams {
  type?: string
  status?: string
  trigger?: string
  sourceId?: string
  fromDate?: string
  toDate?: string
  limit?: number
  offset?: number
}

export async function getExecutions(
  botId: string,
  params: ListExecutionsParams = {}
): Promise<ExecutionLog[]> {
  const qs = new URLSearchParams()
  if (params.type) qs.set('type', params.type)
  if (params.status) qs.set('status', params.status)
  if (params.trigger) qs.set('trigger', params.trigger)
  if (params.sourceId) qs.set('source_id', params.sourceId)
  if (params.fromDate) qs.set('from_date', params.fromDate)
  if (params.toDate) qs.set('to_date', params.toDate)
  if (params.limit) qs.set('limit', params.limit.toString())
  if (params.offset) qs.set('offset', params.offset.toString())
  return request(`/bots/${botId}/executions?${qs}`)
}

export async function getExecution(botId: string, execId: string): Promise<ExecutionLog> {
  return request(`/bots/${botId}/executions/${execId}`)
}

export async function getExecutionOutput(
  botId: string,
  execId: string
): Promise<{ id: string; output: string | null; error: string | null; status: string }> {
  return request(`/bots/${botId}/executions/${execId}/output`)
}

export async function getExecutionLines(
  botId: string,
  execId: string,
  limit = 100,
  offset = 0
): Promise<LogLine[]> {
  return request(`/bots/${botId}/executions/${execId}/lines?limit=${limit}&offset=${offset}`)
}

export async function getRunningExecutions(botId: string): Promise<ExecutionLog[]> {
  return request(`/bots/${botId}/executions/running`)
}

export async function getExecutionStats(
  botId: string,
  period = '24h'
): Promise<ExecutionStats> {
  return request(`/bots/${botId}/executions/stats?period=${period}`)
}

export async function cancelExecution(
  botId: string,
  execId: string
): Promise<{ cancelled: boolean }> {
  return request(`/bots/${botId}/executions/${execId}/cancel`, { method: 'POST' })
}

// =============================================================================
// ADMIN EXECUTION LOG API
// =============================================================================

export interface AdminListParams {
  type?: string
  status?: string
  botId?: string
  trigger?: string
  fromDate?: string
  toDate?: string
  limit?: number
  offset?: number
}

export async function adminGetExecutions(
  params: AdminListParams = {}
): Promise<ExecutionLog[]> {
  const qs = new URLSearchParams()
  if (params.type) qs.set('type', params.type)
  if (params.status) qs.set('status', params.status)
  if (params.botId) qs.set('bot_id', params.botId)
  if (params.trigger) qs.set('trigger', params.trigger)
  if (params.fromDate) qs.set('from_date', params.fromDate)
  if (params.toDate) qs.set('to_date', params.toDate)
  if (params.limit) qs.set('limit', params.limit.toString())
  if (params.offset) qs.set('offset', params.offset.toString())
  return request(`/admin/executions?${qs}`)
}

export async function adminGetErrorSpotlight(days = 7): Promise<ErrorSpotlight[]> {
  return request(`/admin/executions/errors?days=${days}`)
}

export async function adminGetCostAnalysis(days = 30, limit = 20): Promise<CostEntry[]> {
  return request(`/admin/executions/costs?days=${days}&limit=${limit}`)
}

export async function adminGetStats(period = '24h'): Promise<ExecutionStats> {
  return request(`/admin/executions/stats?period=${period}`)
}

export async function adminGetRunning(): Promise<ExecutionLog[]> {
  return request('/admin/executions/running')
}

export async function adminCancelExecution(execId: string): Promise<{ cancelled: boolean }> {
  return request(`/admin/executions/${execId}/cancel`, { method: 'POST' })
}

export async function adminCancelAll(): Promise<{ cancelledCount: number }> {
  return request('/admin/executions/cancel-all', { method: 'POST' })
}

export async function adminExportCsv(
  botId?: string,
  fromDate?: string,
  toDate?: string
): Promise<string> {
  const qs = new URLSearchParams()
  if (botId) qs.set('bot_id', botId)
  if (fromDate) qs.set('from_date', fromDate)
  if (toDate) qs.set('to_date', toDate)
  return request(`/admin/executions/export?${qs}`)
}
