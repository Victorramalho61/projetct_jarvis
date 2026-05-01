import { useState } from 'react'
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Sector,
  Tooltip,
} from 'recharts'

export interface OrigemItem {
  name: string
  value: number
  pct: number
}

interface Props {
  data: OrigemItem[]
  colors: string[]
  title?: string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderActiveShape(props: any) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props
  return (
    <g>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius - 3}
        outerRadius={outerRadius + 7}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.95}
      />
    </g>
  )
}

function FMT_BRL(v: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
}

export default function DonutOrigem({ data, colors, title = 'Distribuição por Origem' }: Props) {
  const [active, setActive] = useState<number | null>(null)
  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <div className="flex items-start justify-between gap-2 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h3>
          <p className="text-xs text-gray-400 mt-0.5">por categoria de documento</p>
        </div>
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 tabular-nums whitespace-nowrap">
          {FMT_BRL(total)}
        </span>
      </div>

      {data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
      ) : (
        <div className="donut-wrapper">
          {/* Chart */}
          <div style={{ flexShrink: 0, width: 170, height: 170 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="50%" cy="50%"
                  innerRadius={48} outerRadius={76}
                  dataKey="value"
                  activeIndex={active ?? undefined}
                  activeShape={renderActiveShape}
                  onMouseEnter={(_, i) => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                  isAnimationActive
                  animationBegin={100}
                  animationDuration={800}
                  strokeWidth={0}
                >
                  {data.map((_, i) => (
                    <Cell key={i} fill={colors[i] ?? '#6b7280'} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active: a, payload }) => {
                    if (!a || !payload?.length) return null
                    const d = payload[0]
                    const idx = data.findIndex((o) => o.name === d.name)
                    return (
                      <div className="chart-tooltip">
                        <div className="chart-tooltip__label">{d.name}</div>
                        <div className="chart-tooltip__row">
                          <span
                            className="chart-tooltip__dot"
                            style={{ background: colors[idx] ?? '#6b7280' }}
                          />
                          <span className="chart-tooltip__value">
                            {FMT_BRL(d.value as number)}
                          </span>
                        </div>
                        <div className="chart-tooltip__sub">
                          {d.payload.pct}% do total
                        </div>
                      </div>
                    )
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Lateral legend — replaces overlapping external labels */}
          <div className="donut-legend">
            {data.map((d, i) => (
              <div
                key={i}
                className="donut-legend__item"
                style={{ opacity: active === null || active === i ? 1 : 0.35 }}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
              >
                <span
                  className="donut-legend__swatch"
                  style={{ background: colors[i] ?? '#6b7280' }}
                />
                <span className="donut-legend__name" title={d.name}>{d.name}</span>
                <span className="donut-legend__pct">{d.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
