/**
 * Shared helpers for the computer views (C4), kept tiny and honest:
 * labels map the real service states; nothing invents a state or a name.
 */

import type { BotComputer } from '../../types'

/** States in which the computer is live (a container is up and Vela answers). */
export function isComputerLive(state: string | undefined): boolean {
  return state === 'awake' || state === 'needs_you'
}

/** Short label for a computer state (empty when there is nothing to say). */
export function computerStateLabel(state: string | undefined): string {
  switch (state) {
    case 'awake':
      return 'Awake'
    case 'asleep':
      return 'Asleep'
    case 'off':
      return 'Off'
    case 'building':
      return 'Building'
    case 'starting':
      return 'Starting'
    case 'needs_you':
      return 'Needs you'
    default:
      return ''
  }
}

/** Whether the given user currently holds the take-over lease. */
export function isDrivingComputer(
  computer: BotComputer | undefined,
  userId: string | undefined
): boolean {
  return !!computer?.driver && !!userId && computer.driver.userId === userId
}

/** Design 09 first-use facts. All true by construction (C1/C2 architecture):
 * one container per bot on this machine's Docker, the container can reach
 * the internet but not the host's network, /workspace is a named volume that
 * survives sleep, and the idle sleep is the shipped 10-minute default (the
 * configured value is not exposed to the UI). */
export const COMPUTER_FACTS = [
  { label: 'Runs on', value: 'This PC · Docker' },
  { label: 'Can reach', value: 'The internet, not your network' },
  { label: 'Keeps', value: '/workspace between runs' },
  { label: 'Sleeps', value: 'After 10 min idle' },
] as const
