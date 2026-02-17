/**
 * Groups Store
 *
 * Zustand store for user groups (server-side state, no localStorage persistence).
 */

import { create } from 'zustand'
import type { Group, GroupWithMembers } from '../types'
import * as groupsApi from '../api/groups'

interface GroupsState {
  groups: Group[]
  loading: boolean
  activeGroup: GroupWithMembers | null

  fetchGroups: () => Promise<void>
  createGroup: (name: string, description?: string) => Promise<Group>
  updateGroup: (groupId: string, name?: string, description?: string) => Promise<void>
  deleteGroup: (groupId: string) => Promise<void>
  fetchGroup: (groupId: string) => Promise<GroupWithMembers>
  addMember: (groupId: string, userId: string, role?: 'owner' | 'member') => Promise<void>
  removeMember: (groupId: string, userId: string) => Promise<void>
  setActiveGroup: (group: GroupWithMembers | null) => void
}

export const useGroupsStore = create<GroupsState>((set, get) => ({
  groups: [],
  loading: false,
  activeGroup: null,

  fetchGroups: async () => {
    set({ loading: true })
    try {
      const groups = await groupsApi.listGroups()
      set({ groups })
    } finally {
      set({ loading: false })
    }
  },

  createGroup: async (name, description) => {
    const group = await groupsApi.createGroup({ name, description })
    set({ groups: [group, ...get().groups] })
    return group
  },

  updateGroup: async (groupId, name, description) => {
    const updated = await groupsApi.updateGroup(groupId, { name, description })
    set({
      groups: get().groups.map((g) => (g.id === groupId ? updated : g)),
    })
  },

  deleteGroup: async (groupId) => {
    await groupsApi.deleteGroup(groupId)
    set({
      groups: get().groups.filter((g) => g.id !== groupId),
      activeGroup: get().activeGroup?.id === groupId ? null : get().activeGroup,
    })
  },

  fetchGroup: async (groupId) => {
    const group = await groupsApi.getGroup(groupId)
    set({ activeGroup: group })
    return group
  },

  addMember: async (groupId, userId, role) => {
    await groupsApi.addMember(groupId, { user_id: userId, role })
    // Refresh active group if it matches
    if (get().activeGroup?.id === groupId) {
      await get().fetchGroup(groupId)
    }
    // Update member count in groups list
    set({
      groups: get().groups.map((g) =>
        g.id === groupId ? { ...g, member_count: g.member_count + 1 } : g,
      ),
    })
  },

  removeMember: async (groupId, userId) => {
    await groupsApi.removeMember(groupId, userId)
    if (get().activeGroup?.id === groupId) {
      await get().fetchGroup(groupId)
    }
    set({
      groups: get().groups.map((g) =>
        g.id === groupId ? { ...g, member_count: Math.max(0, g.member_count - 1) } : g,
      ),
    })
  },

  setActiveGroup: (group) => set({ activeGroup: group }),
}))
