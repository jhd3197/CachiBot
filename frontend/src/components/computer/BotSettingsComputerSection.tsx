/**
 * BotSettingsComputerSection — Bot settings › Computer (design view 18's
 * hidden section, now backed by C1/C2). Status, the true first-use facts
 * and the wake/sleep/stop controls (operator+; viewers see read-only rows).
 * The parent renders this section only while the Docker probe is available.
 */

import { useEffect, useState } from 'react'
import { useComputerStore } from '../../stores/computer'
import { useBotAccess } from '../../hooks/useBotAccess'
import type { Bot } from '../../types'
import { computerStateLabel, COMPUTER_FACTS } from './utils'

export function BotSettingsComputerSection({ bot }: { bot: Bot }) {
  const { canOperate } = useBotAccess(bot.id)
  const computer = useComputerStore((s) => s.byBot[bot.id])
  const [pending, setPending] = useState<string | null>(null)

  useEffect(() => {
    void useComputerStore.getState().ensureForBot(bot.id)
  }, [bot.id])

  const state = computer?.state
  const live = state === 'awake' || state === 'needs_you'

  const run = (key: string, action: () => Promise<unknown>) => {
    setPending(key)
    action()
      .catch(() => undefined)
      .finally(() => setPending(null))
  }

  const statusSub = [
    state === 'awake' && computer?.activity?.text ? computer.activity.text : null,
    computer?.lastError ?? null,
    computer?.velaVersion ? `Vela ${computer.velaVersion}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="computer-settings">
      <div className="computer-settings__statusrow">
        <span className="computer-settings__state" data-state={state ?? 'off'}>
          {computerStateLabel(state) || 'Off'}
        </span>
        {statusSub && <span className="computer-settings__sub">{statusSub}</span>}
      </div>

      <dl className="computer-facts">
        {COMPUTER_FACTS.map((fact) => (
          <div key={fact.label} className="computer-facts__row">
            <dt className="computer-facts__label">{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>

      {canOperate && (
        <div className="computer-settings__actions">
          {(state === 'off' || state === 'asleep' || state === undefined) && (
            <button
              type="button"
              className="computer-card__btn computer-card__btn--primary"
              disabled={pending !== null}
              onClick={() => run('wake', () => useComputerStore.getState().wake(bot.id))}
            >
              {pending === 'wake' ? 'Waking…' : state === 'asleep' ? 'Wake' : 'Turn on'}
            </button>
          )}
          {live && (
            <button
              type="button"
              className="computer-card__btn"
              disabled={pending !== null}
              onClick={() => run('sleep', () => useComputerStore.getState().sleep(bot.id))}
            >
              {pending === 'sleep' ? 'Sleeping…' : 'Sleep'}
            </button>
          )}
          {live && (
            <button
              type="button"
              className="computer-card__btn"
              disabled={pending !== null}
              onClick={() => run('stop', () => useComputerStore.getState().stop(bot.id))}
            >
              {pending === 'stop' ? 'Stopping…' : 'Stop'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
