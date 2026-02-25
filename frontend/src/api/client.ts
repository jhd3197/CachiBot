/**
 * REST API Client for Cachibot
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

  return response.json()
}

// Health check
export interface HealthInfo {
  status: string
  version: string
  build: string
  python: string
  platform: string
  desktop: boolean
  distribution: string
}

export async function checkHealth(): Promise<HealthInfo> {
  return request('/health')
}

// Mobile pairing
export interface PairTokenResponse {
  token: string
  url: string
  urls: string[]
  expires: number
}

export async function createMobilePairToken(): Promise<PairTokenResponse> {
  return request('/auth/mobile-pair', { method: 'POST' })
}

export interface FirewallStatus {
  platform: string
  needed: boolean
  enabled: boolean | null
  port: string
}

export async function getFirewallStatus(): Promise<FirewallStatus> {
  return request('/auth/mobile-pair/firewall')
}

export async function enableFirewallRule(): Promise<{ success: boolean; message: string }> {
  return request('/auth/mobile-pair/firewall', { method: 'POST' })
}

// Coding agents discovery
import type { CodingAgentsResponse } from '../types'

export async function getCodingAgents(): Promise<CodingAgentsResponse> {
  return request('/coding-agents')
}

// Config
export async function getConfig(): Promise<{
  agent: {
    model: string
    max_iterations: number
    approve_actions: boolean
    temperature: number
  }
  sandbox: {
    allowed_imports: string[]
    timeout_seconds: number
    max_output_length: number
  }
  display: {
    show_thinking: boolean
    show_cost: boolean
    style: string
  }
  workspace_path: string
  timezone: string
}> {
  return request('/config')
}

export async function updateConfig(updates: {
  model?: string
  max_iterations?: number
  approve_actions?: boolean
  temperature?: number
  show_thinking?: boolean
  show_cost?: boolean
}): Promise<ReturnType<typeof getConfig>> {
  return request('/config', {
    method: 'PUT',
    body: JSON.stringify(updates),
  })
}

// Chat history
export async function getChatHistory(
  limit = 50,
  offset = 0
): Promise<{
  messages: Array<{
    id: string
    role: string
    content: string
    timestamp: string
    metadata: Record<string, unknown>
  }>
  total: number
}> {
  return request(`/chat/history?limit=${limit}&offset=${offset}`)
}

export async function clearChatHistory(): Promise<{ status: string }> {
  return request('/chat/history', { method: 'DELETE' })
}

// Bot creation
export async function generateBotNames(exclude: string[] = []): Promise<string[]> {
  const response = await request<{ names: string[] }>('/creation/names', {
    method: 'POST',
    body: JSON.stringify({ count: 4, exclude }),
  })
  return response.names
}

// Name with meaning type
export interface NameWithMeaning {
  name: string
  meaning: string
}

// Names with meanings request
export interface NamesWithMeaningsRequest {
  count?: number
  exclude?: string[]
  purpose?: string
  personality?: string
}

// Generate names with meanings (non-streaming fallback)
export async function generateBotNamesWithMeanings(
  options: NamesWithMeaningsRequest = {}
): Promise<NameWithMeaning[]> {
  const response = await request<{ names: NameWithMeaning[] }>('/creation/names-with-meanings', {
    method: 'POST',
    body: JSON.stringify({
      count: options.count ?? 4,
      exclude: options.exclude ?? [],
      purpose: options.purpose,
      personality: options.personality,
    }),
  })
  return response.names
}

// Follow-up questions
export interface FollowUpQuestion {
  id: string
  question: string
  placeholder: string
}

export interface GenerateQuestionsRequest {
  category: string
  description: string
}

// Non-streaming fallback
export async function generateFollowUpQuestions(
  data: GenerateQuestionsRequest
): Promise<FollowUpQuestion[]> {
  const response = await request<{ questions: FollowUpQuestion[] }>('/creation/follow-up-questions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
  return response.questions
}

// =============================================================================
// SSE STREAMING HELPERS
// =============================================================================

interface SSEEvent {
  event: string
  data: unknown
}

/**
 * Generic SSE fetch for POST endpoints.
 * Yields parsed {event, data} objects from the SSE stream.
 */
async function* fetchSSE(
  endpoint: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const url = `${API_BASE}${endpoint}`

  let response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(body),
    signal,
  })

  // Handle 401 by trying to refresh token (same as request())
  if (response.status === 401) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(body),
        signal,
      })
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(
      data.detail || `SSE request failed: ${response.statusText}`,
      response.status,
      data,
    )
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Parse complete SSE events from buffer
      const parts = buffer.split('\n\n')
      // Last part may be incomplete — keep it in buffer
      buffer = parts.pop() || ''

      for (const part of parts) {
        if (!part.trim()) continue

        let eventType = 'message'
        let eventData = ''

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6)
          }
        }

        if (eventData) {
          try {
            yield { event: eventType, data: JSON.parse(eventData) }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * Stream bot name suggestions with meanings via SSE.
 * Calls onName for each name as it arrives, onDone when complete.
 */
export async function streamBotNamesWithMeanings(
  options: NamesWithMeaningsRequest,
  callbacks: {
    onName: (name: NameWithMeaning) => void
    onDone: () => void
    onError: (error: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  try {
    for await (const { event, data } of fetchSSE(
      '/creation/names-with-meanings/stream',
      {
        count: options.count ?? 4,
        exclude: options.exclude ?? [],
        purpose: options.purpose,
        personality: options.personality,
      },
      signal,
    )) {
      if (event === 'name') {
        callbacks.onName(data as NameWithMeaning)
      } else if (event === 'done') {
        callbacks.onDone()
      } else if (event === 'error') {
        callbacks.onError((data as { error: string }).error)
      }
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    callbacks.onError(err instanceof Error ? err.message : 'Stream failed')
  }
}

/**
 * Stream follow-up questions via SSE.
 * Calls onQuestion for each question as it arrives.
 */
export async function streamFollowUpQuestions(
  data: GenerateQuestionsRequest,
  callbacks: {
    onQuestion: (question: FollowUpQuestion) => void
    onDone: () => void
    onError: (error: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  try {
    for await (const { event, data: eventData } of fetchSSE(
      '/creation/follow-up-questions/stream',
      data,
      signal,
    )) {
      if (event === 'question') {
        callbacks.onQuestion(eventData as FollowUpQuestion)
      } else if (event === 'done') {
        callbacks.onDone()
      } else if (event === 'error') {
        callbacks.onError((eventData as { error: string }).error)
      }
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    callbacks.onError(err instanceof Error ? err.message : 'Stream failed')
  }
}

// Full prompt generation
export interface FollowUpAnswer {
  question: string
  answer: string
}

export interface GenerateFullPromptRequest {
  name: string
  name_meaning: string
  purpose_category: string
  purpose_description: string
  follow_up_answers: FollowUpAnswer[]
  communication_style: string
  use_emojis: 'yes' | 'no' | 'sometimes'
}

export async function generateFullPrompt(
  data: GenerateFullPromptRequest
): Promise<SuggestPromptResponse> {
  return request('/creation/generate-prompt', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// AI-assisted bot creation
export interface SuggestPromptRequest {
  purpose_category: string
  purpose_description: string
  communication_style?: string
  use_emojis?: 'yes' | 'no' | 'sometimes'
  model?: string
}

export interface SuggestPromptResponse {
  system_prompt: string
  suggested_name: string
  suggested_description: string
}

export async function suggestPrompt(data: SuggestPromptRequest): Promise<SuggestPromptResponse> {
  return request('/creation/suggest-prompt', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface RefinePromptRequest {
  current_prompt: string
  feedback: string
  model?: string
}

export interface RefinePromptResponse {
  system_prompt: string
  changes_made: string
}

export async function refinePrompt(data: RefinePromptRequest): Promise<RefinePromptResponse> {
  return request('/creation/refine-prompt', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface PreviewBotRequest {
  system_prompt: string
  test_message: string
  model?: string
}

export interface PreviewBotResponse {
  response: string
}

export async function previewBot(data: PreviewBotRequest): Promise<PreviewBotResponse> {
  return request('/creation/preview-bot', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Creation context analysis
export interface SuggestedTodo {
  title: string
  notes: string
}

export interface SuggestedSchedule {
  name: string
  description: string
  frequency: string
}

export interface AnalyzeContextRequest {
  purpose_category: string
  purpose_description: string
  follow_up_answers: FollowUpAnswer[]
  system_prompt: string
  bot_name: string
}

export interface AnalyzeContextResponse {
  user_context: string
  suggested_todos: SuggestedTodo[]
  suggested_schedules: SuggestedSchedule[]
}

export async function analyzeCreationContext(
  data: AnalyzeContextRequest
): Promise<AnalyzeContextResponse> {
  return request('/creation/analyze-context', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Bot sync (for platform connections)
export interface BotSyncData {
  id: string
  name: string
  description?: string
  icon?: string
  color?: string
  model: string
  models?: Record<string, string>
  systemPrompt: string
  capabilities?: Record<string, boolean>
  createdAt: string
  updatedAt: string
}

export async function syncBot(bot: BotSyncData): Promise<BotSyncData> {
  return request(`/bots/${bot.id}`, {
    method: 'PUT',
    body: JSON.stringify(bot),
  })
}

/** Fetch a single bot from the backend by ID. */
export async function getBackendBot(botId: string): Promise<BotSyncData> {
  return request(`/bots/${botId}`)
}

export async function deleteBackendBot(botId: string): Promise<void> {
  return request(`/bots/${botId}`, { method: 'DELETE' })
}

// Bot export/import
export interface BotExportData {
  version: string
  exportedAt: string
  bot: {
    name: string
    description?: string
    icon?: string
    color?: string
    model: string
    systemPrompt: string
    tools?: string[]
    capabilities?: Record<string, boolean>
    skills?: string[]
  }
}

export async function exportBot(botId: string): Promise<BotExportData> {
  return request(`/bots/${botId}/export`)
}

export interface BotImportResponse {
  id: string
  name: string
  imported: boolean
  message: string
}

export async function importBot(data: BotExportData): Promise<BotImportResponse> {
  return request('/bots/import', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Platform chats (Telegram, Discord conversations synced from backend)
export interface PlatformChat {
  id: string
  botId: string
  title: string
  platform: string | null
  platformChatId: string | null
  pinned: boolean
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface PlatformMessage {
  id: string
  chatId: string
  role: string
  content: string
  timestamp: string
  metadata: Record<string, unknown>
}

export async function getPlatformChats(botId: string): Promise<PlatformChat[]> {
  return request(`/bots/${botId}/chats`)
}

export async function getPlatformChatMessages(
  botId: string,
  chatId: string,
  limit = 50
): Promise<PlatformMessage[]> {
  return request(`/bots/${botId}/chats/${chatId}/messages?limit=${limit}`)
}

export async function deletePlatformChat(botId: string, chatId: string): Promise<void> {
  return request(`/bots/${botId}/chats/${chatId}`, { method: 'DELETE' })
}

export async function clearChatMessages(botId: string, chatId: string): Promise<ClearBotDataResponse> {
  return request(`/bots/${botId}/chats/${chatId}/_clear-messages`, { method: 'POST' })
}

export interface ClearBotDataResponse {
  chats_deleted: number
  messages_deleted: number
}

export async function clearBotPlatformData(botId: string): Promise<ClearBotDataResponse> {
  return request(`/bots/${botId}/chats/_clear`, { method: 'POST' })
}

export interface ArchiveResponse {
  archived: boolean
  chat_id: string
}

export async function archivePlatformChat(botId: string, chatId: string): Promise<ArchiveResponse> {
  return request(`/bots/${botId}/chats/${chatId}/_archive`, { method: 'POST' })
}

export async function unarchivePlatformChat(botId: string, chatId: string): Promise<ArchiveResponse> {
  return request(`/bots/${botId}/chats/${chatId}/_unarchive`, { method: 'POST' })
}

export async function getPlatformChatsIncludingArchived(botId: string): Promise<PlatformChat[]> {
  return request(`/bots/${botId}/chats?include_archived=true`)
}

// =============================================================================
// WORK MANAGEMENT API
// =============================================================================

import type {
  BotFunction,
  Schedule,
  Work,
  WorkTask,
  WorkJob,
  Todo,
  FunctionStep,
  FunctionParameter,
  Priority,
  ScheduleType,
} from '../types'

// Function types
export interface CreateFunctionRequest {
  name: string
  description?: string
  steps: Omit<FunctionStep, 'order'>[]
  parameters?: FunctionParameter[]
  tags?: string[]
}

export interface UpdateFunctionRequest {
  name?: string
  description?: string
  steps?: Omit<FunctionStep, 'order'>[]
  parameters?: FunctionParameter[]
  tags?: string[]
}

// Schedule types
export interface CreateScheduleRequest {
  name: string
  description?: string
  functionId?: string
  functionParams?: Record<string, unknown>
  scheduleType?: ScheduleType
  cronExpression?: string
  intervalSeconds?: number
  runAt?: string
  eventTrigger?: string
  timezone?: string
  maxConcurrent?: number
  catchUp?: boolean
}

export interface UpdateScheduleRequest {
  name?: string
  description?: string
  functionId?: string
  functionParams?: Record<string, unknown>
  cronExpression?: string
  intervalSeconds?: number
  runAt?: string
  eventTrigger?: string
  timezone?: string
  enabled?: boolean
  maxConcurrent?: number
  catchUp?: boolean
}

// Work types
export interface CreateWorkRequest {
  title: string
  description?: string
  goal?: string
  chatId?: string
  functionId?: string
  scheduleId?: string
  parentWorkId?: string
  priority?: Priority
  dueAt?: string
  context?: Record<string, unknown>
  tags?: string[]
  tasks?: CreateTaskRequest[]
}

export interface UpdateWorkRequest {
  title?: string
  description?: string
  goal?: string
  status?: string
  priority?: Priority
  progress?: number
  dueAt?: string
  result?: unknown
  error?: string
  context?: Record<string, unknown>
  tags?: string[]
}

// Task types
export interface CreateTaskRequest {
  title: string
  description?: string
  action?: string
  order?: number
  dependsOn?: string[]
  priority?: Priority
  maxRetries?: number
  timeoutSeconds?: number
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  action?: string
  order?: number
  dependsOn?: string[]
  status?: string
  priority?: Priority
  maxRetries?: number
  timeoutSeconds?: number
  result?: unknown
  error?: string
}

// Todo types
export interface CreateTodoRequest {
  title: string
  notes?: string
  chatId?: string
  priority?: Priority
  remindAt?: string
  tags?: string[]
}

export interface UpdateTodoRequest {
  title?: string
  notes?: string
  status?: string
  priority?: Priority
  remindAt?: string
  tags?: string[]
}

export interface ConvertTodoRequest {
  toWork?: boolean
  workTitle?: string
  workDescription?: string
  priority?: Priority
}

// =============================================================================
// FUNCTION API
// =============================================================================

export async function getFunctions(botId: string): Promise<BotFunction[]> {
  return request(`/bots/${botId}/functions`)
}

export async function getFunction(botId: string, functionId: string): Promise<BotFunction> {
  return request(`/bots/${botId}/functions/${functionId}`)
}

export async function createFunction(botId: string, data: CreateFunctionRequest): Promise<BotFunction> {
  return request(`/bots/${botId}/functions`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateFunction(
  botId: string,
  functionId: string,
  data: UpdateFunctionRequest
): Promise<BotFunction> {
  return request(`/bots/${botId}/functions/${functionId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteFunction(botId: string, functionId: string): Promise<void> {
  return request(`/bots/${botId}/functions/${functionId}`, { method: 'DELETE' })
}

export async function runFunction(
  botId: string,
  functionId: string,
  params?: Record<string, unknown>
): Promise<Work> {
  return request(`/bots/${botId}/functions/${functionId}/run`, {
    method: 'POST',
    body: JSON.stringify(params || {}),
  })
}

// =============================================================================
// SCHEDULE API
// =============================================================================

export async function getSchedules(botId: string): Promise<Schedule[]> {
  return request(`/bots/${botId}/schedules`)
}

export async function getSchedule(botId: string, scheduleId: string): Promise<Schedule> {
  return request(`/bots/${botId}/schedules/${scheduleId}`)
}

export async function createSchedule(botId: string, data: CreateScheduleRequest): Promise<Schedule> {
  return request(`/bots/${botId}/schedules`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateSchedule(
  botId: string,
  scheduleId: string,
  data: UpdateScheduleRequest
): Promise<Schedule> {
  return request(`/bots/${botId}/schedules/${scheduleId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function toggleSchedule(botId: string, scheduleId: string): Promise<Schedule> {
  return request(`/bots/${botId}/schedules/${scheduleId}/toggle`, { method: 'POST' })
}

export async function deleteSchedule(botId: string, scheduleId: string): Promise<void> {
  return request(`/bots/${botId}/schedules/${scheduleId}`, { method: 'DELETE' })
}

// =============================================================================
// WORK API
// =============================================================================

export async function getWork(botId: string, status?: string, limit = 50): Promise<Work[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  params.set('limit', limit.toString())
  return request(`/bots/${botId}/work?${params}`)
}

export async function getActiveWork(botId: string): Promise<Work[]> {
  return request(`/bots/${botId}/work/active`)
}

export async function getWorkById(botId: string, workId: string): Promise<Work> {
  return request(`/bots/${botId}/work/${workId}`)
}

export async function createWork(botId: string, data: CreateWorkRequest): Promise<Work> {
  return request(`/bots/${botId}/work`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateWork(botId: string, workId: string, data: UpdateWorkRequest): Promise<Work> {
  return request(`/bots/${botId}/work/${workId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function startWork(botId: string, workId: string): Promise<Work> {
  return request(`/bots/${botId}/work/${workId}/start`, { method: 'POST' })
}

export async function completeWork(botId: string, workId: string, result?: unknown): Promise<Work> {
  return request(`/bots/${botId}/work/${workId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ result }),
  })
}

export async function failWork(botId: string, workId: string, error?: string): Promise<Work> {
  return request(`/bots/${botId}/work/${workId}/fail`, {
    method: 'POST',
    body: JSON.stringify({ error }),
  })
}

export async function deleteWork(botId: string, workId: string): Promise<void> {
  return request(`/bots/${botId}/work/${workId}`, { method: 'DELETE' })
}

// =============================================================================
// TASK API
// =============================================================================

export async function getTasks(botId: string, workId: string): Promise<WorkTask[]> {
  return request(`/bots/${botId}/work/${workId}/tasks`)
}

export async function getReadyTasks(botId: string, workId: string): Promise<WorkTask[]> {
  return request(`/bots/${botId}/work/${workId}/tasks/ready`)
}

export async function getTask(botId: string, taskId: string): Promise<WorkTask> {
  return request(`/bots/${botId}/tasks/${taskId}`)
}

export async function createTask(botId: string, workId: string, data: CreateTaskRequest): Promise<WorkTask> {
  return request(`/bots/${botId}/work/${workId}/tasks`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateTask(botId: string, taskId: string, data: UpdateTaskRequest): Promise<WorkTask> {
  return request(`/bots/${botId}/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function startTask(botId: string, taskId: string): Promise<WorkTask> {
  return request(`/bots/${botId}/tasks/${taskId}/start`, { method: 'POST' })
}

export async function completeTask(botId: string, taskId: string, result?: unknown): Promise<WorkTask> {
  return request(`/bots/${botId}/tasks/${taskId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ result }),
  })
}

export async function failTask(botId: string, taskId: string, error?: string): Promise<WorkTask> {
  return request(`/bots/${botId}/tasks/${taskId}/fail`, {
    method: 'POST',
    body: JSON.stringify({ error }),
  })
}

export async function deleteTask(botId: string, taskId: string): Promise<void> {
  return request(`/bots/${botId}/tasks/${taskId}`, { method: 'DELETE' })
}

// =============================================================================
// JOB API
// =============================================================================

export async function getJobsForTask(botId: string, taskId: string): Promise<WorkJob[]> {
  return request(`/bots/${botId}/tasks/${taskId}/jobs`)
}

export async function getJobsForWork(botId: string, workId: string): Promise<WorkJob[]> {
  return request(`/bots/${botId}/work/${workId}/jobs`)
}

export async function getRunningJobs(botId: string): Promise<WorkJob[]> {
  return request(`/bots/${botId}/jobs/running`)
}

export async function getJob(botId: string, jobId: string): Promise<WorkJob> {
  return request(`/bots/${botId}/jobs/${jobId}`)
}

export async function appendJobLog(
  botId: string,
  jobId: string,
  level: string,
  message: string,
  data?: unknown
): Promise<WorkJob> {
  return request(`/bots/${botId}/jobs/${jobId}/log`, {
    method: 'POST',
    body: JSON.stringify({ level, message, data }),
  })
}

export async function updateJobProgress(botId: string, jobId: string, progress: number): Promise<WorkJob> {
  return request(`/bots/${botId}/jobs/${jobId}/progress?progress=${progress}`, { method: 'PATCH' })
}

// =============================================================================
// TODO API
// =============================================================================

export async function getTodos(botId: string, status?: string, limit = 50): Promise<Todo[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  params.set('limit', limit.toString())
  return request(`/bots/${botId}/todos?${params}`)
}

export async function getOpenTodos(botId: string): Promise<Todo[]> {
  return request(`/bots/${botId}/todos/open`)
}

export async function getTodo(botId: string, todoId: string): Promise<Todo> {
  return request(`/bots/${botId}/todos/${todoId}`)
}

export async function createTodo(botId: string, data: CreateTodoRequest): Promise<Todo> {
  return request(`/bots/${botId}/todos`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateTodo(botId: string, todoId: string, data: UpdateTodoRequest): Promise<Todo> {
  return request(`/bots/${botId}/todos/${todoId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function markTodoDone(botId: string, todoId: string): Promise<Todo> {
  return request(`/bots/${botId}/todos/${todoId}/done`, { method: 'POST' })
}

export async function dismissTodo(botId: string, todoId: string): Promise<Todo> {
  return request(`/bots/${botId}/todos/${todoId}/dismiss`, { method: 'POST' })
}

export async function convertTodoToWork(botId: string, todoId: string, data?: ConvertTodoRequest): Promise<Work> {
  return request(`/bots/${botId}/todos/${todoId}/convert`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function deleteTodo(botId: string, todoId: string): Promise<void> {
  return request(`/bots/${botId}/todos/${todoId}`, { method: 'DELETE' })
}

// =============================================================================
// MARKETPLACE API
// =============================================================================

// Remote marketplace configuration
const REMOTE_MARKETPLACE_URL = import.meta.env.VITE_MARKETPLACE_URL || ''
const MARKETPLACE_CACHE_KEY = 'cachibot_marketplace_cache'
const MARKETPLACE_CACHE_TTL = 5 * 60 * 1000 // 5 minutes

interface CacheEntry<T> {
  data: T
  timestamp: number
}

function getMarketplaceCache<T>(key: string): T | null {
  try {
    const cached = localStorage.getItem(`${MARKETPLACE_CACHE_KEY}_${key}`)
    if (!cached) return null

    const entry: CacheEntry<T> = JSON.parse(cached)
    if (Date.now() - entry.timestamp > MARKETPLACE_CACHE_TTL) {
      localStorage.removeItem(`${MARKETPLACE_CACHE_KEY}_${key}`)
      return null
    }
    return entry.data
  } catch {
    return null
  }
}

function setMarketplaceCache<T>(key: string, data: T): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now() }
    localStorage.setItem(`${MARKETPLACE_CACHE_KEY}_${key}`, JSON.stringify(entry))
  } catch {
    // Ignore cache errors (quota exceeded, etc.)
  }
}

export interface MarketplaceTemplate {
  id: string
  name: string
  description: string
  icon: string
  color: string
  category: string
  tags: string[]
  model: string
  system_prompt: string
  tools: string[]
  rating: number
  downloads: number
}

export interface MarketplaceCategory {
  id: string
  name: string
  description: string
  count: number
}

export interface TemplateListResponse {
  templates: MarketplaceTemplate[]
  total: number
  source?: 'local' | 'remote'
}

export interface InstallTemplateResponse {
  bot_id: string
  name: string
  installed: boolean
  message: string
}

/**
 * Fetch templates from remote cachibot.com marketplace.
 * Returns null if fetch fails or remote is not configured.
 */
async function fetchRemoteTemplates(
  category?: string,
  search?: string
): Promise<TemplateListResponse | null> {
  if (!REMOTE_MARKETPLACE_URL) return null

  try {
    const cacheKey = `remote_templates_${category || ''}_${search || ''}`

    // Check cache first (only for non-search)
    if (!search) {
      const cached = getMarketplaceCache<TemplateListResponse>(cacheKey)
      if (cached) return { ...cached, source: 'remote' }
    }

    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (search) params.set('search', search)

    const queryString = params.toString()
    const url = `${REMOTE_MARKETPLACE_URL}/marketplace/templates${queryString ? `?${queryString}` : ''}`

    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) return null

    const data: TemplateListResponse = await response.json()

    // Cache non-search results
    if (!search) {
      setMarketplaceCache(cacheKey, data)
    }

    return { ...data, source: 'remote' }
  } catch (err) {
    console.warn('Failed to fetch from remote marketplace:', err)
    return null
  }
}

/**
 * Fetch a single template from remote marketplace.
 */
async function fetchRemoteTemplate(templateId: string): Promise<MarketplaceTemplate | null> {
  if (!REMOTE_MARKETPLACE_URL) return null

  try {
    const cacheKey = `remote_template_${templateId}`
    const cached = getMarketplaceCache<MarketplaceTemplate>(cacheKey)
    if (cached) return cached

    const url = `${REMOTE_MARKETPLACE_URL}/marketplace/templates/${templateId}`
    const response = await fetch(url)

    if (!response.ok) return null

    const data: MarketplaceTemplate = await response.json()
    setMarketplaceCache(cacheKey, data)
    return data
  } catch (err) {
    console.warn('Failed to fetch template from remote marketplace:', err)
    return null
  }
}

/**
 * Fetch categories from remote marketplace.
 */
async function fetchRemoteCategories(): Promise<MarketplaceCategory[] | null> {
  if (!REMOTE_MARKETPLACE_URL) return null

  try {
    const cacheKey = 'remote_categories'
    const cached = getMarketplaceCache<MarketplaceCategory[]>(cacheKey)
    if (cached) return cached

    const url = `${REMOTE_MARKETPLACE_URL}/marketplace/categories`
    const response = await fetch(url)

    if (!response.ok) return null

    const data: MarketplaceCategory[] = await response.json()
    setMarketplaceCache(cacheKey, data)
    return data
  } catch (err) {
    console.warn('Failed to fetch categories from remote marketplace:', err)
    return null
  }
}

/**
 * Get marketplace templates.
 * If VITE_MARKETPLACE_URL is set, tries remote first with fallback to local API.
 */
export async function getMarketplaceTemplates(
  category?: string,
  search?: string
): Promise<TemplateListResponse> {
  // Try remote first if configured
  const remote = await fetchRemoteTemplates(category, search)
  if (remote) return remote

  // Fall back to local API
  try {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (search) params.set('search', search)
    const result = await request<TemplateListResponse>(`/marketplace/templates?${params}`)
    return { ...result, source: 'local' }
  } catch {
    return { templates: [], total: 0, source: 'local' }
  }
}

/**
 * Get a single marketplace template.
 * Tries remote first, falls back to local API.
 */
export async function getMarketplaceTemplate(templateId: string): Promise<MarketplaceTemplate | null> {
  // Try remote first
  const remote = await fetchRemoteTemplate(templateId)
  if (remote) return remote

  // Fall back to local
  try {
    return await request(`/marketplace/templates/${templateId}`)
  } catch {
    return null
  }
}

/**
 * Install a template to create a new bot.
 * Always uses the local API since it needs to create the bot locally.
 */
export async function installMarketplaceTemplate(templateId: string): Promise<InstallTemplateResponse> {
  return request(`/marketplace/templates/${templateId}/install`, { method: 'POST' })
}

/**
 * Get marketplace categories.
 * Tries remote first, falls back to local API.
 */
export async function getMarketplaceCategories(): Promise<MarketplaceCategory[]> {
  // Try remote first
  const remote = await fetchRemoteCategories()
  if (remote) return remote

  // Fall back to local
  try {
    return await request('/marketplace/categories')
  } catch {
    return []
  }
}

/**
 * Get room marketplace categories.
 * Tries remote first, falls back to local API.
 */
export async function getRoomMarketplaceCategories(): Promise<MarketplaceCategory[]> {
  // Try remote first
  if (REMOTE_MARKETPLACE_URL) {
    try {
      const cacheKey = 'remote_room_categories'
      const cached = getRoomMarketplaceCache<MarketplaceCategory[]>(cacheKey)
      if (cached) return cached

      const url = `${REMOTE_MARKETPLACE_URL}/marketplace/room-categories`
      const response = await fetch(url)
      if (response.ok) {
        const data: MarketplaceCategory[] = await response.json()
        setRoomMarketplaceCache(cacheKey, data)
        return data
      }
    } catch {
      // Fall through to local
    }
  }

  // Fall back to local
  try {
    return await request('/marketplace/room-categories')
  } catch {
    return []
  }
}

// =============================================================================
// UPDATE API
// =============================================================================

export interface UpdateCheckInfo {
  current_version: string
  latest_stable: string | null
  latest_prerelease: string | null
  update_available: boolean
  prerelease_available: boolean
  release_notes: string | null
  release_url: string | null
  published_at: string | null
  is_docker: boolean
}

export interface UpdateApplyRequest {
  target_version?: string
  include_prerelease?: boolean
}

export interface UpdateApplyResponse {
  success: boolean
  old_version: string
  new_version: string
  message: string
  restart_required: boolean
  pip_output: string
}

export interface UpdateRestartResponse {
  restarting: boolean
  message: string
}

export async function checkForUpdate(force = false): Promise<UpdateCheckInfo> {
  return request(`/update/check?force=${force}`)
}

export async function applyUpdate(data?: UpdateApplyRequest): Promise<UpdateApplyResponse> {
  return request('/update/apply', {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function restartServer(): Promise<UpdateRestartResponse> {
  return request('/update/restart', { method: 'POST' })
}

// =============================================================================
// SETUP API (Onboarding: Database + SMTP)
// =============================================================================

export interface DatabaseTestRequest {
  host: string
  port: number
  database: string
  username: string
  password: string
}

export interface DatabaseTestResponse {
  success: boolean
  message: string
  db_version: string
}

export interface DatabaseSetupRequest {
  db_type: 'sqlite' | 'postgresql'
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
}

export interface DatabaseStatusResponse {
  db_type: string
  url_configured: boolean
  restart_required: boolean
}

export interface SmtpTestRequest {
  host: string
  port: number
  username?: string
  password?: string
  use_tls: boolean
  from_address?: string
  send_test_to?: string
}

export interface SmtpTestResponse {
  success: boolean
  message: string
}

export interface SmtpSetupRequest {
  host: string
  port: number
  username?: string
  password?: string
  from_address?: string
  use_tls: boolean
}

export interface SmtpStatusResponse {
  configured: boolean
  host: string
  port: number
  from_address: string
  use_tls: boolean
}

export async function getDatabaseStatus(): Promise<DatabaseStatusResponse> {
  return request('/setup/database/status')
}

export async function testDatabaseConnection(data: DatabaseTestRequest): Promise<DatabaseTestResponse> {
  return request('/setup/database/test', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function saveDatabaseConfig(data: DatabaseSetupRequest): Promise<DatabaseStatusResponse> {
  return request('/setup/database/save', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getSmtpStatus(): Promise<SmtpStatusResponse> {
  return request('/setup/smtp/status')
}

export async function testSmtpConnection(data: SmtpTestRequest): Promise<SmtpTestResponse> {
  return request('/setup/smtp/test', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function saveSmtpConfig(data: SmtpSetupRequest): Promise<SmtpStatusResponse> {
  return request('/setup/smtp/save', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// =============================================================================
// ROOM MARKETPLACE API
// =============================================================================

import type {
  RoomMarketplaceTemplate,
  RoomTemplateListResponse,
  InstallRoomTemplateResponse,
} from '../types'

const ROOM_MARKETPLACE_CACHE_KEY = 'cachibot_room_marketplace_cache'

function getRoomMarketplaceCache<T>(key: string): T | null {
  try {
    const cached = localStorage.getItem(`${ROOM_MARKETPLACE_CACHE_KEY}_${key}`)
    if (!cached) return null
    const entry: CacheEntry<T> = JSON.parse(cached)
    if (Date.now() - entry.timestamp > MARKETPLACE_CACHE_TTL) {
      localStorage.removeItem(`${ROOM_MARKETPLACE_CACHE_KEY}_${key}`)
      return null
    }
    return entry.data
  } catch {
    return null
  }
}

function setRoomMarketplaceCache<T>(key: string, data: T): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now() }
    localStorage.setItem(`${ROOM_MARKETPLACE_CACHE_KEY}_${key}`, JSON.stringify(entry))
  } catch {
    // Ignore cache errors
  }
}

async function fetchRemoteRoomTemplates(
  category?: string,
  search?: string,
  responseMode?: string,
): Promise<RoomTemplateListResponse | null> {
  if (!REMOTE_MARKETPLACE_URL) return null

  try {
    const cacheKey = `remote_room_templates_${category || ''}_${search || ''}_${responseMode || ''}`
    if (!search) {
      const cached = getRoomMarketplaceCache<RoomTemplateListResponse>(cacheKey)
      if (cached) return { ...cached, source: 'remote' }
    }

    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (search) params.set('search', search)
    if (responseMode) params.set('response_mode', responseMode)

    const queryString = params.toString()
    const url = `${REMOTE_MARKETPLACE_URL}/marketplace/room-templates${queryString ? `?${queryString}` : ''}`

    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) return null

    const data: RoomTemplateListResponse = await response.json()

    if (!search) {
      setRoomMarketplaceCache(cacheKey, data)
    }

    return { ...data, source: 'remote' }
  } catch (err) {
    console.warn('Failed to fetch remote room templates:', err)
    return null
  }
}

async function fetchRemoteRoomTemplate(templateId: string): Promise<RoomMarketplaceTemplate | null> {
  if (!REMOTE_MARKETPLACE_URL) return null

  try {
    const cacheKey = `remote_room_template_${templateId}`
    const cached = getRoomMarketplaceCache<RoomMarketplaceTemplate>(cacheKey)
    if (cached) return cached

    const url = `${REMOTE_MARKETPLACE_URL}/marketplace/room-templates/${templateId}`
    const response = await fetch(url)

    if (!response.ok) return null

    const data: RoomMarketplaceTemplate = await response.json()
    setRoomMarketplaceCache(cacheKey, data)
    return data
  } catch (err) {
    console.warn('Failed to fetch remote room template:', err)
    return null
  }
}

export async function getRoomMarketplaceTemplates(
  category?: string,
  search?: string,
  responseMode?: string,
): Promise<RoomTemplateListResponse> {
  const remote = await fetchRemoteRoomTemplates(category, search, responseMode)
  if (remote) return remote

  try {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (search) params.set('search', search)
    if (responseMode) params.set('response_mode', responseMode)
    const result = await request<RoomTemplateListResponse>(`/marketplace/room-templates?${params}`)
    return { ...result, source: 'local' }
  } catch {
    return { templates: [], total: 0, source: 'local' }
  }
}

export async function getRoomMarketplaceTemplate(templateId: string): Promise<RoomMarketplaceTemplate | null> {
  const remote = await fetchRemoteRoomTemplate(templateId)
  if (remote) return remote

  try {
    return await request(`/marketplace/room-templates/${templateId}`)
  } catch {
    return null
  }
}

export async function installRoomMarketplaceTemplate(templateId: string): Promise<InstallRoomTemplateResponse> {
  return request(`/marketplace/room-templates/${templateId}/install`, { method: 'POST' })
}

export { ApiError }
