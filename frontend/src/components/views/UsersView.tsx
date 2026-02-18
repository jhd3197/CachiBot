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
      <div className="users-loading">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="users-view">
      {/* Header */}
      <header className="users-header">
        <div className="users-header__inner">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="users-header__back-btn"
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
      <main className="users-content">
        <div className="users-table">
          {/* Table Header */}
          <div className="users-table__header">
            <div>User</div>
            <div>Email</div>
            <div>Role</div>
            <div>Status</div>
            <div></div>
          </div>

          {/* User Rows */}
          {users.length === 0 ? (
            <div className="users-table__empty">
              No users found
            </div>
          ) : (
            users.map((user) => (
              <div key={user.id} className="user-row">
                <div className="flex items-center gap-3">
                  <div className="user-row__avatar">
                    <AtSign className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="font-medium">{user.username}</div>
                    {user.id === currentUser?.id && (
                      <div className="user-row__self-tag">You</div>
                    )}
                  </div>
                </div>
                <div className="user-row__email">{user.email}</div>
                <div>
                  <span
                    className={`user-role ${
                      user.role === 'admin'
                        ? 'user-role--admin'
                        : user.role === 'manager'
                          ? 'user-role--manager'
                          : 'user-role--user'
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
                    className={`user-status ${
                      user.is_active
                        ? 'user-status--active'
                        : 'user-status--inactive'
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
                    className="user-row__menu-btn"
                    disabled={user.id === currentUser?.id}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>
                  {menuOpen === user.id && (
                    <div className="user-context-menu">
                      <button
                        onClick={() => startEditing(user)}
                        className="user-context-menu__item"
                      >
                        Edit User
                      </button>
                      {user.is_active && (
                        <button
                          onClick={() => handleDeactivateUser(user.id)}
                          className="user-context-menu__item--danger"
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

        <p className="users-total">
          {total} user{total !== 1 ? 's' : ''} total
        </p>
      </main>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="user-modal">
          <div className="user-modal__panel">
            <h2 className="user-modal__title">Create New User</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="user-modal__label">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
                  <input
                    type="email"
                    value={createForm.email}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, email: e.target.value })
                    }
                    className="user-modal__input--with-icon"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="user-modal__label">
                  Username
                </label>
                <div className="relative">
                  <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
                  <input
                    type="text"
                    value={createForm.username}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, username: e.target.value })
                    }
                    className="user-modal__input--with-icon"
                    required
                    minLength={3}
                    maxLength={32}
                  />
                </div>
              </div>
              <div>
                <label className="user-modal__label">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, password: e.target.value })
                  }
                  className="user-modal__input"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                />
              </div>
              <div>
                <label className="user-modal__label">
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
                  className="user-modal__select"
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
        <div className="user-modal">
          <div className="user-modal__panel">
            <h2 className="user-modal__title">Edit User</h2>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className="user-modal__label">
                  Email
                </label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  className="user-modal__input"
                  required
                />
              </div>
              <div>
                <label className="user-modal__label">
                  Username
                </label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(e) =>
                    setEditForm({ ...editForm, username: e.target.value })
                  }
                  className="user-modal__input"
                  required
                  minLength={3}
                  maxLength={32}
                />
              </div>
              <div>
                <label className="user-modal__label">
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
                  className="user-modal__select"
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
          className="users-menu-backdrop"
          onClick={() => setMenuOpen(null)}
        />
      )}
    </div>
  )
}
