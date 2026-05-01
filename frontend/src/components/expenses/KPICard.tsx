import type { ReactNode } from 'react'

export interface ComparisonItem {
  label: string
  value?: string | null
  positive?: boolean | null
}

export interface KPICardProps {
  title: string
  value: string
  subtitle?: string
  trend?: number
  comparison?: ComparisonItem[]
  loading?: boolean
  icon?: ReactNode
  color?: string
  accentColor?: 'green' | 'blue' | 'amber' | 'red' | 'teal' | 'violet'
}

const accentMap: Record<string, string> = {
  green:  '#2d9e5f',
  blue:   '#3b82f6',
  amber:  '#f59e0b',
  red:    '#ef4444',
  teal:   '#14b8a6',
  violet: '#8b5cf6',
}

function CompRow({ item }: { item: ComparisonItem }) {
  if (item.value === undefined || item.value === null) {
    return (
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">{item.label}</span>
        <span className="text-[10px] text-gray-400 dark:text-gray-600">
          — <span className="kpi-na-badge">em breve</span>
        </span>
      </div>
    )
  }
  const color =
    item.positive === true  ? '#4ade80' :
    item.positive === false ? '#f87171' :
                               '#94a3b8'
  const arrow = item.positive === true ? '↑ ' : item.positive === false ? '↓ ' : ''
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">{item.label}</span>
      <span className="text-[10px] font-semibold tabular-nums" style={{ color }}>
        {arrow}{item.value}
      </span>
    </div>
  )
}

export default function KPICard({
  title,
  value,
  subtitle,
  trend,
  comparison = [],
  loading = false,
  icon,
  color,
  accentColor = 'blue',
}: KPICardProps) {
  const accent = color ?? accentMap[accentColor] ?? accentMap.blue

  return (
    <div
      className="rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4 flex flex-col gap-2"
      style={{ borderTopColor: accent, borderTopWidth: 2 }}
    >
      {/* Title row */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 truncate">
          {title}
        </span>
        {icon && <span className="text-gray-400 flex-shrink-0">{icon}</span>}
      </div>

      {/* Skeleton */}
      {loading ? (
        <div className="flex flex-col gap-2 pt-1">
          <div className="shimmer h-6 w-3/4 rounded" />
          <div className="shimmer h-2.5 w-1/2 rounded" />
          <div className="shimmer h-2 w-4/5 rounded mt-1" />
        </div>
      ) : (
        <>
          {/* Value */}
          <div>
            <p
              className="text-[22px] font-bold leading-none tabular-nums"
              style={{ color: accent }}
            >
              {value}
            </p>
            {subtitle && (
              <p className="mt-1 text-[11px] text-gray-500">{subtitle}</p>
            )}
          </div>

          {/* Trend */}
          {trend !== undefined && (
            <p
              className="text-[11px] font-semibold"
              style={{ color: trend > 0 ? '#f87171' : '#4ade80' }}
            >
              {trend > 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}% vs mês ant.
            </p>
          )}

          {/* Comparisons */}
          {comparison.length > 0 && (
            <div className="flex flex-col gap-1 pt-1 border-t border-gray-100 dark:border-gray-800">
              {comparison.map((item, i) => <CompRow key={i} item={item} />)}
            </div>
          )}

          {comparison.length === 0 && (
            <p className="text-[10px] text-gray-400 dark:text-gray-600 italic">
              Comparativos pendentes
            </p>
          )}
        </>
      )}
    </div>
  )
}
