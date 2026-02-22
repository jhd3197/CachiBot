const ACCENT = 'var(--accent-500)'
const MUTED = 'currentColor'

function Circle({ cx, cy, r = 4, fill = ACCENT }: { cx: number; cy: number; r?: number; fill?: string }) {
  return <circle cx={cx} cy={cy} r={r} fill={fill} />
}

function Arrow({ x1, y1, x2, y2, color = MUTED }: { x1: number; y1: number; x2: number; y2: number; color?: string }) {
  return (
    <line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={color} strokeWidth={1.5}
      markerEnd="url(#arrow)"
    />
  )
}

function ArrowDef({ color = MUTED }: { color?: string }) {
  return (
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth={5} markerHeight={5} orient="auto-start-auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
      </marker>
    </defs>
  )
}

function SvgWrap({ children }: { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 80 40" fill="none" className="room-wizard__mode-svg">
      {children}
    </svg>
  )
}

/** All bots fire simultaneously from a single input */
export function ParallelIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* User node */}
      <Circle cx={10} cy={20} r={5} fill={ACCENT} />
      {/* Three parallel arrows fanning out */}
      <Arrow x1={16} y1={20} x2={50} y2={8} />
      <Arrow x1={16} y1={20} x2={50} y2={20} />
      <Arrow x1={16} y1={20} x2={50} y2={32} />
      {/* Bot nodes */}
      <Circle cx={56} cy={8} r={4} fill={MUTED} />
      <Circle cx={56} cy={20} r={4} fill={MUTED} />
      <Circle cx={56} cy={32} r={4} fill={MUTED} />
    </SvgWrap>
  )
}

/** Bots respond one after another in turn order */
export function SequentialIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      <Circle cx={8} cy={20} r={4} fill={MUTED} />
      <Arrow x1={13} y1={20} x2={26} y2={20} />
      <Circle cx={31} cy={20} r={4} fill={MUTED} />
      <Arrow x1={36} y1={20} x2={49} y2={20} />
      <Circle cx={54} cy={20} r={4} fill={MUTED} />
      <Arrow x1={59} y1={20} x2={72} y2={20} />
      <Circle cx={76} cy={20} r={4} fill={ACCENT} />
    </SvgWrap>
  )
}

/** Output of one bot feeds into the next */
export function ChainIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      <Circle cx={8} cy={20} r={4} fill={ACCENT} />
      <Arrow x1={13} y1={20} x2={24} y2={20} color={ACCENT} />
      <Circle cx={29} cy={20} r={4} fill={MUTED} />
      <Arrow x1={34} y1={20} x2={45} y2={20} color={ACCENT} />
      <Circle cx={50} cy={20} r={4} fill={MUTED} />
      <Arrow x1={55} y1={20} x2={66} y2={20} color={ACCENT} />
      <Circle cx={71} cy={20} r={4} fill={MUTED} />
      {/* Connecting data labels */}
      <rect x={18} y={10} width={16} height={5} rx={1.5} fill={ACCENT} opacity={0.25} />
      <rect x={39} y={10} width={16} height={5} rx={1.5} fill={ACCENT} opacity={0.25} />
      <rect x={60} y={10} width={16} height={5} rx={1.5} fill={ACCENT} opacity={0.25} />
    </SvgWrap>
  )
}

/** AI router selects which bot handles each message */
export function RouterIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* Input */}
      <Circle cx={10} cy={20} r={5} fill={ACCENT} />
      {/* Router diamond */}
      <polygon points="32,12 40,20 32,28 24,20" fill={ACCENT} opacity={0.3} stroke={ACCENT} strokeWidth={1} />
      <Arrow x1={16} y1={20} x2={23} y2={20} color={ACCENT} />
      {/* Fan-out to bots */}
      <Arrow x1={41} y1={17} x2={58} y2={8} />
      <Arrow x1={41} y1={20} x2={58} y2={20} color={ACCENT} />
      <Arrow x1={41} y1={23} x2={58} y2={32} />
      {/* Bot nodes — only the selected one is accent */}
      <Circle cx={63} cy={8} r={4} fill={MUTED} />
      <Circle cx={63} cy={20} r={4} fill={ACCENT} />
      <Circle cx={63} cy={32} r={4} fill={MUTED} />
    </SvgWrap>
  )
}

/** Bots argue structured positions back and forth */
export function DebateIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* Two debaters */}
      <Circle cx={16} cy={20} r={5} fill={MUTED} />
      <Circle cx={64} cy={20} r={5} fill={MUTED} />
      {/* Arrows going back and forth */}
      <Arrow x1={22} y1={16} x2={58} y2={16} color={ACCENT} />
      <Arrow x1={58} y1={24} x2={22} y2={24} color={ACCENT} />
      {/* Round labels */}
      <text x={40} y={13} textAnchor="middle" fontSize={6} fill={ACCENT} fontWeight={600}>1</text>
      <text x={40} y={30} textAnchor="middle" fontSize={6} fill={ACCENT} fontWeight={600}>2</text>
    </SvgWrap>
  )
}

/** Bots process in sequence, stopping when resolved */
export function WaterfallIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* Descending steps */}
      <Circle cx={10} cy={8} r={4} fill={MUTED} />
      <line x1={14} y1={10} x2={26} y2={18} stroke={ACCENT} strokeWidth={1.5} strokeDasharray="3 2" />
      <Circle cx={30} cy={20} r={4} fill={MUTED} />
      <line x1={34} y1={22} x2={46} y2={30} stroke={ACCENT} strokeWidth={1.5} strokeDasharray="3 2" />
      <Circle cx={50} cy={32} r={4} fill={ACCENT} />
      {/* Stop marker */}
      <rect x={58} y={28} width={12} height={8} rx={2} fill={ACCENT} opacity={0.25} />
      <text x={64} y={34} textAnchor="middle" fontSize={5} fill={ACCENT} fontWeight={600}>OK</text>
    </SvgWrap>
  )
}

/** Auto round-robin: each message goes to the next bot in rotation */
export function RelayIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* User node */}
      <Circle cx={10} cy={20} r={5} fill={ACCENT} />
      {/* Arrow to a single bot (highlighted) */}
      <Arrow x1={16} y1={20} x2={38} y2={20} color={ACCENT} />
      <Circle cx={44} cy={20} r={5} fill={ACCENT} />
      {/* Circular rotation indicator around 3 bot slots */}
      <Circle cx={60} cy={10} r={3} fill={MUTED} />
      <Circle cx={70} cy={20} r={3} fill={MUTED} />
      <Circle cx={60} cy={30} r={3} fill={MUTED} />
      {/* Rotation arc */}
      <path d="M 63 10 Q 72 10, 70 17" stroke={ACCENT} strokeWidth={1} fill="none" />
      <path d="M 70 23 Q 72 30, 63 30" stroke={ACCENT} strokeWidth={1} fill="none" />
      <path d="M 57 30 Q 52 25, 57 10" stroke={ACCENT} strokeWidth={1} fill="none" />
    </SvgWrap>
  )
}

/** All bots respond hidden, then a synthesizer bot merges responses */
export function ConsensusIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* User node */}
      <Circle cx={8} cy={20} r={4} fill={ACCENT} />
      {/* Fan out to hidden bots */}
      <Arrow x1={13} y1={20} x2={26} y2={8} />
      <Arrow x1={13} y1={20} x2={26} y2={20} />
      <Arrow x1={13} y1={20} x2={26} y2={32} />
      {/* Hidden bot nodes (dashed outlines) */}
      <circle cx={31} cy={8} r={4} fill="none" stroke={MUTED} strokeWidth={1} strokeDasharray="2 1.5" />
      <circle cx={31} cy={20} r={4} fill="none" stroke={MUTED} strokeWidth={1} strokeDasharray="2 1.5" />
      <circle cx={31} cy={32} r={4} fill="none" stroke={MUTED} strokeWidth={1} strokeDasharray="2 1.5" />
      {/* Converge to synthesizer */}
      <Arrow x1={36} y1={8} x2={54} y2={20} color={ACCENT} />
      <Arrow x1={36} y1={20} x2={54} y2={20} color={ACCENT} />
      <Arrow x1={36} y1={32} x2={54} y2={20} color={ACCENT} />
      {/* Synthesizer node (larger, accent) */}
      <Circle cx={60} cy={20} r={5} fill={ACCENT} />
      {/* Result arrow */}
      <Arrow x1={66} y1={20} x2={76} y2={20} color={ACCENT} />
    </SvgWrap>
  )
}

/** One bot interviews the user, then hands off to specialists */
export function InterviewIllustration() {
  return (
    <SvgWrap>
      <ArrowDef />
      {/* User */}
      <Circle cx={8} cy={20} r={4} fill={ACCENT} />
      {/* Interviewer bot */}
      <Circle cx={26} cy={20} r={5} fill={MUTED} />
      {/* Back-and-forth arrows (interview) */}
      <Arrow x1={13} y1={17} x2={20} y2={17} color={ACCENT} />
      <Arrow x1={20} y1={23} x2={13} y2={23} color={ACCENT} />
      {/* Question marks */}
      <text x={26} y={13} textAnchor="middle" fontSize={6} fill={ACCENT} fontWeight={600}>?</text>
      {/* Handoff arrow */}
      <line x1={32} y1={20} x2={46} y2={20} stroke={ACCENT} strokeWidth={1.5} strokeDasharray="3 2" />
      {/* Specialist bots fan out */}
      <Arrow x1={48} y1={20} x2={60} y2={10} color={ACCENT} />
      <Arrow x1={48} y1={20} x2={60} y2={20} color={ACCENT} />
      <Arrow x1={48} y1={20} x2={60} y2={30} color={ACCENT} />
      <Circle cx={65} cy={10} r={4} fill={MUTED} />
      <Circle cx={65} cy={20} r={4} fill={MUTED} />
      <Circle cx={65} cy={30} r={4} fill={MUTED} />
    </SvgWrap>
  )
}
