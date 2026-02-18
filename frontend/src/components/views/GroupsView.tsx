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
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-white">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-sm border-b border-zinc-200 dark:border-zinc-800">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
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
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
              {/* Table Header */}
              <div className="grid grid-cols-[1fr_1fr_80px_120px_48px] gap-4 px-4 py-3 bg-zinc-100 dark:bg-zinc-800/50 text-sm text-zinc-500 dark:text-zinc-400 font-medium">
                <div>Group Name</div>
                <div>Description</div>
                <div>Members</div>
                <div>Created By</div>
                <div></div>
              </div>

              {/* Group Rows */}
              {groups.length === 0 ? (
                <div className="px-4 py-8 text-center text-zinc-500">No groups found</div>
              ) : (
                groups.map((group) => (
                  <div
                    key={group.id}
                    className={`grid grid-cols-[1fr_1fr_80px_120px_48px] gap-4 px-4 py-3 border-t border-zinc-200 dark:border-zinc-800 items-center hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors cursor-pointer ${
                      activeGroupId === group.id ? 'bg-zinc-100 dark:bg-zinc-800/40' : ''
                    }`}
                    onClick={() =>
                      setActiveGroupId(activeGroupId === group.id ? null : group.id)
                    }
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center">
                        <Users className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                      </div>
                      <div className="font-medium truncate">{group.name}</div>
                    </div>
                    <div className="text-zinc-500 dark:text-zinc-400 truncate">
                      {group.description || '\u2014'}
                    </div>
                    <div className="text-zinc-700 dark:text-zinc-300">{group.member_count}</div>
                    <div className="text-zinc-500 dark:text-zinc-400 truncate text-sm">
                      {group.created_by === currentUser?.id ? 'You' : group.created_by}
                    </div>
                    <div className="relative" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() =>
                          setMenuOpen(menuOpen === group.id ? null : group.id)
                        }
                        className="p-1.5 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded transition-colors"
                      >
                        <MoreVertical className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                      </button>
                      {menuOpen === group.id && (
                        <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-zinc-200 dark:bg-zinc-800 dark:border-zinc-700 rounded-lg shadow-lg py-1 z-20">
                          <button
                            onClick={() => {
                              setActiveGroupId(group.id)
                              setMenuOpen(null)
                            }}
                            className="w-full px-3 py-2 text-left text-sm hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
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
                                className="w-full px-3 py-2 text-left text-sm hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                              >
                                Edit Group
                              </button>
                              <button
                                onClick={() => handleDeleteGroup(group.id)}
                                className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
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

            <p className="text-sm text-zinc-500 mt-4 text-center">
              {groups.length} group{groups.length !== 1 ? 's' : ''} total
            </p>
          </div>

          {/* Group Detail Panel */}
          {activeGroupId && (
            <div className="w-96 shrink-0">
              <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                {loadingDetail ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                  </div>
                ) : activeGroup ? (
                  <>
                    {/* Detail Header */}
                    <div className="px-4 py-4 border-b border-zinc-200 dark:border-zinc-800">
                      <div className="flex items-center justify-between mb-2">
                        <h2 className="text-lg font-semibold">{activeGroup.name}</h2>
                        <button
                          onClick={() => setActiveGroupId(null)}
                          className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                        >
                          <X className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                        </button>
                      </div>
                      {activeGroup.description && (
                        <p className="text-sm text-zinc-500 dark:text-zinc-400">{activeGroup.description}</p>
                      )}
                    </div>

                    {/* Members Header */}
                    <div className="px-4 py-3 flex items-center justify-between bg-zinc-100 dark:bg-zinc-800/50">
                      <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                        Members ({activeGroup.members.length})
                      </span>
                      <button
                        onClick={() => setShowAddMemberModal(true)}
                        className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Add Member
                      </button>
                    </div>

                    {/* Members List */}
                    <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
                      {activeGroup.members.length === 0 ? (
                        <div className="px-4 py-6 text-center text-zinc-500 text-sm">
                          No members yet
                        </div>
                      ) : (
                        activeGroup.members.map((member: GroupMember) => (
                          <div
                            key={member.user_id}
                            className="px-4 py-3 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="w-8 h-8 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center shrink-0">
                                {member.role === 'owner' ? (
                                  <Shield className="h-4 w-4 text-purple-400" />
                                ) : (
                                  <UserIcon className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                                )}
                              </div>
                              <div className="min-w-0">
                                <div className="font-medium text-sm truncate">
                                  {member.username}
                                  {member.user_id === currentUser?.id && (
                                    <span className="text-xs text-blue-400 ml-1.5">
                                      You
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-zinc-500 truncate">
                                  {member.email}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                  member.role === 'owner'
                                    ? 'bg-purple-500/20 text-purple-300'
                                    : 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300'
                                }`}
                              >
                                {member.role}
                              </span>
                              {member.user_id !== currentUser?.id && (
                                <button
                                  onClick={() => handleRemoveMember(member.user_id)}
                                  className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded transition-colors text-zinc-500 hover:text-red-400"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl border border-zinc-200 dark:bg-zinc-900 dark:border-zinc-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Create New Group</h2>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-white border border-zinc-300 rounded-lg text-zinc-900 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                  placeholder="Group name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                  Description
                </label>
                <input
                  type="text"
                  value={createForm.description}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, description: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-white border border-zinc-300 rounded-lg text-zinc-900 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl border border-zinc-200 dark:bg-zinc-900 dark:border-zinc-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Add Member</h2>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                  User ID
                </label>
                <input
                  type="text"
                  value={addMemberForm.userId}
                  onChange={(e) =>
                    setAddMemberForm({ ...addMemberForm, userId: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-white border border-zinc-300 rounded-lg text-zinc-900 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                  placeholder="Enter user ID"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
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
                  className="w-full px-3 py-2 bg-white border border-zinc-300 rounded-lg text-zinc-900 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
