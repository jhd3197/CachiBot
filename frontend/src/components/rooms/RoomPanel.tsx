import { useEffect, useState, useMemo } from 'react'
import { Settings, Users, Bot, Loader2, MessageSquare, LayoutGrid, Clock, Download, CheckSquare, FolderOpen, MoreHorizontal } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { useBotStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { useRoomWebSocket } from '../../hooks/useRoomWebSocket'
import { getRoomMessages, getRoom } from '../../api/rooms'
import { RoomMessageList } from '../chat/MessageList'
import { ToolCallList } from '../chat/ToolCallList'
import { ThinkingIndicator } from '../chat/ThinkingIndicator'
import { Spinner } from '../common/Spinner'
import { InputArea } from '../chat/InputArea'
import { RoomSettingsDialog } from './RoomSettingsDialog'
import { PinnedMessagesBar } from './PinnedMessagesBar'
import { DashboardCardsView } from './DashboardCardsView'
import { TimelineView } from './TimelineView'
import { RoomTasksView } from './RoomTasksView'
import { AssetsView } from '../common/AssetsView'
import { FilesSheet } from '../chat/FilesSheet'
import { BotAvatar } from '../common/Avatar'
import { V2Menu, V2MenuItem, V2MenuLabel, V2MenuDivider } from '../common/V2Menu'
import { useAuthStore } from '../../stores/auth'
import { downloadJson, slugify } from '../../lib/utils'
import type { Room } from '../../types'

interface RoomPanelProps {
  roomId: string
}

export function RoomPanel({ roomId }: RoomPanelProps) {
  const { messages, botStates, botActivity, typingUsers, onlineUsers, setMessages, updateRoom, deleteRoom, setActiveRoom, chainStep, routeDecision, activeToolCalls, thinkingContent, instructionDeltas, consensusState, interviewState, viewMode, setViewMode } = useRoomStore()
  const { bots } = useBotStore()
  const { showThinking } = useUIStore()
  const [room, setRoom] = useState<Room | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showMore, setShowMore] = useState(false)
  const [showFiles, setShowFiles] = useState(false)
  const [loading, setLoading] = useState(true)

  // Connect WebSocket only after the initial REST load finishes so that
  // setMessages() from the REST response cannot overwrite messages that
  // arrived via WebSocket in the meantime.
  const { isConnected, sendMessage, sendTyping } = useRoomWebSocket(loading ? null : roomId)
  const user = useAuthStore((s) => s.user)

  const roomMessages = messages[roomId] || []
  const roomBotStates = botStates[roomId] || {}
  const roomTyping = typingUsers[roomId] || []
  const roomOnline = onlineUsers[roomId] || []
  const roomChainStep = chainStep[roomId] || null
  const roomRouteDecision = routeDecision[roomId] || null

  // Load room data and transcript
  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const [roomData, msgs] = await Promise.all([
          getRoom(roomId),
          getRoomMessages(roomId),
        ])
        if (cancelled) return
        setRoom(roomData)
        setMessages(roomId, msgs)
      } catch {
        // Handled by error state
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [roomId, setMessages])

  const handleSettingsUpdate = (updated: Room) => {
    setRoom(updated)
    updateRoom(roomId, updated)
  }

  const handleDeleteRoom = () => {
    deleteRoom(roomId)
    setActiveRoom(null)
  }

  // All hooks must be above early returns (Rules of Hooks)
  const activeBots = Object.entries(roomBotStates).filter(
    ([, state]) => state !== 'idle'
  )
  const roomActiveToolCalls = activeToolCalls[roomId] || {}
  const allActiveToolCalls = useMemo(
    () => Object.values(roomActiveToolCalls).flat(),
    [roomActiveToolCalls]
  )
  const roomInstructionDeltas = instructionDeltas[roomId] || {}
  const roomBotActivity = botActivity[roomId] || {}
  const roomThinking = thinkingContent[roomId] || {}
  const thinkingBots = useMemo(
    () => Object.entries(roomThinking).filter(([, text]) => text),
    [roomThinking]
  )

  if (loading) {
    return (
      <div className="room-panel__loading">
        <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-text-secondary)' }} />
      </div>
    )
  }

  if (!room) {
    return (
      <div className="room-panel__empty">
        Room not found
      </div>
    )
  }

  // Is current user the creator?
  const isCreator = user?.id === room.creatorId
  const currentView = viewMode[roomId] || 'chat'

  // Members line per design 13 ("Writer, Researcher and you") — real names
  const membersLine = (() => {
    const names = room.bots.map((b) => b.botName).filter(Boolean)
    const others = room.members
      .filter((m) => m.userId !== user?.id)
      .map((m) => m.username)
      .filter(Boolean)
    const all = [...names, ...others]
    if (all.length === 0) return 'you'
    return all.length <= 2
      ? `${all.join(', ')} and you`
      : `${all.slice(0, -1).join(', ')} and you`
  })()

  return (
    <div className="room-panel">
      {/* Header (design 13): stacked bot avatars, room name, members line,
          Files + More on the right. Presence counters stay (real data); the
          legacy view toggle/export/settings live in the More menu. */}
      <div className="v2-room-header">
        <div className="v2-room-header__id">
          <span className="v2-room-header__avatars">
            {room.bots.slice(0, 4).map((b) => {
              const bot = bots.find((bot) => bot.id === b.botId)
              return (
                <BotAvatar
                  key={b.botId}
                  color={bot?.color || '#4ade80'}
                  name={b.botName || 'Bot'}
                  size={22}
                />
              )
            })}
          </span>
          <span className="v2-room-header__names">
            <span className="v2-room-header__title">{room.title}</span>
            <span className="v2-room-header__members">{membersLine}</span>
          </span>
          {!isConnected && (
            <span className="room-panel__reconnecting">Reconnecting...</span>
          )}
        </div>

        <div className="v2-room-header__actions">
          <div className="room-panel__counters">
            <div className="room-panel__counter">
              <Users size={13} />
              <span>{roomOnline.length}/{room.members.length}</span>
            </div>
            <div className="room-panel__counter">
              <Bot size={13} />
              <span>{room.bots.length}</span>
            </div>
          </div>

          <button
            type="button"
            className="v2-icon-btn"
            title="Files"
            aria-label="Files"
            onClick={() => setShowFiles(true)}
          >
            <FolderOpen size={17} strokeWidth={1.8} />
          </button>

          <div className="v2-room-header__more">
            <button
              type="button"
              className="v2-icon-btn"
              title="More"
              aria-label="More"
              aria-haspopup="menu"
              aria-expanded={showMore}
              onClick={(e) => { e.stopPropagation(); setShowMore((o) => !o) }}
            >
              <MoreHorizontal size={18} strokeWidth={1.8} />
            </button>
            {showMore && (
              <V2Menu className="v2-room-header__menu" onClose={() => setShowMore(false)}>
                <V2MenuLabel>View</V2MenuLabel>
                {(
                  [
                    ['chat', 'Chat', MessageSquare],
                    ['cards', 'Dashboard cards', LayoutGrid],
                    ['timeline', 'Timeline', Clock],
                    ['tasks', 'Tasks', CheckSquare],
                  ] as const
                ).map(([mode, label, Icon]) => (
                  <V2MenuItem
                    key={mode}
                    icon={<Icon size={16} strokeWidth={1.8} />}
                    suffix={currentView === mode ? '✓' : undefined}
                    onClick={() => { setViewMode(roomId, mode); setShowMore(false) }}
                  >
                    {label}
                  </V2MenuItem>
                ))}
                <V2MenuDivider />
                <V2MenuItem
                  icon={<Download size={16} strokeWidth={1.8} />}
                  onClick={() => {
                    const msgs = useRoomStore.getState().messages[roomId] || []
                    const date = new Date().toISOString().slice(0, 10)
                    downloadJson({
                      room: { id: room.id, title: room.title, description: room.description, settings: room.settings, members: room.members, bots: room.bots, createdAt: room.createdAt, updatedAt: room.updatedAt },
                      messages: msgs,
                      exportedAt: new Date().toISOString(),
                    }, `room-${slugify(room.title)}-${date}.json`)
                    setShowMore(false)
                  }}
                >
                  Export JSON
                </V2MenuItem>
                {isCreator && (
                  <>
                    <V2MenuDivider />
                    <V2MenuItem
                      icon={<Settings size={16} strokeWidth={1.8} />}
                      onClick={() => { setShowMore(false); setShowSettings(true) }}
                    >
                      Room settings
                    </V2MenuItem>
                  </>
                )}
              </V2Menu>
            )}
          </div>
        </div>
      </div>

      {/* Pinned messages bar */}
      <PinnedMessagesBar roomId={roomId} />

      {/* Chain step indicator */}
      {roomChainStep && (
        <div className="room-panel__chain-step">
          Step {roomChainStep.step}/{roomChainStep.totalSteps}: {roomChainStep.botName}
        </div>
      )}

      {/* Route decision indicator */}
      {roomRouteDecision && (
        <div className="room-panel__route-decision">
          Routed to {roomRouteDecision.botName} — {roomRouteDecision.reason}
        </div>
      )}

      {/* Consensus status indicator */}
      {consensusState[roomId] && (
        <div className="room-panel__consensus-status">
          <Spinner size="sm" label="" aria-hidden="true" />
          {consensusState[roomId].phase === 'collecting'
            ? `Collecting responses: ${consensusState[roomId].collected}/${consensusState[roomId].total} bots`
            : `${consensusState[roomId].synthesizerName} is synthesizing...`}
        </div>
      )}

      {/* Interview status indicator */}
      {interviewState[roomId] && !interviewState[roomId].handoffTriggered && (
        <div className="room-panel__interview-status">
          Question {interviewState[roomId].questionCount}/{interviewState[roomId].maxQuestions}
        </div>
      )}
      {interviewState[roomId]?.handoffTriggered && (
        <div className="room-panel__interview-status room-panel__interview-status--handoff">
          Interview complete — specialists responding
        </div>
      )}

      {/* Bot status bar */}
      {activeBots.length > 0 && (
        <div className="room-panel__status-bar">
          {activeBots.map(([botId, state]) => {
            const bot = room.bots.find((b) => b.botId === botId)
            const activity = roomBotActivity[botId]
            const statusText = activity
              ? `calling ${activity}`
              : state === 'thinking' ? 'thinking' : 'responding'
            return (
              <span
                key={botId}
                className={`room-panel__bot-status room-panel__bot-status--${state === 'thinking' ? 'thinking' : 'responding'}`}
              >
                <Spinner size="sm" label="" aria-hidden="true" />
                {bot?.botName || botId} is {statusText}...
              </span>
            )
          })}
        </div>
      )}

      {/* Main content area — switches between Chat, Cards, Timeline, Tasks, Assets */}
      {currentView === 'cards' ? (
        <DashboardCardsView roomId={roomId} messages={roomMessages} roomBots={room.bots} />
      ) : currentView === 'timeline' ? (
        <TimelineView roomId={roomId} roomBots={room.bots} />
      ) : currentView === 'tasks' ? (
        <RoomTasksView roomId={roomId} />
      ) : currentView === 'assets' ? (
        <AssetsView ownerType="room" ownerId={roomId} />
      ) : (
        <RoomMessageList messages={roomMessages} roomId={roomId}>
          {/* Active tool calls */}
          {allActiveToolCalls.length > 0 && (
            <div className="mt-4">
              <ToolCallList toolCalls={allActiveToolCalls} instructionDeltas={roomInstructionDeltas} />
            </div>
          )}

          {/* Thinking indicators */}
          {showThinking && thinkingBots.map(([botId, text]) => {
            const bot = room?.bots.find((b) => b.botId === botId)
            const label = bot?.botName || botId
            const markColor = bots.find((b) => b.id === botId)?.color
            return (
              <div key={botId} className="mt-4">
                <ThinkingIndicator content={text} label={`${label} is thinking`} markColor={markColor} />
              </div>
            )
          })}
        </RoomMessageList>
      )}

      {/* Typing indicators */}
      {roomTyping.length > 0 && (
        <div className="room-panel__typing">
          {roomTyping.map((t) => t.username).join(', ')}
          {roomTyping.length === 1 ? ' is' : ' are'} typing...
        </div>
      )}

      {/* Input — v2 composer (design 13) */}
      <InputArea
        onSend={sendMessage}
        onTyping={sendTyping}
        bots={room.bots}
        isConnected={isConnected}
        placeholder="Message the room · type @ to pick a bot"
      />

      {/* Settings dialog */}
      {showSettings && room && (
        <RoomSettingsDialog
          room={room}
          onClose={() => setShowSettings(false)}
          onUpdate={handleSettingsUpdate}
          onDelete={handleDeleteRoom}
        />
      )}

      {/* Files sheet (design 10/13) — the room's shared files; upload and
          delete stay reachable here, formerly in the assets view mode */}
      {showFiles && room && (
        <FilesSheet roomId={room.id} roomTitle={room.title} onClose={() => setShowFiles(false)} />
      )}
    </div>
  )
}
