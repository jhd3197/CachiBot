import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useBotStore, useChatStore } from '../../stores/bots'

/**
 * The voice channel now lives inside the chat itself (design view 15): the
 * composer mic switches the same chat to voice mode. This route is kept so
 * old links/bookmarks still work — it redirects to the bot's chat with
 * voice mode switched on (`?voice=1`, handled by ChatView).
 */
export function VoiceView() {
  const navigate = useNavigate()
  const { getActiveBot } = useBotStore()
  const { activeChatId } = useChatStore()
  const bot = getActiveBot()

  useEffect(() => {
    if (!bot) {
      navigate('/dashboard', { replace: true })
      return
    }
    const target = activeChatId ? `/${bot.id}/chats/${activeChatId}` : `/${bot.id}/chats`
    navigate(`${target}?voice=1`, { replace: true })
  }, [bot, activeChatId, navigate])

  return null
}
