import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users,
  UserPlus,
  Shield,
  User as UserIcon,
  MoreVertical,
  Check,
  X,
  ArrowLeft,
  Loader2,
  Mail,
  AtSign,
} from 'lucide-react'
import { toast } from 'sonner'
import { listUsers, createUser, updateUser, deactivateUser } from '../../api/auth'
import { useAuthStore } from '../../stores/auth'
import { Button } from '../common/Button'
import type { User, UserRole } from '../../types'

export function UsersView() {
  const navigate = useNavigate()
  const { user: currentUser } = useAuthStore()

  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Create user modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({
    email: '',
    username: '',
    password: '',
    role: 'user' as UserRole,
  })
  const [creating, setCreating] = useState(false)

  // Edit user state
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({
    email: '',
    username: '',
    role: 'user' as UserRole,
  })
  const [updating, setUpdating] = useState(false)

  // Context menu state
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const response = await listUsers()
      setUsers(response.users)
      setTotal(response.total)
    } catch {
      toast.error('Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.email || !createForm.username || !createForm.password) {
      toast.error('All fields are required')
      return
    }
    if (createForm.password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }

    setCreating(true)
    try {
      const newUser = await createUser(createForm)
      setUsers([newUser, ...users])
      setTotal(total + 1)
      setShowCreateModal(false)
      setCreateForm({ email: '', username: '', password: '', role: 'user' })
      toast.success('User created successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create user'
      toast.error(message)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    setUpdating(true)
    try {
      const updated = await updateUser(editingUser.id, editForm)
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)))
      setEditingUser(null)
      toast.success('User updated successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update user'
      toast.error(message)
    } finally {
      setUpdating(false)
    }
  }

  const handleDeactivateUser = async (userId: string) => {
    if (!confirm('Are you sure you want to deactivate this user?')) return

    try {
      await deactivateUser(userId)
      setUsers(users.map((u) => (u.id === userId ? { ...u, is_active: false } : u)))
      toast.success('User deactivated')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to deactivate user'
      toast.error(message)
    }
    setMenuOpen(null)
  }

  const startEditing = (user: User) => {
    setEditingUser(user)
    setEditForm({
      email: user.email,
      username: user.username,
      role: user.role,
    })
    setMenuOpen(null)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-zinc-950/80 backdrop-blur-sm border-b border-zinc-800">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-400" />
              <h1 className="text-lg font-semibold">User Management</h1>
            </div>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-[1fr_1fr_100px_100px_48px] gap-4 px-4 py-3 bg-zinc-800/50 text-sm text-zinc-400 font-medium">
            <div>User</div>
            <div>Email</div>
            <div>Role</div>
            <div>Status</div>
            <div></div>
          </div>

          {/* User Rows */}
          {users.length === 0 ? (
            <div className="px-4 py-8 text-center text-zinc-500">
              No users found
            </div>
          ) : (
            users.map((user) => (
              <div
                key={user.id}
                className="grid grid-cols-[1fr_1fr_100px_100px_48px] gap-4 px-4 py-3 border-t border-zinc-800 items-center hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                    <AtSign className="h-4 w-4 text-zinc-400" />
                  </div>
                  <div>
                    <div className="font-medium">{user.username}</div>
                    {user.id === currentUser?.id && (
                      <div className="text-xs text-blue-400">You</div>
                    )}
                  </div>
                </div>
                <div className="text-zinc-400 truncate">{user.email}</div>
                <div>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      user.role === 'admin'
                        ? 'bg-purple-500/20 text-purple-300'
                        : user.role === 'manager'
                          ? 'bg-teal-500/20 text-teal-300'
                          : 'bg-zinc-700 text-zinc-300'
                    }`}
                  >
                    {user.role === 'admin' ? (
                      <Shield className="h-3 w-3" />
                    ) : (
                      <UserIcon className="h-3 w-3" />
                    )}
                    {user.role}
                  </span>
                </div>
                <div>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-500/20 text-green-300'
                        : 'bg-red-500/20 text-red-300'
                    }`}
                  >
                    {user.is_active ? (
                      <Check className="h-3 w-3" />
                    ) : (
                      <X className="h-3 w-3" />
                    )}
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="relative">
                  <button
                    onClick={() => setMenuOpen(menuOpen === user.id ? null : user.id)}
                    className="p-1.5 hover:bg-zinc-700 rounded transition-colors"
                    disabled={user.id === currentUser?.id}
                  >
                    <MoreVertical className="h-4 w-4 text-zinc-400" />
                  </button>
                  {menuOpen === user.id && (
                    <div className="absolute right-0 top-full mt-1 w-40 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg py-1 z-20">
                      <button
                        onClick={() => startEditing(user)}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-zinc-700 transition-colors"
                      >
                        Edit User
                      </button>
                      {user.is_active && (
                        <button
                          onClick={() => handleDeactivateUser(user.id)}
                          className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-zinc-700 transition-colors"
                        >
                          Deactivate
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <p className="text-sm text-zinc-500 mt-4 text-center">
          {total} user{total !== 1 ? 's' : ''} total
        </p>
      </main>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Create New User</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                  <input
                    type="email"
                    value={createForm.email}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, email: e.target.value })
                    }
                    className="w-full pl-10 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Username
                </label>
                <div className="relative">
                  <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                  <input
                    type="text"
                    value={createForm.username}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, username: e.target.value })
                    }
                    className="w-full pl-10 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                    minLength={3}
                    maxLength={32}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, password: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Role
                </label>
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      role: e.target.value as UserRole,
                    })
                  }
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="user">User</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
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
                    'Create User'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Edit User</h2>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(e) =>
                    setEditForm({ ...editForm, username: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                  minLength={3}
                  maxLength={32}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Role
                </label>
                <select
                  value={editForm.role}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      role: e.target.value as UserRole,
                    })
                  }
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="user">User</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => setEditingUser(null)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={updating}>
                  {updating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Save Changes'
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
