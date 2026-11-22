import { create } from 'zustand'

/**
 * Pending tool approvals (UI v2 Workspace "Needs you").
 *
 * Entries are recorded when the WebSocket delivers an `approval_needed`
 * payload and removed when the user answers the approval dialog or the
 * agent run ends (done/error). Deliberately NOT persisted: a pending
 * approval only exists while an agent run is waiting on a connected
 * client, so the list is per-tab live state, not history.
 */

export interface PendingApproval {
  id: string
  /** Bot the approval belongs to (captured from the active bot when the payload arrived) */
  botId: string | null
  /** Chat the approval belongs to (active chat when the payload arrived) */
  chatId: string | null
  /** Tool requesting approval (e.g. python_execute) */
  tool: string
  /** Human-readable action description from the agent */
  action: string
  receivedAt: number
}

interface ApprovalsState {
  pending: PendingApproval[]
  addApproval: (approval: PendingApproval) => void
  resolveApproval: (id: string) => void
  clearForChat: (chatId: string) => void
  clearAll: () => void
}

export const useApprovalsStore = create<ApprovalsState>()((set) => ({
  pending: [],

  addApproval: (approval) =>
    set((state) => ({
      pending: state.pending.some((a) => a.id === approval.id)
        ? state.pending
        : [...state.pending, approval],
    })),

  resolveApproval: (id) =>
    set((state) => ({
      pending: state.pending.filter((a) => a.id !== id),
    })),

  clearForChat: (chatId) =>
    set((state) => ({
      pending: state.pending.filter((a) => a.chatId !== chatId),
    })),

  clearAll: () => set({ pending: [] }),
}))
