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
  utility?: string
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
  codingAgent: boolean        // coding_agent (Claude Code, Codex, Gemini CLI)
  // Dynamic external plugin capabilities (ext_<name>)
  [key: string]: boolean | undefined
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

// Rail ordering types
export interface BotGroup {
  id: string
  name: string
  collapsed: boolean
  botIds: string[]  // ordered bot IDs within this group
}

export type RailItem =
  | { type: 'bot'; botId: string }
  | { type: 'group'; groupId: string }

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
// SIDE TASK TYPES (principle 9 — child chats that work in parallel)
// =============================================================================

export type SideTaskStatus =
  | 'waiting_for_slot'
  | 'running'
  | 'needs_you'
  | 'done'
  | 'merged'
  | 'failed'
  | 'stopped'

export type SideTaskKind = 'side' | 'helper'
export type SideTaskStartedBy = 'user' | 'bot'

/** One path changed on the side branch relative to base, as recorded on merge. */
export interface SideTaskMergedFile {
  path: string
  status: string
}

/**
 * Metadata of the assistant reply message a side task (or helper group)
 * persists in the parent chat (kind "side_task_reply"): the thread-style
 * report that quotes the message that started it. The message body is the
 * short summary; the structured outcome lives here, from the real record.
 */
export interface SideTaskReplyMetadata {
  kind: 'side_task_reply'
  sideTaskId: string
  title: string
  /** The side task's own chat ("View thread" target). */
  chatId: string
  status: SideTaskStatus
  /** Parent-chat message quoted (== message.replyToId). */
  replyTo?: string
  mergedFiles?: SideTaskMergedFile[]
  mergedCommit?: string
  error?: string
  needsYouReason?: string
  conflictFiles?: string[]
}

/** One per-helper row carried by a group reply (kind "side_task_group_reply"). */
export interface SideTaskGroupReplyItem {
  id: string
  title: string
  status: SideTaskStatus
  chatId: string
}

export interface SideTaskGroupReplyMetadata {
  kind: 'side_task_group_reply'
  groupId: string
  title: string
  status: 'running' | 'needs_you' | 'failed' | 'settled'
  total: number
  done: number
  failed: number
  running: number
  waiting: number
  needsYou: number
  items: SideTaskGroupReplyItem[]
  replyTo?: string
}

export type SideTaskReplyKind = 'side_task_reply' | 'side_task_group_reply'

/** Full side-task record as returned by the REST API and `side_task_update`. */
export interface SideTask {
  id: string
  botId: string
  parentChatId: string
  chatId: string
  title: string
  prompt: string
  kind: SideTaskKind
  groupId: string | null
  groupTitle: string | null
  status: SideTaskStatus
  needsYouReason: string | null
  startedBy: SideTaskStartedBy
  worktreePath: string | null
  branch: string | null
  baseCommit: string | null
  mergedCommit: string | null
  mergedFiles: SideTaskMergedFile[]
  conflictFiles: string[]
  /** Parent-chat message this side task answers (thread-reply source). */
  sourceMessageId: string | null
  /** The one parent-chat reply message (created once, updated in place). */
  replyMessageId: string | null
  error: string | null
  workId: string | null
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  updatedAt: string
}

// =============================================================================
// FARO AGENT BRIDGE — the local Faro bridge detection plus the per-bot
// connection. Nothing here ever carries the bridge token; the pending
// approvals may carry sensitive command summaries and are delivered only to
// users who can see the bot. Every surface stays hidden while the bridge is
// unavailable and the bot is not connected.
// =============================================================================

/** GET /api/integrations/faro/status — the global bridge detection. */
export interface FaroIntegrationStatus {
  available: boolean
  reason: string | null
  version: string | null
  supportsApprovals: boolean
}

/** One approval Faro is waiting for (GET /approvals shape, summary-mapped). */
export interface FaroApproval {
  requestId: string
  sessionId: string | null
  sessionName: string | null
  kind: string | null
  summary: string | null
}

/** GET /api/bots/{id}/faro — one bot's Faro connection status. */
export interface BotFaroStatus {
  connected: boolean
  available: boolean
  reason: string | null
  version: string | null
  supportsApprovals: boolean
  /** One of this bot's faro tools is running right now. */
  callInFlight: boolean
  /** Approvals Faro is waiting on during the current call. */
  pendingApprovals: FaroApproval[]
}

/** `faro_update` WebSocket payload: the per-bot status plus the bot it
 * belongs to. Delivered only to sockets that can see the bot. */
export interface FaroUpdatePayload extends BotFaroStatus {
  botId: string
}

// =============================================================================
// BOT COMPUTER (Mini Vela) — status/state (C1) plus the live surface (C2):
// preview revision, activity, windows, watchers, driver and needs-you. The
// views land in C4 and stay hidden while the Docker probe says unavailable.
// =============================================================================

/** Lifecycle of a bot's computer, as reported by the backend. */
export type ComputerState =
  | 'unavailable'
  | 'off'
  | 'building'
  | 'starting'
  | 'awake'
  | 'asleep'
  | 'needs_you'

/** Progress of the first-use Vela image build (global, single-flight). */
export interface ComputerBuildProgress {
  status: 'building' | 'idle' | 'failed'
  step?: number | null
  total?: number | null
  line?: string
  error?: string | null
}

/** GET /api/computer/status — the Docker probe summary. */
export interface DockerProbeSummary {
  available: boolean
  reason: string | null
  docker_version: string | null
  server_os: string | null
  arch: string | null
}

/** GET /api/bots/{id}/computer — one bot's computer status. Never carries
 * the controller token or the container's host port. */export interface BotComputer {
  available: boolean
  reason: string | null
  state: ComputerState
  build: ComputerBuildProgress | null
  velaVersion: string
  lastActiveAt: string | null
  lastError: string | null
  /** The desktop's one-line "what it is doing" (null when idle). */
  activity: ComputerActivity | null
  /** Open windows on the desktop. */
  windowsCount: number
  /** Live watchers CachiBot counts (heartbeats + preview fetches). */
  watchers: number
  /** Who is driving right now (a person holding the take-over), or null. */
  driver: ComputerDriver | null
  /** Why the computer needs a person (state needs_you), or null. */
  needsYou: string | null
  /** Content revision of the preview; refetch the preview when it changes. */
  previewRevision: string | null
}

/** The desktop's one-line activity, derived by Vela from the running step. */
export interface ComputerActivity {
  text: string
  at: number
  viewId?: string | null
}

/** Who is driving the computer right now. */
export interface ComputerDriver {
  userId: string
  name: string
  since: string
}

/** One open window on the bot's desktop (a Vela view). */
export interface ComputerWindow {
  id: string
  kind: string
  title: string
  app: string
  url?: string | null
}

/** GET /api/bots/{id}/computer/views — windows plus the activity line. */
export interface ComputerViewsResponse {
  windows: ComputerWindow[]
  activity: ComputerActivity | null
}

/** One entry in the bot's /workspace (GET .../computer/workspace). */
export interface ComputerWorkspaceEntry {
  name: string
  path: string
  kind: string
  size: number | null
  modified: string | null
}

/** GET /api/bots/{id}/computer/workspace — one folder of the workspace. */
export interface ComputerWorkspaceResponse {
  path: string
  entries: ComputerWorkspaceEntry[]
}

/** POST /api/bots/{id}/computer/watch — the watcher is counted. */
export interface ComputerWatchResponse {
  watching: boolean
  watchers: number
  expiresInSeconds: number
}

/** POST /api/bots/{id}/computer/input — one piece of person input.
 * click (button left/right/middle), scroll (wheel deltas), type, key. */
export interface ComputerInput {
  kind: 'click' | 'scroll' | 'type' | 'key'
  viewId?: string
  point?: { x: number; y: number }
  button?: 'left' | 'right' | 'middle'
  clickCount?: 1 | 2
  dx?: number
  dy?: number
  key?: string
  text?: string
  frameAt?: number
}

/** A fetched preview/frame: image bytes named by their ETag revision. */
export interface ComputerFrame {
  blob: Blob
  etag: string | null
  revision: string | null
}

/** `computer_update` WebSocket payload: the status plus the bot it belongs to. */
export interface ComputerUpdatePayload extends BotComputer {
  botId: string
}

/** Aggregate view of one helper group (GET /side-task-groups/{groupId}). */
export interface SideTaskGroupSummary {
  groupId: string
  title: string | null
  total: number
  done: number
  failed: number
  running: number
  waiting: number
  needsYou: number
  items: SideTask[]
}

/** One changed file in a side-task diff (GET /side-tasks/{id}/diff). */
export interface SideTaskDiffFile {
  path: string
  /** added | modified | deleted */
  status: string
  /** null when the file is binary */
  additions: number | null
  deletions: number | null
  binary: boolean
}

/**
 * Unified diff + per-file stats behind "View changes". Unmerged: the
 * worktree against its base (incl. uncommitted). Merged: the merged commit
 * range. `truncated` flags a diff cut at the size cap.
 */
export interface SideTaskDiff {
  sideTaskId: string
  status: string
  base: string | null
  head: string | null
  truncated: boolean
  files: SideTaskDiffFile[]
  diff: string
}

/** Chat row as returned by GET /api/bots/{id}/chats (includes side-task chats). */
export interface BackendChat {
  id: string
  botId: string
  title: string
  platform: string | null
  platformChatId: string | null
  pinned: boolean
  archived: boolean
  parentChatId: string | null
  createdAt: string
  updatedAt: string
}

/** Message row as returned by GET /api/bots/{id}/chats/{chatId}/messages. */
export interface BackendMessage {
  id: string
  chatId: string
  role: string
  content: string
  timestamp: string
  metadata: Record<string, unknown>
  replyToId: string | null
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
  timezone: string
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
// CODING AGENT TYPES
// =============================================================================

export interface CodingAgentInfo {
  id: string
  name: string
  available: boolean
  binary: string
  custom_path: boolean
}

export interface CodingAgentsResponse {
  agents: CodingAgentInfo[]
  default_agent: string
}

// =============================================================================
// ARTIFACT TYPES
// =============================================================================

export type ArtifactType = 'code' | 'html' | 'markdown' | 'svg' | 'mermaid' | 'react' | 'image' | 'custom' | 'document'

export interface Artifact {
  id: string
  type: ArtifactType
  title: string
  content: string
  language?: string
  metadata?: Record<string, unknown>
  plugin?: string
  version: number
  botId?: string
  chatId?: string
  messageId?: string
}

export interface ArtifactUpdatePayload {
  id: string
  content?: string
  title?: string
  metadata?: Record<string, unknown>
  version?: number
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
  | 'instruction_delta'
  | 'message'
  | 'platform_message'
  | 'scheduled_notification'
  | 'document_status'
  | 'connection_status'
  | 'artifact'
  | 'artifact_update'
  | 'workspace_progress'
  | 'approval_needed'
  | 'usage'
  | 'error'
  | 'done'
  | 'job_update'
  | 'message_update'
  | 'task_update'
  | 'side_task_update'
  | 'computer_update'
  | 'faro_update'

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

export type BotView = 'chats' | 'rooms' | 'work' | 'automations' | 'routines' | 'voice' | 'tools' | 'plugins' | 'developer' | 'settings' | 'computer'
export type WorkSection = 'overview' | 'active' | 'completed' | 'history' | 'quick-tasks'
export type AutomationSection = 'routines' | 'advanced'
export type AppView = 'dashboard' | 'dashboard-usage' | 'runs' | 'admin-logs' | 'settings'

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
// COMMAND TYPES
// =============================================================================

export interface CommandDescriptor {
  prefix: string
  name: string
  display_name: string
  description: string
  source: string  // "user_skill" | "bot_instruction" | "cli"
  execution_mode: 'native' | 'passthrough'
  instructions?: string
  cli_binary?: string
  tags: string[]
  icon?: string
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
  external?: boolean           // true for external (user-installed) plugins
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

// External plugin info (from /api/plugins/external)
export interface ExternalPluginInfo {
  name: string
  displayName: string
  description: string
  version: string
  author: string
  type: 'tool' | 'view'
  icon: string
  color: string
  group: string
  capabilityKey: string
  contexts: string[]
  allowLateActivation: boolean
  requires: {
    python: string
    filesystem: boolean
    network: boolean
    imports: string[]
  }
  permissions: {
    allowEnvVars: string[]
    allowPaths: string[]
  }
  config: {
    name: string
    displayName: string
    type: string
    default: unknown
    description: string
    options?: string[]
  }[]
  view: {
    route: string
    navLabel: string
    navIcon: string
  } | null
  loaded: boolean
  error: string | null
  external: true
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
  response_mode: 'parallel' | 'sequential' | 'chain' | 'router' | 'debate' | 'waterfall' | 'relay' | 'consensus' | 'interview'
  debate_rounds?: number
  debate_positions?: Record<string, string>
  debate_judge_bot_id?: string | null
  debate_judge_prompt?: string
  routing_strategy?: 'llm' | 'keyword' | 'round_robin'
  bot_keywords?: Record<string, string[]>
  waterfall_conditions?: Record<string, string>

  // Room personality — injected into all bots' context
  system_prompt?: string

  // Room variables — key-value pairs accessible to all bots
  variables?: Record<string, string>

  // Consensus mode
  consensus_synthesizer_bot_id?: string | null
  consensus_show_individual?: boolean

  // Interview mode
  interview_bot_id?: string | null
  interview_max_questions?: number
  interview_handoff_trigger?: 'auto' | 'manual' | 'keyword'

  // Auto-summary
  auto_summary_interval?: number
  auto_summary_bot_id?: string | null
  auto_summary_auto_pin?: boolean
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
  lastMessage?: RoomMessage | null
  createdAt: string
  updatedAt: string
}

// Reaction types
export interface ReactionSummary {
  emoji: string
  count: number
  userIds: string[]
}

// Pinned message types
export interface PinnedMessage {
  id: string
  roomId: string
  messageId: string
  pinnedBy: string
  pinnedAt: string
  senderName: string
  content: string
  timestamp: string
}

// Bookmarked message types
export interface BookmarkedMessage {
  id: string
  roomId: string
  messageId: string
  createdAt: string
  senderName: string
  content: string
  timestamp: string
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
  reactions?: ReactionSummary[]
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
  // Social features
  | 'room_reaction_add'
  | 'room_reaction_remove'
  | 'room_pin_add'
  | 'room_pin_remove'
  | 'room_variable_update'
  // Consensus mode
  | 'room_consensus_synthesizing'
  | 'room_consensus_complete'
  // Interview mode
  | 'room_interview_question'
  | 'room_interview_handoff'
  // Automations
  | 'room_automation_triggered'

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

// =============================================================================
// ROOM AUTOMATIONS
// =============================================================================

export type AutomationTriggerType = 'on_message' | 'on_keyword' | 'on_idle' | 'on_schedule'
export type AutomationActionType = 'send_message' | 'summarize' | 'pin_message'

export interface RoomAutomation {
  id: string
  roomId: string
  name: string
  enabled: boolean
  triggerType: AutomationTriggerType
  triggerConfig: Record<string, unknown>
  actionType: AutomationActionType
  actionConfig: Record<string, unknown>
  createdBy: string
  triggerCount: number
  createdAt: string
  updatedAt: string
}

// =============================================================================
// ROOM TASK TYPES
// =============================================================================

export type RoomTaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'
export type RoomTaskPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface RoomTask {
  id: string
  roomId: string
  title: string
  description: string | null
  status: RoomTaskStatus
  priority: RoomTaskPriority
  position: number
  assignedToBotId: string | null
  assignedToUserId: string | null
  createdByUserId: string | null
  createdByBotId: string | null
  tags: string[]
  dueAt: string | null
  createdAt: string
  updatedAt: string
}

export type RoomTaskEventAction =
  | 'created'
  | 'updated'
  | 'status_changed'
  | 'priority_changed'
  | 'assigned'
  | 'deleted'

export interface RoomTaskEvent {
  id: string
  taskId: string
  roomId: string
  action: RoomTaskEventAction
  field: string | null
  oldValue: string | null
  newValue: string | null
  actorUserId: string | null
  actorBotId: string | null
  createdAt: string
}

export interface CreateRoomTaskRequest {
  title: string
  description?: string
  status?: RoomTaskStatus
  priority?: RoomTaskPriority
  assigned_to_bot_id?: string
  assigned_to_user_id?: string
  tags?: string[]
  due_at?: string
}

export interface UpdateRoomTaskRequest {
  title?: string
  description?: string
  status?: RoomTaskStatus
  priority?: RoomTaskPriority
  assigned_to_bot_id?: string
  assigned_to_user_id?: string
  tags?: string[]
  due_at?: string
}

// =============================================================================
// ASSET TYPES
// =============================================================================

export type AssetOwnerType = 'room' | 'chat'

export interface Asset {
  id: string
  ownerType: AssetOwnerType
  ownerId: string
  name: string
  originalFilename: string
  contentType: string
  sizeBytes: number
  uploadedByUserId: string | null
  uploadedByBotId: string | null
  metadata: Record<string, unknown>
  createdAt: string
}
