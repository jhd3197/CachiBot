import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const STEPS = ['welcome', 'api-key', 'model', 'preferences', 'complete'] as const
export type OnboardingStep = (typeof STEPS)[number]

interface OnboardingState {
  isOpen: boolean
  currentStep: number
  hasCompletedOnboarding: boolean

  // Actions
  open: () => void
  close: () => void
  nextStep: () => void
  prevStep: () => void
  completeOnboarding: () => void
  skipOnboarding: () => void
}

export { STEPS as ONBOARDING_STEPS }

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      isOpen: false,
      currentStep: 0,
      hasCompletedOnboarding: false,

      open: () => set({ isOpen: true, currentStep: 0 }),
      close: () => set({ isOpen: false }),
      nextStep: () =>
        set((state) => ({
          currentStep: Math.min(state.currentStep + 1, STEPS.length - 1),
        })),
      prevStep: () =>
        set((state) => ({
          currentStep: Math.max(state.currentStep - 1, 0),
        })),
      completeOnboarding: () =>
        set({ isOpen: false, hasCompletedOnboarding: true, currentStep: 0 }),
      skipOnboarding: () =>
        set({ isOpen: false, hasCompletedOnboarding: true, currentStep: 0 }),
    }),
    {
      name: 'cachibot-onboarding',
      partialize: (state) => ({
        hasCompletedOnboarding: state.hasCompletedOnboarding,
      }),
    }
  )
)
