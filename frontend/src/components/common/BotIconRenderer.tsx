import {
  Shield,
  Bot,
  Brain,
  Zap,
  Flame,
  Gem,
  Rocket,
  Target,
  Laptop,
  BarChart3,
  Sparkles,
  Star,
  Cpu,
  Ghost,
  Palette,
  PenTool,
  Code,
  Terminal,
  type LucideIcon,
} from 'lucide-react'
import type { BotIcon } from '../../types'

const iconMap: Record<BotIcon, LucideIcon> = {
  'shield': Shield,
  'bot': Bot,
  'brain': Brain,
  'zap': Zap,
  'flame': Flame,
  'gem': Gem,
  'rocket': Rocket,
  'target': Target,
  'laptop': Laptop,
  'bar-chart': BarChart3,
  'sparkles': Sparkles,
  'star': Star,
  'cpu': Cpu,
  'ghost': Ghost,
  'palette': Palette,
  'pen-tool': PenTool,
  'code': Code,
  'terminal': Terminal,
}

interface BotIconRendererProps {
  icon: BotIcon | string
  className?: string
  size?: number
  color?: string
}

export function BotIconRenderer({ icon, className, size = 24, color }: BotIconRendererProps) {
  const IconComponent = iconMap[icon as BotIcon] || Shield
  return <IconComponent className={className} size={size} style={color ? { color } : undefined} />
}

export function getBotIconComponent(icon: BotIcon): LucideIcon {
  return iconMap[icon] || Shield
}

export const BOT_ICON_OPTIONS: { id: BotIcon; label: string }[] = [
  { id: 'shield', label: 'Shield' },
  { id: 'bot', label: 'Bot' },
  { id: 'brain', label: 'Brain' },
  { id: 'zap', label: 'Zap' },
  { id: 'flame', label: 'Flame' },
  { id: 'gem', label: 'Gem' },
  { id: 'rocket', label: 'Rocket' },
  { id: 'target', label: 'Target' },
  { id: 'laptop', label: 'Laptop' },
  { id: 'bar-chart', label: 'Chart' },
  { id: 'sparkles', label: 'Sparkles' },
  { id: 'star', label: 'Star' },
  { id: 'cpu', label: 'CPU' },
  { id: 'ghost', label: 'Ghost' },
  { id: 'palette', label: 'Palette' },
  { id: 'pen-tool', label: 'Pen' },
  { id: 'code', label: 'Code' },
  { id: 'terminal', label: 'Terminal' },
]
