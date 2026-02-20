import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const STEPS = ['welcome', 'api-key', 'model', 'database', 'smtp', 'preferences', 'complete'] as const
export type OnboardingStep = (typeof STEPS)[number]

interface OnboardingState {
  currentStep: number
  hasCompletedOnboarding: boolean

  // Setup state (not persisted — ephemeral within a single wizard run)
  databaseType: 'sqlite' | 'postgresql'
  databaseConfigured: boolean
  smtpConfigured: boolean

  // Actions
  resetStep: () => void
  nextStep: () => void
  prevStep: () => void
  completeOnboarding: () => void
  skipOnboarding: () => void
  setDatabaseType: (type: 'sqlite' | 'postgresql') => void
  setDatabaseConfigured: (configured: boolean) => void
  setSmtpConfigured: (configured: boolean) => void
}

export { STEPS as ONBOARDING_STEPS }

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      currentStep: 0,
      hasCompletedOnboarding: false,

      databaseType: 'sqlite',
      databaseConfigured: false,
      smtpConfigured: false,

      resetStep: () => set({ currentStep: 0 }),
      nextStep: () =>
        set((state) => ({
          currentStep: Math.min(state.currentStep + 1, STEPS.length - 1),
        })),
      prevStep: () =>
        set((state) => ({
          currentStep: Math.max(state.currentStep - 1, 0),
        })),
      completeOnboarding: () =>
        set({ hasCompletedOnboarding: true, currentStep: 0 }),
      skipOnboarding: () =>
        set({ hasCompletedOnboarding: true, currentStep: 0 }),
      setDatabaseType: (type) => set({ databaseType: type }),
      setDatabaseConfigured: (configured) => set({ databaseConfigured: configured }),
      setSmtpConfigured: (configured) => set({ smtpConfigured: configured }),
    }),
    {
      name: 'cachibot-onboarding',
      partialize: (state) => ({
        hasCompletedOnboarding: state.hasCompletedOnboarding,
      }),
    }
  )
)
