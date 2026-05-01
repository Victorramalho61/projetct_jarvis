import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTheme } from '../../context/ThemeContext'

const FMT_COMPACT = (v: number) => {
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000)     return `R$${(v / 1_000).toFixed(0)}k`
  return `R$${v.toFixed(0)}`
}

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

export interface ForecastDataPoint {
  mes: string
  real: number | null
  proj: number | null
  min: number | null
  max: number | null
}

interface Props {
  data: ForecastDataPoint[]
  todayLabel?: string
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ dataKey: string; name: string; value: number; stroke?: string; fill?: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  const rows = payload.filter(
    (p) => p.dataKey !== 'max' && p.dataKey !== 'min' && p.value != null,
  )
  if (!rows.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {rows.map((p, i) => (
        <div key={i} className="chart-tooltip__row">
          <span
            className="chart-tooltip__dot"
            style={{ background: p.stroke ?? p.fill ?? '#3b82f6' }}
          />
          <span className="chart-tooltip__name">{p.name}</span>
          <span className="chart-tooltip__value">{FMT_BRL(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

export default function ForecastChart({ data, todayLabel }: Props) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const gridColor  = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)'
  const tickColor  = isDark ? '#64748b' : '#6b7280'
  const axisColor  = isDark ? '#374151' : '#e5e7eb'

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Evolução Real vs Projetada — 2026
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Linha sólida = realizado · tracejada = projetado · faixa = intervalo de confiança
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <span className="w-5 h-0.5 bg-blue-500 rounded inline-block" />
            Realizado
          </span>
          <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <span className="w-5 h-px border-t-2 border-dashed border-blue-300 inline-block" />
            Projetado
          </span>
          <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <span className="w-4 h-3 bg-blue-500/15 rounded inline-block" />
            Intervalo
          </span>
        </div>
      </div>

      {data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-12">Sem dados de previsão</p>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="fcBand" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.03} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis
              dataKey="mes"
              tick={{ fill: tickColor, fontSize: 11 }}
              axisLine={{ stroke: axisColor }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={FMT_COMPACT}
              tick={{ fill: tickColor, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Confidence band: max fills with gradient */}
            <Area
              dataKey="max"
              stroke="none"
              fill="url(#fcBand)"
              legendType="none"
              isAnimationActive
              animationDuration={700}
              name="max"
            />
            {/* Confidence band: min masks with --bg-base CSS variable */}
            <Area
              dataKey="min"
              stroke="none"
              fill="var(--bg-base, #111827)"
              fillOpacity={1}
              legendType="none"
              isAnimationActive
              animationDuration={700}
              name="min"
            />

            {/* Projected — dashed */}
            <Line
              dataKey="proj"
              name="Projetado"
              stroke="#60a5fa"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              activeDot={{ r: 5, fill: '#60a5fa', strokeWidth: 2 }}
              isAnimationActive
              animationDuration={900}
              connectNulls
            />

            {/* Realized — solid */}
            <Line
              dataKey="real"
              name="Realizado"
              stroke="#3b82f6"
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: '#3b82f6', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}
              isAnimationActive
              animationDuration={1000}
            />

            {todayLabel && (
              <ReferenceLine
                x={todayLabel}
                stroke={isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'}
                strokeDasharray="4 4"
                label={{
                  value: 'hoje',
                  position: 'insideTopRight',
                  fill: '#475569',
                  fontSize: 10,
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
