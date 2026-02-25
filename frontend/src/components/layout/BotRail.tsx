import { useState, useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Plus, Settings, LayoutDashboard, Github, Activity, Folder, ChevronDown } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { Modifier } from '@dnd-kit/core'

// Lock drag to vertical axis only
const restrictToVerticalAxis: Modifier = (args) => ({
  ...args.transform,
  x: 0,
})
import { useBotStore, useChatStore } from '../../stores/bots'
import { useRailStore } from '../../stores/rail'
import { useUIStore } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'
import type { Bot, BotGroup } from '../../types'

// App-level paths (not bot views)
const appPaths = ['/dashboard', '/settings', '/admin/logs']

interface BotRailProps {
  onNavigate?: () => void
}

export function BotRail({ onNavigate }: BotRailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { bots, activeBotId, setActiveBot } = useBotStore()
  const { setActiveChat } = useChatStore()
  const { setCreateBotOpen } = useUIStore()
  const { railOrder, botGroups, moveItem, addBotToGroup, initFromBots } = useRailStore()

  const [activeDragId, setActiveDragId] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{
    x: number
    y: number
    botId?: string
    groupId?: string
  } | null>(null)

  // Initialize rail from existing bots on first load
  useEffect(() => {
    initFromBots()
  }, [initFromBots])

  // Close context menu on any click outside
  useEffect(() => {
    if (!contextMenu) return
    const handle = () => setContextMenu(null)
    // Use timeout so the current click that opened the menu doesn't close it
    const id = setTimeout(() => document.addEventListener('click', handle), 0)
    return () => {
      clearTimeout(id)
      document.removeEventListener('click', handle)
    }
  }, [contextMenu])

  // Derive current app view from URL
  const currentPath = location.pathname
  const isAppView = appPaths.some((p) => currentPath === p || currentPath.startsWith(p + '/'))

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const handleBotClick = useCallback((botId: string) => {
    setActiveBot(botId)
    setActiveChat(null)
    navigate(`/${botId}/chats`)
    onNavigate?.()
  }, [setActiveBot, setActiveChat, navigate, onNavigate])

  const handleAppViewClick = useCallback((path: string) => {
    if (currentPath === path) {
      navigate('/')
    } else {
      navigate(path)
    }
    onNavigate?.()
  }, [currentPath, navigate, onNavigate])

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveDragId(event.active.id as string)
  }, [])

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveDragId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeId = active.id as string
    const overId = over.id as string

    // Extract real bot/group IDs from sortable IDs
    // Top-level items: "rail-<botId>" or "rail-<groupId>"
    // Grouped items: "<groupId>-<botId>"
    const isActiveTopLevel = activeId.startsWith('rail-')
    const isOverTopLevel = overId.startsWith('rail-')

    // Get the source bot ID regardless of where it lives
    const activeBotId = isActiveTopLevel
      ? activeId.slice(5) // "rail-xxx" -> "xxx"
      : activeId.slice(activeId.indexOf('-') + 1) // "groupId-botId" -> "botId"

    // Check if active is actually a bot (not a group)
    const activeIsBot = isActiveTopLevel
      ? railOrder.some((item) => item.type === 'bot' && item.botId === activeBotId)
      : true // grouped items are always bots

    // Check if we dropped onto a group folder
    if (isOverTopLevel && activeIsBot) {
      const overKey = overId.slice(5)
      const targetGroup = botGroups.find((g) => g.id === overKey)
      if (targetGroup) {
        // Dropped a bot onto a group folder — add it to that group
        addBotToGroup(targetGroup.id, activeBotId)
        return
      }
    }

    // Same-group reorder
    if (!isActiveTopLevel && !isOverTopLevel) {
      const activeGroupId = activeId.slice(0, activeId.indexOf('-'))
      const overGroupId = overId.slice(0, overId.indexOf('-'))
      if (activeGroupId === overGroupId) {
        const group = botGroups.find((g) => g.id === activeGroupId)
        if (!group) return
        const fromBotId = activeId.slice(activeGroupId.length + 1)
        const toBotId = overId.slice(overGroupId.length + 1)
        const fromIndex = group.botIds.indexOf(fromBotId)
        const toIndex = group.botIds.indexOf(toBotId)
        if (fromIndex >= 0 && toIndex >= 0) {
          useRailStore.getState().moveBotWithinGroup(activeGroupId, fromIndex, toIndex)
        }
        return
      }
    }

    // Top-level rail reorder (both items are top-level)
    if (isActiveTopLevel && isOverTopLevel) {
      const sortIds = railOrder.map((item) =>
        item.type === 'bot' ? `rail-${item.botId}` : `rail-${item.groupId}`
      )
      const fromIndex = sortIds.indexOf(activeId)
      const toIndex = sortIds.indexOf(overId)
      if (fromIndex >= 0 && toIndex >= 0) {
        moveItem(fromIndex, toIndex)
      }
    }
  }, [railOrder, botGroups, moveItem, addBotToGroup])

  const handleContextMenu = useCallback((e: React.MouseEvent, botId?: string, groupId?: string) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({ x: e.clientX, y: e.clientY, botId, groupId })
  }, [])

  // Build the sortable ID list for the top-level rail
  const sortableIds = railOrder.map((item) =>
    item.type === 'bot' ? `rail-${item.botId}` : `rail-${item.groupId}`
  )

  // Find the bot being dragged (for overlay)
  const draggedBot = activeDragId
    ? bots.find((b) => activeDragId === `rail-${b.id}` || activeDragId.endsWith(`-${b.id}`))
    : null

  return (
    <div className="bot-rail">
      {/* App-level navigation */}
      <div className="bot-rail__section">
        <button
          onClick={() => handleAppViewClick('/dashboard')}
          className={cn(
            'bot-rail__avatar-btn',
            currentPath === '/dashboard' && 'bot-rail__avatar-btn--active'
          )}
        >
          <LayoutDashboard className="h-5 w-5" />
          <Tooltip>Dashboard</Tooltip>
        </button>

        <div className="bot-rail__divider" />
      </div>

      {/* Bot avatars — sortable */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        modifiers={[restrictToVerticalAxis]}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
          <div className="bot-rail__scroll">
            {railOrder.map((item) => {
              if (item.type === 'bot') {
                const bot = bots.find((b) => b.id === item.botId)
                if (!bot) return null
                return (
                  <SortableBotAvatar
                    key={bot.id}
                    id={`rail-${bot.id}`}
                    bot={bot}
                    active={
                      bot.id === activeBotId &&
                      !isAppView &&
                      currentPath.startsWith(`/${bot.id}/`)
                    }
                    isDragging={activeDragId === `rail-${bot.id}`}
                    onClick={() => handleBotClick(bot.id)}
                    onContextMenu={(e) => handleContextMenu(e, bot.id)}
                  />
                )
              }

              // Group
              const group = botGroups.find((g) => g.id === item.groupId)
              if (!group) return null
              return (
                <BotGroupItem
                  key={group.id}
                  id={`rail-${group.id}`}
                  group={group}
                  bots={bots}
                  activeBotId={activeBotId}
                  isAppView={isAppView}
                  currentPath={currentPath}
                  activeDragId={activeDragId}
                  onBotClick={handleBotClick}
                  onContextMenu={handleContextMenu}
                />
              )
            })}

            {/* Add bot button */}
            <button
              onClick={() => setCreateBotOpen(true)}
              className="bot-rail__avatar-btn"
            >
              <Plus className="h-5 w-5" />
              <Tooltip>Create Bot</Tooltip>
            </button>
          </div>
        </SortableContext>

        <DragOverlay>
          {draggedBot ? (
            <div
              className="bot-rail__avatar-btn bot-rail__avatar-btn--active"
              style={{ '--bot-color': draggedBot.color } as React.CSSProperties}
            >
              <BotIconRenderer icon={draggedBot.icon} className="h-6 w-6" size={24} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Bottom actions */}
      <div className="bot-rail__bottom">
        <div className="bot-rail__divider" />

        <button
          onClick={() => handleAppViewClick('/admin/logs')}
          className={cn(
            'bot-rail__action-btn',
            currentPath === '/admin/logs' && 'bot-rail__action-btn--active'
          )}
        >
          <Activity className="h-5 w-5" />
          <Tooltip>Exec Logs</Tooltip>
        </button>

        <a
          href="https://github.com/jhd3197/CachiBot"
          target="_blank"
          rel="noopener noreferrer"
          className="bot-rail__action-btn"
        >
          <Github className="h-5 w-5" />
          <Tooltip>GitHub</Tooltip>
        </a>

        <button
          onClick={() => handleAppViewClick('/settings')}
          className={cn(
            'bot-rail__action-btn',
            (currentPath === '/settings' || currentPath.startsWith('/settings/')) && 'bot-rail__action-btn--active'
          )}
        >
          <Settings className="h-5 w-5" />
          <Tooltip>Settings</Tooltip>
        </button>
      </div>

      {/* Context menu — portaled to body to escape stacking context */}
      {contextMenu && createPortal(
        <BotRailContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          botId={contextMenu.botId}
          groupId={contextMenu.groupId}
          botGroups={botGroups}
          onClose={() => setContextMenu(null)}
        />,
        document.body
      )}
    </div>
  )
}

// =============================================================================
// Sortable Bot Avatar
// =============================================================================

interface SortableBotAvatarProps {
  id: string
  bot: Bot
  active: boolean
  isDragging: boolean
  onClick: () => void
  onContextMenu: (e: React.MouseEvent) => void
}

function SortableBotAvatar({ id, bot, active, isDragging, onClick, onContextMenu }: SortableBotAvatarProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const accessLevel = (bot as unknown as Record<string, unknown>).access_level as string | undefined
  const isShared = accessLevel && accessLevel !== 'owner'

  return (
    <button
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      onContextMenu={onContextMenu}
      className={cn('group relative', isDragging && 'bot-rail__avatar-btn--dragging')}
    >
      <div
        className={cn(
          'bot-rail__active-indicator',
          active && 'bot-rail__active-indicator--active'
        )}
      />

      <div
        className={cn(
          'bot-rail__avatar-btn',
          active && 'bot-rail__avatar-btn--active'
        )}
        style={{ '--bot-color': bot.color } as React.CSSProperties}
      >
        <BotIconRenderer icon={bot.icon} className="h-6 w-6" size={24} />
      </div>

      {isShared && (
        <div
          className={cn(
            'bot-rail__shared-dot',
            accessLevel === 'viewer' ? 'bot-rail__shared-dot--viewer' :
            accessLevel === 'operator' ? 'bot-rail__shared-dot--operator' :
            'bot-rail__shared-dot--editor'
          )}
          title={`Shared (${accessLevel})`}
        />
      )}

      <Tooltip>{bot.name}{isShared ? ` (${accessLevel})` : ''}</Tooltip>
    </button>
  )
}

// =============================================================================
// Bot Group Item
// =============================================================================

interface BotGroupItemProps {
  id: string
  group: BotGroup
  bots: Bot[]
  activeBotId: string | null
  isAppView: boolean
  currentPath: string
  activeDragId: string | null
  onBotClick: (botId: string) => void
  onContextMenu: (e: React.MouseEvent, botId?: string, groupId?: string) => void
}

function BotGroupItem({
  id,
  group,
  bots,
  activeBotId,
  isAppView,
  currentPath,
  activeDragId,
  onBotClick,
  onContextMenu,
}: BotGroupItemProps) {
  const { toggleGroupCollapse } = useRailStore()

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  // Check if any bot in this group is active
  const hasActiveBotInGroup = group.botIds.some(
    (botId) => botId === activeBotId && !isAppView && currentPath.startsWith(`/${botId}/`)
  )

  const groupBotIds = group.botIds.map((botId) => `${group.id}-${botId}`)

  return (
    <div ref={setNodeRef} style={style} className="bot-rail__group">
      {/* Group folder button */}
      <button
        {...attributes}
        {...listeners}
        onClick={() => toggleGroupCollapse(group.id)}
        onContextMenu={(e) => onContextMenu(e, undefined, group.id)}
        className="group relative"
      >
        <div
          className={cn(
            'bot-rail__group-btn',
            hasActiveBotInGroup && 'bot-rail__group-btn--active'
          )}
        >
          <Folder className="h-5 w-5" />
          <ChevronDown
            className={cn(
              'bot-rail__group-chevron',
              group.collapsed && 'bot-rail__group-chevron--collapsed'
            )}
          />
        </div>

        {/* Count badge */}
        <div className="bot-rail__group-count">{group.botIds.length}</div>

        <Tooltip>{group.name}</Tooltip>
      </button>

      {/* Expanded bot list */}
      {!group.collapsed && group.botIds.length > 0 && (
        <SortableContext items={groupBotIds} strategy={verticalListSortingStrategy}>
          <div className="bot-rail__group-items">
            {group.botIds.map((botId) => {
              const bot = bots.find((b) => b.id === botId)
              if (!bot) return null
              return (
                <SortableBotAvatar
                  key={`${group.id}-${botId}`}
                  id={`${group.id}-${botId}`}
                  bot={bot}
                  active={
                    bot.id === activeBotId &&
                    !isAppView &&
                    currentPath.startsWith(`/${bot.id}/`)
                  }
                  isDragging={activeDragId === `${group.id}-${botId}`}
                  onClick={() => onBotClick(bot.id)}
                  onContextMenu={(e) => onContextMenu(e, bot.id, group.id)}
                />
              )
            })}
          </div>
        </SortableContext>
      )}
    </div>
  )
}

// =============================================================================
// Context Menu
// =============================================================================

interface BotRailContextMenuProps {
  x: number
  y: number
  botId?: string
  groupId?: string
  botGroups: BotGroup[]
  onClose: () => void
}

function BotRailContextMenu({ x, y, botId, groupId, botGroups, onClose }: BotRailContextMenuProps) {
  const { createGroup, deleteGroup, renameGroup, addBotToGroup, removeBotFromGroup } = useRailStore()
  const bots = useBotStore((s) => s.bots)
  const menuRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [subMenu, setSubMenu] = useState<'add-to-group' | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState('')

  // Auto-focus rename input
  useEffect(() => {
    if (renaming) inputRef.current?.focus()
  }, [renaming])

  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    left: x,
    top: y,
    zIndex: 9999,
  }

  // Stop clicks inside the menu from bubbling to the document listener
  const stopProp = (e: React.MouseEvent) => e.stopPropagation()

  const handleCreateGroup = () => {
    const existing = botGroups.length
    const defaultName = `Group ${existing + 1}`
    const bot = botId ? bots.find((b) => b.id === botId) : null
    const name = bot ? bot.name : defaultName
    createGroup(name, botId)
    onClose()
  }

  const handleAddToGroup = (targetGroupId: string) => {
    if (botId) addBotToGroup(targetGroupId, botId)
    onClose()
  }

  const handleRemoveFromGroup = () => {
    if (botId && groupId) removeBotFromGroup(groupId, botId)
    onClose()
  }

  const handleStartRename = () => {
    const group = botGroups.find((g) => g.id === groupId)
    setRenameValue(group?.name ?? '')
    setRenaming(true)
  }

  const handleRenameSubmit = () => {
    const name = renameValue.trim()
    if (!name || !groupId) return
    renameGroup(groupId, name)
    onClose()
  }

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleRenameSubmit()
    else if (e.key === 'Escape') { setRenaming(false); setRenameValue('') }
  }

  const handleDeleteGroup = () => {
    if (!groupId) return
    deleteGroup(groupId)
    onClose()
  }

  // Bot right-click in top-level rail (no group)
  if (botId && !groupId) {
    return (
      <div ref={menuRef} className="context-menu" style={menuStyle} onClick={stopProp}>
        <button className="context-menu__item" onClick={handleCreateGroup}>
          Create Group
        </button>
        {botGroups.length > 0 && (
          <>
            <div className="context-menu__divider" />
            {subMenu === 'add-to-group' ? (
              botGroups.map((g) => (
                <button
                  key={g.id}
                  className="context-menu__item"
                  onClick={() => handleAddToGroup(g.id)}
                >
                  {g.name}
                </button>
              ))
            ) : (
              <button
                className="context-menu__item"
                onClick={() => setSubMenu('add-to-group')}
              >
                Add to Group &rsaquo;
              </button>
            )}
          </>
        )}
      </div>
    )
  }

  // Bot right-click inside a group
  if (botId && groupId) {
    return (
      <div ref={menuRef} className="context-menu" style={menuStyle} onClick={stopProp}>
        <button className="context-menu__item" onClick={handleRemoveFromGroup}>
          Remove from Group
        </button>
        {botGroups.length > 1 && (
          <>
            <div className="context-menu__divider" />
            {subMenu === 'add-to-group' ? (
              botGroups
                .filter((g) => g.id !== groupId)
                .map((g) => (
                  <button
                    key={g.id}
                    className="context-menu__item"
                    onClick={() => handleAddToGroup(g.id)}
                  >
                    {g.name}
                  </button>
                ))
            ) : (
              <button
                className="context-menu__item"
                onClick={() => setSubMenu('add-to-group')}
              >
                Move to Group &rsaquo;
              </button>
            )}
          </>
        )}
      </div>
    )
  }

  // Group right-click
  if (groupId) {
    return (
      <div ref={menuRef} className="context-menu" style={menuStyle} onClick={stopProp}>
        {renaming ? (
          <div className="bot-rail__context-input">
            <input
              ref={inputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={handleRenameKeyDown}
              placeholder="Group name"
              className="bot-rail__context-input-field"
            />
            <button
              className="bot-rail__context-input-ok"
              onClick={handleRenameSubmit}
              disabled={!renameValue.trim()}
            >
              OK
            </button>
          </div>
        ) : (
          <>
            <button className="context-menu__item" onClick={handleStartRename}>
              Rename Group
            </button>
            <div className="context-menu__divider" />
            <button
              className="context-menu__item context-menu__item--danger"
              onClick={handleDeleteGroup}
            >
              Delete Group
            </button>
          </>
        )}
      </div>
    )
  }

  return null
}

// =============================================================================
// Tooltip
// =============================================================================

function Tooltip({ children }: { children: React.ReactNode }) {
  return (
    <div className="bot-rail__tooltip">
      {children}
      <div className="bot-rail__tooltip-arrow" />
    </div>
  )
}
