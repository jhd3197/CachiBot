// =============================================================================
// AUTH TYPES
// =============================================================================

export type UserRole = 'admin' | 'manager' | 'user'

export interface User {
  id: string
  email: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
  created_by: string | null
  last_login: string | null
  website_user_id: number | null
  tier: string
  credit_balance: number
  is_verified: boolean
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
  legacy_db_detected: boolean
}

export interface UserListResponse {
  users: User[]
  total: number
}

export interface AuthModeResponse {
  mode: 'selfhosted' | 'cloud'
  login_url: string | null
}

export interface ExchangeTokenRequest {
  token: string
}

// =============================================================================
// GROUP & ACCESS TYPES
// =============================================================================

export type GroupRole = 'owner' | 'member'
export type BotAccessLevel = 'viewer' | 'operator' | 'editor'

export interface Group {
  id: string
  name: string
  description: string | null
  created_by: string
  created_at: string
  updated_at: string
  member_count: number
}

export interface GroupMember {
  user_id: string
  username: string
  email: string
  role: GroupRole
  joined_at: string
}

export interface GroupWithMembers extends Group {
  members: GroupMember[]
}

export interface BotAccessRecord {
  id: string
  bot_id: string
  bot_name: string | null
  group_id: string
  group_name: string | null
  access_level: BotAccessLevel
  granted_by: string
  granted_at: string
}

export interface CreateGroupRequest {
  name: string
  description?: string
}

export interface UpdateGroupRequest {
  name?: string
  description?: string
}

export interface AddMemberRequest {
  user_id: string
  role?: GroupRole
}

export interface ShareBotRequest {
  group_id: string
  access_level?: BotAccessLevel
}

export interface UpdateAccessRequest {
  access_level: BotAccessLevel
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
  promptTokens?: number
  completionTokens?: number
  elapsedMs?: number
  tokensPerSecond?: number
  callCount?: number
  errors?: number
  perModel?: Record<string, { tokens: number; cost: number }>
  latencyStats?: Record<string, number>
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  metadata?: MessageMetadata & Record<string, unknown>
  toolCalls?: ToolCall[]
  replyToId?: string
  thinking?: string
}

// =============================================================================
// BOT TYPES
// =============================================================================

// Icon names from Lucide
export type BotIcon =
  | 'shield' | 'bot' | 'brain' | 'zap' | 'flame' | 'gem'
  | 'rocket' | 'target' | 'laptop' | 'bar-chart' | 'sparkles' | 'star'
  | 'cpu' | 'ghost' | 'palette' | 'pen-tool' | 'code' | 'terminal'

// Multi-model slot configuration per bot
export interface BotModels {
  default: string
  image?: string
  audio?: string
  structured?: string
}

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
  imageGeneration: boolean    // generate_image (DALL-E, Imagen, Stability AI)
  audioGeneration: boolean    // generate_audio, transcribe_audio (TTS/STT)
}

export interface Bot {
  id: string
  name: string
  description: string
  icon: BotIcon // Lucide icon name
  color: string // accent color for the bot
  model: string
  models?: BotModels // Multi-model slot configuration
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

  // Voice channel settings (optional)
  voiceSettings?: {
    ttsVoice: string
    ttsSpeed: number
    sttLanguage: string | null
    enableInterruption: boolean
    saveTranscripts: boolean
  }
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
  /** 0-100 (converted from backend 0.0-1.0 on receive) */
  progress: number
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
  | 'scheduled_notification'
  | 'document_status'
  | 'connection_status'
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
  replyToId?: string
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
  callCount: number
  errors: number
  perModel: Record<string, { tokens: number; cost: number }>
  latencyStats: Record<string, number>
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

export interface ScheduledNotificationPayload {
  botId: string
  chatId?: string
  content: string
}

export interface DocumentStatusPayload {
  botId: string
  documentId: string
  status: 'processing' | 'ready' | 'failed'
  chunkCount?: number
  filename?: string
}

export interface ConnectionStatusPayload {
  connectionId: string
  botId: string
  status: ConnectionStatus
  platform: string
  error?: string
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
  | 'custom'

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

export type BotView = 'chats' | 'rooms' | 'tasks' | 'work' | 'schedules' | 'automations' | 'voice' | 'tools' | 'developer' | 'settings'
export type WorkSection = 'overview' | 'active' | 'completed' | 'history'
export type ScheduleSection = 'all' | 'enabled' | 'disabled' | 'create'
export type AutomationSection = 'all' | 'functions' | 'scripts' | 'schedules'
export type AppView = 'dashboard' | 'admin-logs' | 'settings'

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
// PLATFORM TOOL CONFIG TYPES
// =============================================================================

export interface PlatformToolConfig {
  disabledCapabilities: string[]
  disabledSkills: string[]
}

export interface PlatformToolConfigUpdate {
  disabled_capabilities?: string[]
  disabled_skills?: string[]
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
  type: 'number' | 'string' | 'boolean' | 'select' | 'string[]' | 'number[]' | 'secret' | 'text' | 'path' | 'map' | 'multiselect' | 'url' | 'code'
  default: unknown
  min?: number
  max?: number
  step?: number
  options?: string[]
  unit?: string
  scope: 'global' | 'per_bot' | 'per_call'
  // Array types (string[], number[])
  minItems?: number
  maxItems?: number
  itemPlaceholder?: string
  // Secret, text, path types
  placeholder?: string
  // Text type
  rows?: number
  // Path type
  pathType?: 'file' | 'directory' | 'any'
  // Map type
  keyPlaceholder?: string
  valuePlaceholder?: string
  // Code type
  language?: string
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
  /** 0-100 (converted from backend 0.0-1.0 on receive) */
  progress: number

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
  /** 0-100 (converted from backend 0.0-1.0 on receive) */
  progress: number

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

// =============================================================================
// MULTI-AGENT ROOMS
// =============================================================================

export type RoomMemberRole = 'creator' | 'member'
export type RoomSenderType = 'user' | 'bot' | 'system'
export type RoomBotRole = 'default' | 'lead' | 'reviewer' | 'observer' | 'specialist'

export interface RoomMember {
  userId: string
  username: string
  role: RoomMemberRole
  joinedAt: string
}

export interface RoomBot {
  botId: string
  botName: string
  role: RoomBotRole
  addedAt: string
}

export interface RoomSettings {
  cooldown_seconds: number
  auto_relevance: boolean
  response_mode: 'parallel' | 'sequential' | 'chain' | 'router' | 'debate' | 'waterfall'
  debate_rounds?: number
  debate_positions?: Record<string, string>
  debate_judge_bot_id?: string | null
  debate_judge_prompt?: string
  routing_strategy?: 'llm' | 'keyword' | 'round_robin'
  bot_keywords?: Record<string, string[]>
  waterfall_conditions?: Record<string, string>
}

export interface Room {
  id: string
  title: string
  description: string | null
  creatorId: string
  maxBots: number
  settings: RoomSettings
  members: RoomMember[]
  bots: RoomBot[]
  messageCount: number
  createdAt: string
  updatedAt: string
}

export interface RoomMessage {
  id: string
  roomId: string
  senderType: RoomSenderType
  senderId: string
  senderName: string
  content: string
  metadata: Record<string, unknown>
  timestamp: string
  toolCalls?: ToolCall[]
  thinking?: string
}

export type RoomWSMessageType =
  | 'room_chat'
  | 'room_typing'
  | 'room_cancel'
  | 'room_message'
  | 'room_bot_thinking'
  | 'room_bot_tool_start'
  | 'room_bot_tool_end'
  | 'room_bot_instruction_delta'
  | 'room_bot_done'
  | 'room_typing_indicator'
  | 'room_presence'
  | 'room_error'
  | 'room_usage'
  | 'room_chain_step'
  | 'room_route_decision'
  | 'room_debate_round_start'
  | 'room_debate_round_end'
  | 'room_debate_judge_start'
  | 'room_debate_complete'
  | 'room_waterfall_step'
  | 'room_waterfall_skipped'
  | 'room_waterfall_stopped'

export interface RoomWSMessage {
  type: RoomWSMessageType
  payload: Record<string, unknown>
}

export interface RoomMessagePayload {
  roomId: string
  senderType: RoomSenderType
  senderId: string
  senderName: string
  content: string
  messageId?: string
}

export interface RoomPresencePayload {
  roomId: string
  userId: string
  username: string
  status: 'online' | 'offline'
}

export interface RoomTypingPayload {
  roomId: string
  userId: string
  username: string
  isTyping: boolean
}

export interface RoomBotThinkingPayload {
  roomId: string
  botId: string
  botName: string
}

export interface CreateRoomRequest {
  title: string
  description?: string
  bot_ids: string[]
  settings?: RoomSettings
}

// =============================================================================
// ROOM MARKETPLACE TYPES
// =============================================================================

export interface RoomBotSpec {
  template_id: string
  role: RoomBotRole
  position?: string | null
  keywords?: string[]
  waterfall_condition?: string | null
}

export interface RoomMarketplaceTemplate {
  id: string
  name: string
  description: string
  icon: string
  color: string
  category: string
  tags: string[]
  response_mode: RoomSettings['response_mode']
  bots: RoomBotSpec[]
  settings: Partial<RoomSettings>
  rating: number
  downloads: number
  bot_details?: MarketplaceBot[]
}

export interface MarketplaceBot {
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

export interface RoomTemplateListResponse {
  templates: RoomMarketplaceTemplate[]
  total: number
  source?: 'local' | 'remote'
}

export interface InstallRoomTemplateResponse {
  room_id: string
  room_title: string
  bot_ids: string[]
  installed_bots: string[]
  reused_bots: string[]
}

// =============================================================================
// DEVELOPER API TYPES
// =============================================================================

export type WebhookEvent =
  | 'message.created'
  | 'task.completed'
  | 'work.completed'
  | 'work.failed'
  | 'schedule.triggered'
  | 'api.request'

export interface BotApiKey {
  id: string
  bot_id: string
  name: string
  key_prefix: string
  created_at: string
  last_used_at: string | null
  usage_count: number
  expires_at: string | null
  is_revoked: boolean
}

export interface BotApiKeyCreated extends BotApiKey {
  key: string
}

export interface BotWebhook {
  id: string
  bot_id: string
  name: string
  url: string
  events: WebhookEvent[]
  is_active: boolean
  last_triggered_at: string | null
  failure_count: number
  created_at: string
  updated_at: string | null
}
