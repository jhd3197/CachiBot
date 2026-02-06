import { useEffect, useRef } from 'react'
import { useCreationStore } from '../../stores/creation'
import { useUIStore } from '../../stores/ui'
import { CreateBotWizard } from './CreateBotWizard'

/**
 * CreateBotDialog - Wrapper component that syncs with the UI store and renders the wizard.
 *
 * This maintains backward compatibility with existing code that uses `setCreateBotOpen(true)`
 * while leveraging the new CreateBotWizard component internally.
 */
export function CreateBotDialog() {
  const { createBotOpen, setCreateBotOpen } = useUIStore()
  const { isOpen, open, close, reset } = useCreationStore()
  const wasOpen = useRef(isOpen)

  // Sync createBotOpen from UI store to creation store
  useEffect(() => {
    if (createBotOpen && !isOpen) {
      open()
    } else if (!createBotOpen && isOpen) {
      close()
      setTimeout(reset, 200)
    }
  }, [createBotOpen, isOpen, open, close, reset])

  // Sync creation store back to UI store when wizard closes itself
  // Only trigger when isOpen transitions from true to false
  useEffect(() => {
    if (wasOpen.current && !isOpen && createBotOpen) {
      setCreateBotOpen(false)
    }
    wasOpen.current = isOpen
  }, [isOpen, createBotOpen, setCreateBotOpen])

  return <CreateBotWizard />
}
