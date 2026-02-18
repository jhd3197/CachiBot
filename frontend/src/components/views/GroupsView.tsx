import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users,
  UserPlus,
  ArrowLeft,
  MoreVertical,
  Loader2,
  Shield,
  User as UserIcon,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  listGroups,
  createGroup,
  getGroup,
  deleteGroup,
  addMember,
  removeMember,
} from '../../api/groups'
import { useAuthStore } from '../../stores/auth'
import { Button } from '../common/Button'
import type { Group, GroupWithMembers, GroupMember, GroupRole } from '../../types'

export function GroupsView() {
  const navigate = useNavigate()
  const { user: currentUser } = useAuthStore()

  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)

  // Create group modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
  })
  const [creating, setCreating] = useState(false)

  // Group detail panel state
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null)
  const [activeGroup, setActiveGroup] = useState<GroupWithMembers | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Add member modal state
  const [showAddMemberModal, setShowAddMemberModal] = useState(false)
  const [addMemberForm, setAddMemberForm] = useState({
    userId: '',
    role: 'member' as GroupRole,
  })
  const [addingMember, setAddingMember] = useState(false)

  // Context menu state
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  useEffect(() => {
    fetchGroups()
  }, [])

  useEffect(() => {
    if (activeGroupId) {
      fetchGroupDetail(activeGroupId)
    } else {
      setActiveGroup(null)
    }
  }, [activeGroupId])

  const fetchGroups = async () => {
    try {
      const response = await listGroups()
      setGroups(response)
    } catch {
      toast.error('Failed to load groups')
    } finally {
      setLoading(false)
    }
  }

  const fetchGroupDetail = async (groupId: string) => {
    setLoadingDetail(true)
    try {
      const group = await getGroup(groupId)
      setActiveGroup(group)
    } catch {
      toast.error('Failed to load group details')
      setActiveGroupId(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.name) {
      toast.error('Group name is required')
      return
    }

    setCreating(true)
    try {
      const newGroup = await createGroup({
        name: createForm.name,
        description: createForm.description || undefined,
      })
      setGroups([newGroup, ...groups])
      setShowCreateModal(false)
      setCreateForm({ name: '', description: '' })
      toast.success('Group created successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create group'
      toast.error(message)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteGroup = async (groupId: string) => {
    if (!confirm('Are you sure you want to delete this group?')) return

    try {
      await deleteGroup(groupId)
      setGroups(groups.filter((g) => g.id !== groupId))
      if (activeGroupId === groupId) {
        setActiveGroupId(null)
      }
      toast.success('Group deleted')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete group'
      toast.error(message)
    }
    setMenuOpen(null)
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeGroupId || !addMemberForm.userId) {
      toast.error('User ID is required')
      return
    }

    setAddingMember(true)
    try {
      const newMember = await addMember(activeGroupId, {
        user_id: addMemberForm.userId,
        role: addMemberForm.role,
      })
      if (activeGroup) {
        setActiveGroup({
          ...activeGroup,
          members: [...activeGroup.members, newMember],
          member_count: activeGroup.member_count + 1,
        })
      }
      setGroups(
        groups.map((g) =>
          g.id === activeGroupId ? { ...g, member_count: g.member_count + 1 } : g,
        ),
      )
      setShowAddMemberModal(false)
      setAddMemberForm({ userId: '', role: 'member' })
      toast.success('Member added successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add member'
      toast.error(message)
    } finally {
      setAddingMember(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!activeGroupId) return
    if (!confirm('Are you sure you want to remove this member?')) return

    try {
      await removeMember(activeGroupId, userId)
      if (activeGroup) {
        setActiveGroup({
          ...activeGroup,
          members: activeGroup.members.filter((m) => m.user_id !== userId),
          member_count: activeGroup.member_count - 1,
        })
      }
      setGroups(
        groups.map((g) =>
          g.id === activeGroupId ? { ...g, member_count: g.member_count - 1 } : g,
        ),
      )
      toast.success('Member removed')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to remove member'
      toast.error(message)
    }
  }

  const isGroupOwnerOrAdmin = (group: Group): boolean => {
    if (!currentUser) return false
    if (currentUser.role === 'admin') return true
    return group.created_by === currentUser.id
  }

  if (loading) {
    return (
      <div className="groups-view flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="groups-view">
      {/* Header */}
      <header className="groups-header">
        <div className="groups-header__inner">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="groups-header__back-btn"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-400" />
              <h1 className="text-lg font-semibold">Groups</h1>
            </div>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Create Group
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        <div className="flex gap-6">
          {/* Groups Table */}
          <div className={`${activeGroupId ? 'flex-1' : 'w-full'} transition-all`}>
            <div className="groups-table">
              {/* Table Header */}
              <div className="groups-table__header">
                <div>Group Name</div>
                <div>Description</div>
                <div>Members</div>
                <div>Created By</div>
                <div></div>
              </div>

              {/* Group Rows */}
              {groups.length === 0 ? (
                <div className="groups-table__empty">No groups found</div>
              ) : (
                groups.map((group) => (
                  <div
                    key={group.id}
                    className={`group-row ${activeGroupId === group.id ? 'group-row--active' : ''}`}
                    onClick={() =>
                      setActiveGroupId(activeGroupId === group.id ? null : group.id)
                    }
                  >
                    <div className="flex items-center gap-3">
                      <div className="group-row__avatar">
                        <Users className="group-row__avatar-icon" />
                      </div>
                      <div className="group-row__name">{group.name}</div>
                    </div>
                    <div className="group-row__description">
                      {group.description || '\u2014'}
                    </div>
                    <div className="group-row__member-count">{group.member_count}</div>
                    <div className="group-row__created-by">
                      {group.created_by === currentUser?.id ? 'You' : group.created_by}
                    </div>
                    <div className="relative" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() =>
                          setMenuOpen(menuOpen === group.id ? null : group.id)
                        }
                        className="group-menu-btn"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                      {menuOpen === group.id && (
                        <div className="group-context-menu">
                          <button
                            onClick={() => {
                              setActiveGroupId(group.id)
                              setMenuOpen(null)
                            }}
                            className="group-context-menu__item"
                          >
                            View Members
                          </button>
                          {isGroupOwnerOrAdmin(group) && (
                            <>
                              <button
                                onClick={() => {
                                  setActiveGroupId(group.id)
                                  setMenuOpen(null)
                                }}
                                className="group-context-menu__item"
                              >
                                Edit Group
                              </button>
                              <button
                                onClick={() => handleDeleteGroup(group.id)}
                                className="group-context-menu__item group-context-menu__item--danger"
                              >
                                Delete Group
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <p className="groups-table__count">
              {groups.length} group{groups.length !== 1 ? 's' : ''} total
            </p>
          </div>

          {/* Group Detail Panel */}
          {activeGroupId && (
            <div className="group-detail">
              <div className="group-detail__card">
                {loadingDetail ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                  </div>
                ) : activeGroup ? (
                  <>
                    {/* Detail Header */}
                    <div className="group-detail__header">
                      <div className="flex items-center justify-between mb-2">
                        <h2 className="group-detail__title">{activeGroup.name}</h2>
                        <button
                          onClick={() => setActiveGroupId(null)}
                          className="group-detail__close-btn"
                        >
                          <X className="group-detail__close-icon" />
                        </button>
                      </div>
                      {activeGroup.description && (
                        <p className="group-detail__description">{activeGroup.description}</p>
                      )}
                    </div>

                    {/* Members Header */}
                    <div className="group-members-header">
                      <span className="group-members-header__label">
                        Members ({activeGroup.members.length})
                      </span>
                      <button
                        onClick={() => setShowAddMemberModal(true)}
                        className="group-members-header__add-btn"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Add Member
                      </button>
                    </div>

                    {/* Members List */}
                    <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
                      {activeGroup.members.length === 0 ? (
                        <div className="group-members-empty">
                          No members yet
                        </div>
                      ) : (
                        activeGroup.members.map((member: GroupMember) => (
                          <div key={member.user_id} className="group-member">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="group-member__avatar">
                                {member.role === 'owner' ? (
                                  <Shield className="group-member__avatar-icon--owner" />
                                ) : (
                                  <UserIcon className="group-member__avatar-icon" />
                                )}
                              </div>
                              <div className="min-w-0">
                                <div className="group-member__name">
                                  {member.username}
                                  {member.user_id === currentUser?.id && (
                                    <span className="group-member__you-badge">
                                      You
                                    </span>
                                  )}
                                </div>
                                <div className="group-member__email">
                                  {member.email}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span
                                className={`group-member__role ${
                                  member.role === 'owner'
                                    ? 'group-member__role--owner'
                                    : 'group-member__role--member'
                                }`}
                              >
                                {member.role}
                              </span>
                              {member.user_id !== currentUser?.id && (
                                <button
                                  onClick={() => handleRemoveMember(member.user_id)}
                                  className="group-member__remove-btn"
                                  title="Remove member"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Create Group Modal */}
      {showCreateModal && (
        <div className="groups-modal">
          <div className="groups-modal__panel">
            <h2 className="groups-modal__title">Create New Group</h2>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="groups-modal__label">
                  Name
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  className="groups-modal__input"
                  required
                  placeholder="Group name"
                />
              </div>
              <div>
                <label className="groups-modal__label">
                  Description
                </label>
                <input
                  type="text"
                  value={createForm.description}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, description: e.target.value })
                  }
                  className="groups-modal__input"
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={creating}>
                  {creating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Create Group'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMemberModal && (
        <div className="groups-modal">
          <div className="groups-modal__panel">
            <h2 className="groups-modal__title">Add Member</h2>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="groups-modal__label">
                  User ID
                </label>
                <input
                  type="text"
                  value={addMemberForm.userId}
                  onChange={(e) =>
                    setAddMemberForm({ ...addMemberForm, userId: e.target.value })
                  }
                  className="groups-modal__input"
                  required
                  placeholder="Enter user ID"
                />
              </div>
              <div>
                <label className="groups-modal__label">
                  Role
                </label>
                <select
                  value={addMemberForm.role}
                  onChange={(e) =>
                    setAddMemberForm({
                      ...addMemberForm,
                      role: e.target.value as GroupRole,
                    })
                  }
                  className="groups-modal__select"
                >
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => setShowAddMemberModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={addingMember}>
                  {addingMember ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Add Member'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click outside to close menu */}
      {menuOpen && (
        <div
          className="fixed inset-0 z-10"
          onClick={() => setMenuOpen(null)}
        />
      )}
    </div>
  )
}
