import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { useTheme } from '../../context/ThemeContext'

export interface FornecedorItem {
  name: string
  value: number
  pct: number
}

interface Props {
  data: FornecedorItem[]
  colors: string[]
  title?: string
}

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const FMT_COMPACT = (v: number) => {
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000)     return `R$${(v / 1_000).toFixed(0)}k`
  return `R$${v.toFixed(0)}`
}

export default function FornecedoresRadial({
  data,
  colors,
  title = 'Top 5 Fornecedores',
}: Props) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const tickColor = isDark ? '#6b7280' : '#9ca3af'

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h3>
        <p className="text-xs text-gray-400 mt-0.5">Por volume de gasto acumulado</p>
      </div>

      {data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={data.length * 44 + 16}>
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 0, right: 70, left: 4, bottom: 0 }}
              barCategoryGap="30%"
            >
              <XAxis
                type="number"
                hide
                tickFormatter={FMT_COMPACT}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={160}
                tick={{ fontSize: 11, fill: isDark ? '#d1d5db' : '#374151' }}
                axisLine={false}
                tickLine={false}
              />
              <Bar
                dataKey="value"
                radius={[0, 5, 5, 0]}
                maxBarSize={28}
                isAnimationActive
                animationDuration={900}
                label={{
                  position: 'right',
                  formatter: (v: number) => FMT_COMPACT(v),
                  fill: tickColor,
                  fontSize: 11,
                }}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={colors[i] ?? '#3b82f6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Progress bar legend below */}
          <div className="mt-4 space-y-2">
            {data.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className="h-1 rounded-full transition-all duration-700"
                  style={{
                    width: `${d.pct}%`,
                    background: colors[i] ?? '#3b82f6',
                    minWidth: 6,
                  }}
                />
                <span className="text-[10px] text-gray-400 whitespace-nowrap tabular-nums">
                  {FMT_BRL(d.value)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
