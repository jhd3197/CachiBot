import { cn } from '../../lib/utils'

interface BotAvatarProps {
  /** Bot accent color (deterministic per bot) */
  color?: string
  /** Custom avatar image URL — rendered when present */
  src?: string | null
  /** Accessible label (bot name) */
  name: string
  size?: number
  className?: string
}

/**
 * UI v2 bot avatar (docs/design/cachibot-v2-final-views): a colored circle
 * with two dark eye dots. If the bot has a custom avatar image, that image
 * is shown instead. No initials, no emoji.
 */
export function BotAvatar({ color = '#4ade80', src, name, size = 40, className }: BotAvatarProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={name}
        width={size}
        height={size}
        className={cn('v2-avatar v2-avatar--img', className)}
        style={{ width: size, height: size }}
      />
    )
  }

  // Eye geometry scales from the design's 40px avatar (5x6px eyes, 6px gap)
  const eyeW = Math.round(size * 0.125)
  const eyeH = Math.round(size * 0.15)
  const eyeGap = Math.round(size * 0.15)

  return (
    <span
      role="img"
      aria-label={name}
      className={cn('v2-avatar', className)}
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        gap: eyeGap,
      }}
    >
      <span className="v2-avatar__eye" style={{ width: eyeW, height: eyeH }} />
      <span className="v2-avatar__eye" style={{ width: eyeW, height: eyeH }} />
    </span>
  )
}
