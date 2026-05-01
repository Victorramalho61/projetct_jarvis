import { LineChart, Line, ResponsiveContainer } from 'recharts'

interface SparklineProps {
  data: number[]
  color?: string
}

export default function Sparkline({ data, color = '#3b82f6' }: SparklineProps) {
  if (!data || data.length === 0) return <div style={{ width: 80, height: 32 }} />

  const chartData = data.map((v, i) => ({ i, v }))

  return (
    <div style={{ width: 80, height: 32 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
