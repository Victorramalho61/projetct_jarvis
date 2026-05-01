import type { ReactNode } from 'react'
import type { KPIComparison } from '../../types/expenses'
import Sparkline from './Sparkline'
import TrafficLight from './TrafficLight'

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

interface KPICardProps {
  title: string
  value: number
  sparkline?: number[]
  vs_mes_anterior?: KPIComparison
  vs_forecast?: KPIComparison
  vs_ly?: KPIComparison
  color?: string
  icon?: ReactNode
  subtitle?: string
}

function ComparisonRow({ label, cmp, checkmark }: { label: string; cmp: KPIComparison; checkmark?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[10px] text-gray-500 whitespace-nowrap">{label}</span>
      <div className="flex items-center gap-1">
        {checkmark && cmp.pct <= 0 && (
          <span className="text-emerald-400 text-[10px]">✓</span>
        )}
        <TrafficLight pct={cmp.pct} />
      </div>
    </div>
  )
}

export default function KPICard({
  title,
  value,
  sparkline,
  vs_mes_anterior,
  vs_forecast,
  vs_ly,
  color = '#3b82f6',
  icon,
  subtitle,
}: KPICardProps) {
  const hasComparisons = vs_mes_anterior || vs_forecast || vs_ly

  return (
    <div
      className="rounded-xl bg-gray-900 border border-gray-800 p-4 flex flex-col gap-2"
      style={{ borderTopColor: color, borderTopWidth: 2 }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {icon && <span className="text-gray-400 flex-shrink-0">{icon}</span>}
          <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 truncate">{title}</span>
        </div>
        {sparkline && sparkline.length > 0 && (
          <div className="flex-shrink-0">
            <Sparkline data={sparkline} color={color} />
          </div>
        )}
      </div>

      {/* Value */}
      <div>
        <p className="text-[22px] font-bold leading-none text-white">{FMT_BRL(value)}</p>
        {subtitle && (
          <p className="mt-1 text-[11px] text-gray-500">{subtitle}</p>
        )}
      </div>

      {/* Comparisons */}
      {hasComparisons && (
        <div className="flex flex-col gap-1 pt-1 border-t border-gray-800">
          {vs_mes_anterior && (
            <ComparisonRow label="vs. Mês Ant." cmp={vs_mes_anterior} />
          )}
          {vs_forecast && (
            <ComparisonRow label="vs. Forecast" cmp={vs_forecast} checkmark />
          )}
          {vs_ly && (
            <ComparisonRow label="vs. 2025" cmp={vs_ly} />
          )}
        </div>
      )}
    </div>
  )
}
