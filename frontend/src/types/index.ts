// =============================================================================
// AUTH TYPES
// =============================================================================

export type UserRole = 'admin' | 'user'

export interface User {
  id: string
  email: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
  created_by: string | null
  last_login: string | null
}

export interface LoginRequest {
  identifier: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface RefreshRequest {
  refresh_token: string
}

export interface RefreshResponse {
  access_token: string
  token_type: string
}

export interface CreateUserRequest {
  email: string
  username: string
  password: string
  role: UserRole
}

export interface UpdateUserRequest {
  email?: string
  username?: string
  role?: UserRole
  is_active?: boolean
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface SetupRequest {
  email: string
  username: string
  password: string
}

export interface SetupStatusResponse {
  setup_required: boolean
}

export interface UserListResponse {
  users: User[]
  total: number
}

// =============================================================================
// CORE TYPES
// =============================================================================

// Message types
export type MessageRole = 'user' | 'assistant' | 'system'

export interface MessageMetadata {
  model?: string
  tokens?: number
  cost?: number
  iterations?: number
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  metadata?: MessageMetadata & Record<string, unknown>
  toolCalls?: ToolCall[]
}

// =============================================================================
// BOT TYPES
// =============================================================================

// Icon names from Lucide
export type BotIcon =
  | 'shield' | 'bot' | 'brain' | 'zap' | 'flame' | 'gem'
  | 'rocket' | 'target' | 'laptop' | 'bar-chart' | 'sparkles' | 'star'
  | 'cpu' | 'ghost' | 'palette' | 'pen-tool' | 'code' | 'terminal'

// Capability toggles per bot
export interface BotCapabilities {
  codeExecution: boolean      // python_execute
  fileOperations: boolean     // file_read, file_write, file_list, file_edit, file_info
  gitOperations: boolean      // git_status, git_diff, git_log, git_commit, git_branch
  shellAccess: boolean        // shell_execute, shell_which
  webAccess: boolean          // web_fetch, web_search, http_request
  dataOperations: boolean     // sqlite_query, sqlite_execute, zip/tar
  contacts: boolean           // Access to contacts in system prompt context
  connections: boolean        // telegram_send, discord_send
  workManagement: boolean     // work_create, work_list, work_update, todo_create, todo_list, todo_done
}

export interface Bot {
  id: string
  name: string
  description: string
  icon: BotIcon // Lucide icon name
  color: string // accent color for the bot
  model: string
  systemPrompt?: string
  tools: string[] // tool IDs enabled for this bot
  createdAt: string
  updatedAt: string

  // Personality configuration (optional - for bots created via conversational flow)
  personality?: {
    purposeCategory: string
    purposeDescription: string
    communicationStyle: string
    useEmojis: 'yes' | 'no' | 'sometimes'
  }

  // Capability toggles (optional - defaults applied if missing for backwards compat)
  capabilities?: BotCapabilities

  // Per-tool configuration (optional - defaults applied if missing)
  toolConfigs?: ToolConfigs
}

export interface BotStats {
  totalChats: number
  totalMessages: number
  activeJobs: number
  completedTasks: number
}

// =============================================================================
// CHAT TYPES
// =============================================================================

export interface Chat {
  id: string
  botId: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
  lastMessage?: string
  pinned?: boolean
  archived?: boolean
  // Platform chat fields (for Telegram, Discord conversations)
  platform?: 'telegram' | 'discord' | null
  platformChatId?: string | null
}

// =============================================================================
// JOB TYPES
// =============================================================================

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type JobPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface Job {
  id: string
  botId: string
  chatId?: string
  title: string
  description?: string
  status: JobStatus
  priority: JobPriority
  progress: number // 0-100
  createdAt: string
  startedAt?: string
  completedAt?: string
  result?: string | Record<string, unknown>
  error?: string
  logs?: JobLog[]
}

export interface JobLog {
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
}

// =============================================================================
// TASK TYPES
// =============================================================================

export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'
export type TaskPriority = 'low' | 'medium' | 'high'

export interface Task {
  id: string
  botId: string
  chatId?: string
  title: string
  description?: string
  status: TaskStatus
  priority: TaskPriority
  dueDate?: string
  tags: string[]
  createdAt: string
  completedAt?: string
  blockedBy?: string[] // task IDs
}

// =============================================================================
// TOOL TYPES
// =============================================================================

export interface Tool {
  id: string
  name: string
  description: string
  category: ToolCategory
  icon: string
  enabled: boolean
  riskLevel: 'safe' | 'moderate' | 'dangerous' | 'critical'
  parameters?: ToolParameter[]
  configParams?: ConfigParam[]
}

export type ToolCategory = 'filesystem' | 'code' | 'web' | 'system' | 'data' | 'custom'

export interface ToolParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  description: string
  required: boolean
  default?: unknown
}

export interface ToolExecution {
  id: string
  toolId: string
  botId: string
  chatId?: string
  args: Record<string, unknown>
  result?: unknown
  success?: boolean
  duration?: number
  timestamp: string
}

// =============================================================================
// TOOL CONFIG TYPES
// =============================================================================

// Generic tool config: maps tool ID -> param name -> value
// Config params are now described by ConfigParam[] from the API
export type ToolConfigs = Record<string, Record<string, unknown>>

// =============================================================================
// CONFIG TYPES
// =============================================================================

export interface AgentConfig {
  model: string
  maxIterations: number
  approveActions: boolean
  temperature: number
}

export interface SandboxConfig {
  allowedImports: string[]
  timeoutSeconds: number
  maxOutputLength: number
}

export interface DisplayConfig {
  showThinking: boolean
  showCost: boolean
  style: 'detailed' | 'compact'
}

export interface Config {
  agent: AgentConfig
  sandbox: SandboxConfig
  display: DisplayConfig
  workspacePath: string
}

// Model types
export interface ModelInfo {
  id: string
  name: string
  provider: string
  contextWindow: number
  supportsTools: boolean
}

// =============================================================================
// WEBSOCKET TYPES
// =============================================================================

export type WSMessageType =
  | 'chat'
  | 'cancel'
  | 'approval'
  | 'thinking'
  | 'tool_start'
  | 'tool_end'
  | 'message'
  | 'platform_message'
  | 'approval_needed'
  | 'usage'
  | 'error'
  | 'done'
  | 'job_update'
  | 'task_update'

export interface WSMessage<T = unknown> {
  type: WSMessageType
  payload: T
}

export interface ThinkingPayload {
  content: string
}

export interface ToolStartPayload {
  id: string
  tool: string
  args: Record<string, unknown>
}

export interface ToolEndPayload {
  id: string
  result: unknown
  success: boolean
}

export interface MessagePayload {
  role: MessageRole
  content: string
  messageId?: string
}

export interface ApprovalPayload {
  id: string
  tool: string
  action: string
  details: {
    code?: string
    riskLevel?: string
    reasons?: string[]
  }
}

export interface UsagePayload {
  totalTokens: number
  promptTokens: number
  completionTokens: number
  totalCost: number
  iterations: number
  elapsedMs: number
  tokensPerSecond: number
}

export interface PlatformMessagePayload {
  botId: string
  chatId: string
  role: MessageRole
  content: string
  messageId: string
  platform: string
}

export interface ErrorPayload {
  message: string
  code?: string
}

// Tool call tracking
export interface ToolCall {
  id: string
  tool: string
  args: Record<string, unknown>
  result?: unknown
  success?: boolean
  startTime: number
  endTime?: number
}

// =============================================================================
// CONNECTION TYPES
// =============================================================================

export type ConnectionPlatform =
  | 'whatsapp'
  | 'telegram'
  | 'discord'
  | 'slack'
  | 'messenger'
  | 'matrix'
  | 'email'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface Connection {
  id: string
  botId: string // assigned bot (required for per-bot connections)
  platform: ConnectionPlatform
  name: string
  status: ConnectionStatus
  config: Record<string, string>
  lastActivity?: string
  messageCount: number
  createdAt: string
  error?: string
}

export interface PlatformInfo {
  id: ConnectionPlatform
  name: string
  description: string
  icon: string
  library: string
  docsUrl: string
  free: boolean
  setupSteps: string[]
}

// =============================================================================
// USAGE & COST TYPES
// =============================================================================

export interface UsageStats {
  totalMessages: number
  totalTokens: number
  totalCost: number
  byModel: Record<string, { tokens: number; cost: number; messages: number }>
  byBot: Record<string, { tokens: number; cost: number; messages: number }>
  daily: { date: string; tokens: number; cost: number; messages: number }[]
}

// =============================================================================
// NAVIGATION TYPES
// =============================================================================

export type BotView = 'chats' | 'tasks' | 'work' | 'schedules' | 'tools' | 'settings'
export type WorkSection = 'overview' | 'active' | 'completed' | 'history'
export type ScheduleSection = 'all' | 'enabled' | 'disabled' | 'create'
export type AppView = 'dashboard' | 'settings' | 'models'

// =============================================================================
// CREATION FLOW TYPES
// =============================================================================

export type CreationFlowStep =
  | 'idle'
  | 'name'
  | 'purpose-category'
  | 'purpose-description'
  | 'style'
  | 'emoji'
  | 'summary'
  | 'complete'

export interface CreationFlowData {
  name: string | null
  nameSuggestions: string[]
  purposeCategory: string | null
  purposeDescription: string | null
  communicationStyle: string | null
  useEmojis: 'yes' | 'no' | 'sometimes' | null
  detectedLanguage: string | null
}

// =============================================================================
// SKILL TYPES
// =============================================================================

export type SkillSource = 'local' | 'installed'

export interface SkillDefinition {
  id: string
  name: string
  description: string
  version: string
  author?: string
  tags: string[]
  requiresTools: string[]
  instructions: string
  source: SkillSource
  filepath?: string
}

// =============================================================================
// PLUGIN TYPES
// =============================================================================

export interface PluginInfo {
  name: string
  class: string
  capability: string | null    // null = always enabled
  alwaysEnabled: boolean
  displayName: string          // from PluginManifest
  icon: string | null          // Lucide icon name
  color: string | null         // hex color
  group: string | null         // plugin group
  skills: (PluginSkillInfo | string)[]  // string[] if backend returns names only
}

export interface PluginSkillInfo {
  name: string
  description: string
  category: string
  tags: string[]
  version: string
  isAsync: boolean
  idempotent: boolean
  sideEffects: boolean
  requiresNetwork: boolean
  requiresFilesystem: boolean
  displayName: string           // from SkillDescriptor
  icon: string | null           // Lucide icon name
  riskLevel: string             // "safe" | "moderate" | "dangerous" | "critical"
  group: string | null
  configParams: ConfigParam[]
  hidden: boolean
  deprecated: string | null
}

export interface ConfigParam {
  name: string
  displayName: string | null
  description: string | null
  type: 'number' | 'string' | 'boolean' | 'select'
  default: unknown
  min?: number
  max?: number
  step?: number
  options?: string[]
  unit?: string
  scope: 'global' | 'per_bot' | 'per_call'
}

// =============================================================================
// WORK MANAGEMENT TYPES
// =============================================================================

// Enums
export type WorkStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled' | 'paused'
export type WorkTaskStatus = 'pending' | 'ready' | 'in_progress' | 'completed' | 'failed' | 'blocked' | 'skipped'
export type WorkJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TodoStatus = 'open' | 'done' | 'dismissed'
export type Priority = 'low' | 'normal' | 'high' | 'urgent'
export type ScheduleType = 'cron' | 'interval' | 'once' | 'event'
export type FailureAction = 'stop' | 'continue' | 'skip_dependents'

// Function (Reusable Template)
export interface FunctionStep {
  order: number
  name: string
  description?: string
  action: string
  dependsOn: number[]
  retryCount: number
  timeoutSeconds?: number
  onFailure: FailureAction
}

export interface FunctionParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  default?: unknown
  required: boolean
  description?: string
}

export interface BotFunction {
  id: string
  botId: string
  name: string
  description?: string
  version: string
  steps: FunctionStep[]
  parameters: FunctionParameter[]
  tags: string[]
  createdAt: string
  updatedAt: string
  runCount: number
  lastRunAt?: string
  successRate: number
}

// Schedule (Cron/Timer)
export interface Schedule {
  id: string
  botId: string
  name: string
  description?: string

  // What to run
  functionId?: string
  functionParams: Record<string, unknown>

  // When to run
  scheduleType: ScheduleType
  cronExpression?: string      // "0 2 * * *"
  intervalSeconds?: number     // 3600 = every hour
  runAt?: string               // ISO datetime for once
  eventTrigger?: string        // event name
  timezone: string

  // Constraints
  enabled: boolean
  maxConcurrent: number
  catchUp: boolean

  // Metadata
  createdAt: string
  updatedAt: string
  nextRunAt?: string
  lastRunAt?: string
  runCount: number
}

// Work (High-level Objective)
export interface Work {
  id: string
  botId: string
  chatId?: string

  // Identity
  title: string
  description?: string
  goal?: string

  // Source
  functionId?: string
  scheduleId?: string
  parentWorkId?: string

  // Status
  status: WorkStatus
  priority: Priority
  progress: number  // 0-100

  // Timing
  createdAt: string
  startedAt?: string
  completedAt?: string
  dueAt?: string

  // Results
  result?: unknown
  error?: string

  // Context
  context: Record<string, unknown>
  tags: string[]

  // Derived (computed on frontend)
  taskCount?: number
  completedTaskCount?: number
}

// Task (Step within Work)
export interface WorkTask {
  id: string
  botId: string
  workId: string
  chatId?: string

  // Identity
  title: string
  description?: string
  action?: string

  // Ordering
  order: number
  dependsOn: string[]  // task IDs

  // Status
  status: WorkTaskStatus
  priority: Priority

  // Execution
  retryCount: number
  maxRetries: number
  timeoutSeconds?: number

  // Timing
  createdAt: string
  startedAt?: string
  completedAt?: string

  // Results
  result?: unknown
  error?: string

  // Derived
  jobCount?: number
  latestJobId?: string
}

// Job (Execution Attempt)
export interface WorkJob {
  id: string
  botId: string
  taskId: string
  workId: string
  chatId?: string

  // Status
  status: WorkJobStatus
  attempt: number
  progress: number  // 0-100

  // Timing
  createdAt: string
  startedAt?: string
  completedAt?: string

  // Results
  result?: unknown
  error?: string
  logs: WorkJobLog[]
}

export interface WorkJobLog {
  timestamp: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  data?: unknown
}

// Todo (Reminder/Note)
export interface Todo {
  id: string
  botId: string
  chatId?: string

  // Content
  title: string
  notes?: string

  // Status
  status: TodoStatus
  priority: Priority

  // Timing
  createdAt: string
  completedAt?: string
  remindAt?: string

  // Conversion
  convertedToWorkId?: string
  convertedToTaskId?: string

  tags: string[]
}

// =============================================================================
// WORK MANAGEMENT WEBSOCKET TYPES
// =============================================================================

export interface WorkUpdatePayload {
  work: Work
  action: 'created' | 'updated' | 'deleted'
}

export interface TaskUpdatePayload {
  task: WorkTask
  action: 'created' | 'updated' | 'deleted'
}

export interface JobUpdatePayload {
  job: WorkJob
  action: 'created' | 'updated' | 'deleted'
}

export interface TodoUpdatePayload {
  todo: Todo
  action: 'created' | 'updated' | 'deleted'
}

export interface ScheduleTriggeredPayload {
  scheduleId: string
  workId: string
}

// =============================================================================
// WORK MANAGEMENT API TYPES
// =============================================================================

export interface CreateWorkRequest {
  botId: string
  title: string
  description?: string
  goal?: string
  priority?: Priority
  dueAt?: string
  context?: Record<string, unknown>
  tags?: string[]
  functionId?: string  // To instantiate from a function
  functionParams?: Record<string, unknown>
}

export interface CreateTaskRequest {
  workId: string
  title: string
  description?: string
  action?: string
  order?: number
  dependsOn?: string[]
  priority?: Priority
  maxRetries?: number
  timeoutSeconds?: number
}

export interface CreateTodoRequest {
  botId: string
  title: string
  notes?: string
  priority?: Priority
  remindAt?: string
  tags?: string[]
}

export interface CreateFunctionRequest {
  botId: string
  name: string
  description?: string
  steps: Omit<FunctionStep, 'order'>[]
  parameters?: FunctionParameter[]
  tags?: string[]
}

export interface CreateScheduleRequest {
  botId: string
  name: string
  description?: string
  functionId: string
  functionParams?: Record<string, unknown>
  scheduleType: ScheduleType
  cronExpression?: string
  intervalSeconds?: number
  runAt?: string
  eventTrigger?: string
  timezone?: string
  maxConcurrent?: number
  catchUp?: boolean
}
