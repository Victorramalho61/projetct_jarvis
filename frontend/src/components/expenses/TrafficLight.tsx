interface TrafficLightProps {
  pct: number
  label?: string
}

export default function TrafficLight({ pct, label }: TrafficLightProps) {
  const abs = Math.abs(pct)

  let bgClass: string
  let textClass: string
  if (abs <= 5) {
    bgClass = 'bg-emerald-500/20'
    textClass = 'text-emerald-400'
  } else if (abs <= 15) {
    bgClass = 'bg-amber-500/20'
    textClass = 'text-amber-400'
  } else {
    bgClass = pct > 0 ? 'bg-red-500/20' : 'bg-emerald-500/20'
    textClass = pct > 0 ? 'text-red-400' : 'text-emerald-400'
  }

  const arrow = pct > 0 ? '▲' : pct < 0 ? '▼' : '→'
  const formatted = `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${bgClass} ${textClass}`}>
      <span>{arrow}</span>
      <span>{formatted}</span>
      {label && <span className="opacity-70">{label}</span>}
    </span>
  )
}
