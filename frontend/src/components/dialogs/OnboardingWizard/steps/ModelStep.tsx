import { useEffect } from 'react'
import { useModelsStore } from '../../../../stores/models'
import { ModelSelect } from '../../../common/ModelSelect'

export function ModelStep() {
  const { defaultModel, updateDefaultModel, refresh } = useModelsStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleChange = async (model: string) => {
    if (model) {
      await updateDefaultModel(model)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Choose a Default Model</h3>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          This model will be used for new bots unless you specify a different one.
        </p>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">Default Model</label>
        <ModelSelect
          value={defaultModel}
          onChange={handleChange}
          placeholder="Select a model..."
          className="w-full"
        />
      </div>

      {defaultModel && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
          <p className="text-sm text-green-400">
            Selected: <span className="font-mono text-xs">{defaultModel}</span>
          </p>
        </div>
      )}

      <p className="text-xs text-zinc-500">
        You can change this anytime in Settings &gt; Models.
      </p>
    </div>
  )
}
