import { useCallback, useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Label,
  Legend,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../../context/AuthContext'
import { ApiError, apiFetch } from '../../lib/api'
import type {
  ExpenseDashboard,
  ExpenseRow,
  ForecastDashboard,
  ForecastFornecedor,
} from '../../types/expenses'
import KPICard from '../../components/expenses/KPICard'
import YearSelector from '../../components/expenses/YearSelector'

// ── Formatters ─────────────────────────────────────────────────────────────────

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const FMT_COMPACT = (v: number) => {
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`
  return `R$${v.toFixed(0)}`
}

const SHORT_MONTH: Record<string, string> = {
  '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr',
  '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Ago',
  '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez',
}

function shortMonth(m: string) {
  // m is like "2025-01" or "01"
  const part = m.slice(-2)
  return SHORT_MONTH[part] ?? m
}

// ── Chart colors ───────────────────────────────────────────────────────────────

const COLOR_CONTRATO = '#3b82f6'
const COLOR_EVENTUAL = '#f97316'
const COLOR_OC       = '#8b5cf6'
const COLOR_FIN      = '#6b7280'
const COLOR_LY       = '#9ca3af'
const COLOR_2025     = '#6b7280'
const COLOR_2026     = '#3b82f6'
const COLOR_PROJ     = '#93c5fd'
const COLOR_TEAL     = '#14b8a6'

const ORIGEM_COLOR: Record<string, string> = {
  'Contrato':        COLOR_CONTRATO,
  'Ordem de Compra': COLOR_OC,
  'Financeiro':      COLOR_FIN,
}

// ── Inline sub-components ──────────────────────────────────────────────────────

function OrigemBadge({ origem }: { origem: string }) {
  const styles: Record<string, string> = {
    'Contrato':        'bg-blue-500/20 text-blue-400',
    'Ordem de Compra': 'bg-violet-500/20 text-violet-400',
    'Financeiro':      'bg-gray-500/20 text-gray-400',
  }
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${styles[origem] ?? 'bg-gray-500/20 text-gray-400'}`}>
      {origem}
    </span>
  )
}

function TipoBadge({ tipo }: { tipo: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
      tipo === 'Efetivo'
        ? 'bg-emerald-500/20 text-emerald-400'
        : 'bg-amber-500/20 text-amber-400'
    }`}>
      {tipo}
    </span>
  )
}

function TendenciaBadge({ t }: { t: ForecastFornecedor['tendencia'] }) {
  const map = {
    alta:   { label: '▲ Alta',   cls: 'bg-red-500/20 text-red-400' },
    baixa:  { label: '▼ Baixa',  cls: 'bg-emerald-500/20 text-emerald-400' },
    estavel: { label: '→ Estável', cls: 'bg-gray-500/20 text-gray-400' },
  }
  const { label, cls } = map[t]
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${cls}`}>
      {label}
    </span>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="text-sm font-semibold text-gray-300 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-28 rounded-xl bg-gray-800 animate-pulse" />
      ))}
    </div>
  )
}

// Custom tooltip for ComposedChart
function MonthlyTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-3 text-xs shadow-xl">
      <p className="font-semibold text-gray-200 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-gray-200 font-medium">{FMT_BRL(p.value ?? 0)}</span>
        </div>
      ))}
    </div>
  )
}

// ── Donut center label ─────────────────────────────────────────────────────────

function DonutCenter({ cx, cy, total }: { cx: number; cy: number; total: number }) {
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fill="#e5e7eb">
      <tspan x={cx} dy="-0.4em" fontSize={11} fill="#9ca3af">Total</tspan>
      <tspan x={cx} dy="1.4em" fontSize={13} fontWeight="bold">{FMT_COMPACT(total)}</tspan>
    </text>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

type ActiveTab = 'gastos' | 'previsao'

export default function ExpensesPage() {
  const { token } = useAuth()

  // Dashboard state
  const [data, setData]       = useState<ExpenseDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  // Forecast state
  const [forecast, setForecast]           = useState<ForecastDashboard | null>(null)
  const [forecastLoading, setForecastLoading] = useState(false)
  const [forecastError, setForecastError]     = useState<string | null>(null)

  // Controls
  const [year, setYear]         = useState(2025)
  const [activeTab, setActiveTab] = useState<ActiveTab>('gastos')
  const [filial, setFilial]     = useState('')
  const [tipo, setTipo]         = useState('')

  // Table pagination
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  // ── Load dashboard ───────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    setPage(0)
    try {
      const params = new URLSearchParams({ year: String(year) })
      if (filial) params.set('filial', filial)
      if (tipo)   params.set('tipo', tipo)
      const result = await apiFetch<ExpenseDashboard>(
        `/api/expenses/dashboard?${params.toString()}`,
        { token },
      )
      setData(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao carregar dados de gastos.')
    } finally {
      setLoading(false)
    }
  }, [year, filial, tipo, token])

  useEffect(() => { load() }, [load])

  // ── Load forecast (lazy) ─────────────────────────────────────────────────────

  const loadForecast = useCallback(async () => {
    if (forecast) return
    setForecastLoading(true)
    setForecastError(null)
    try {
      const result = await apiFetch<ForecastDashboard>(
        '/api/expenses/forecast?year=2026',
        { token },
      )
      setForecast(result)
    } catch (err) {
      setForecastError(err instanceof ApiError ? err.message : 'Erro ao carregar previsão.')
    } finally {
      setForecastLoading(false)
    }
  }, [forecast, token])

  useEffect(() => {
    if (activeTab === 'previsao') loadForecast()
  }, [activeTab, loadForecast])

  // ── Derived data ─────────────────────────────────────────────────────────────

  const filteredRows: ExpenseRow[] = data?.rows ?? []

  const totalRows  = filteredRows.length
  const pageRows   = filteredRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(totalRows / PAGE_SIZE)

  // Build monthly chart data: merge by_origem_mensal with yoy
  const monthlyChartData = (data?.by_origem_mensal ?? []).map((m) => ({
    mes: shortMonth(m.mes),
    mesKey: m.mes,
    Contrato: m.contrato,
    Eventual: m.eventual,
    Total: m.contrato + m.eventual,
    LY: data?.yoy?.[m.mes] ?? null,
  }))

  const showLY = year === 2026 && Object.keys(data?.yoy ?? {}).length > 0

  // Donut total
  const origemTotal = (data?.by_origem ?? []).reduce((s, o) => s + o.valor, 0)

  // Top 15 fornecedores
  const topFornecedores = [...(data?.by_fornecedor ?? [])]
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 15)

  // Filiais sorted desc
  const filiaisData = [...(data?.by_filial ?? [])].sort((a, b) => b.valor - a.valor)

  // Forecast chart: combine 2025 + 2026 meses
  const forecastChartData = (forecast?.meses ?? []).map((m) => ({
    mes: shortMonth(m.mes),
    mesKey: m.mes,
    real:    m.tipo === 'real'     ? m.valor : null,
    projecao: m.tipo === 'projecao' ? m.valor : null,
    valor_min: m.valor_min ?? null,
    valor_max: m.valor_max ?? null,
  }))

  // YoY comparison chart (months that exist in both years)
  const yoyChartData = (data?.by_origem_mensal ?? []).map((m) => ({
    mes: shortMonth(m.mes),
    '2026': m.contrato + m.eventual,
    '2025': data?.yoy?.[m.mes] ?? null,
  })).filter((d) => d['2025'] !== null)

  // Current month key for reference line
  const currentMonth = new Date().toISOString().slice(0, 7) // "2026-05"

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 space-y-6 max-w-[1440px] mx-auto">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard Financeiro — TI</h1>
          <p className="text-sm text-gray-500 mt-1">
            VTC Operadora Logística · Despesas do departamento de TI (K_GESTOR 23)
          </p>
        </div>
        <YearSelector value={year} onChange={(y) => { setYear(y); setData(null) }} />
      </div>

      {/* ── Error banner ───────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
      {loading && !data ? (
        <SkeletonGrid />
      ) : data ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total YTD"
            value={data.kpis.total_ytd?.valor ?? data.kpis.total_valor}
            sparkline={data.kpis.total_ytd?.sparkline}
            vs_mes_anterior={data.kpis.total_ytd?.vs_mes_anterior}
            vs_forecast={data.kpis.total_ytd?.vs_forecast}
            vs_ly={data.kpis.total_ytd?.vs_ly}
            color="#3b82f6"
            subtitle={`${data.kpis.count_parcelas} parcelas`}
          />
          <KPICard
            title="Contratos"
            value={data.kpis.contratos?.valor ?? data.kpis.total_recorrente}
            sparkline={data.kpis.contratos?.sparkline}
            vs_mes_anterior={data.kpis.contratos?.vs_mes_anterior}
            vs_forecast={data.kpis.contratos?.vs_forecast}
            vs_ly={data.kpis.contratos?.vs_ly}
            color="#8b5cf6"
            subtitle="despesas recorrentes"
          />
          <KPICard
            title="Eventual"
            value={data.kpis.eventual?.valor ?? data.kpis.total_eventual}
            sparkline={data.kpis.eventual?.sparkline}
            vs_mes_anterior={data.kpis.eventual?.vs_mes_anterior}
            vs_forecast={data.kpis.eventual?.vs_forecast}
            vs_ly={data.kpis.eventual?.vs_ly}
            color="#f97316"
            subtitle="compras e pontuais"
          />
          <KPICard
            title="Média Mensal"
            value={data.kpis.media_mensal?.valor ?? data.kpis.media_mensal_valor}
            sparkline={data.kpis.media_mensal?.sparkline}
            vs_mes_anterior={data.kpis.media_mensal?.vs_mes_anterior}
            vs_forecast={data.kpis.media_mensal?.vs_forecast}
            vs_ly={data.kpis.media_mensal?.vs_ly}
            color="#14b8a6"
            subtitle="no ano selecionado"
          />
        </div>
      ) : null}

      {/* ── Sub-tabs ───────────────────────────────────────────────────────── */}
      <div className="flex gap-1 border-b border-gray-800 pb-0">
        {(['gastos', 'previsao'] as ActiveTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2.5 text-sm font-semibold rounded-t-lg transition-colors -mb-px border-b-2 ${
              activeTab === tab
                ? 'border-blue-500 text-blue-400 bg-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-900/50'
            }`}
          >
            {tab === 'gastos' ? 'Gastos' : 'Previsão'}
          </button>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB: GASTOS                                                         */}
      {/* ════════════════════════════════════════════════════════════════════ */}

      {activeTab === 'gastos' && data && (
        <div className="space-y-6">

          {/* Filters row */}
          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={filial}
              onChange={(e) => setFilial(e.target.value)}
              className="h-9 rounded-lg border border-gray-700 bg-gray-800 px-3 text-sm text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            >
              <option value="">Filial: Todas</option>
              {(data.filiais ?? []).map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>

            <div className="flex rounded-lg border border-gray-700 overflow-hidden">
              {[
                { value: '',          label: 'Todos' },
                { value: 'contrato',  label: 'Contrato' },
                { value: 'eventual',  label: 'Eventual' },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setTipo(opt.value)}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    tipo === opt.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <button
              onClick={load}
              disabled={loading}
              className="h-9 px-5 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Carregando…' : 'Aplicar'}
            </button>
          </div>

          {/* Row 1: Evolução Mensal + Distribuição */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <ChartCard title="Evolução Mensal">
              {monthlyChartData.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-12">Sem dados no período</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={monthlyChartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="mes"
                      tick={{ fontSize: 11, fill: '#9ca3af' }}
                      axisLine={{ stroke: '#4b5563' }}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={FMT_COMPACT}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      axisLine={false}
                      tickLine={false}
                      width={65}
                    />
                    <Tooltip
                      content={<MonthlyTooltip />}
                      cursor={{ fill: '#1f2937' }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11, color: '#9ca3af', paddingTop: 8 }}
                    />
                    <Bar dataKey="Contrato" stackId="a" fill={COLOR_CONTRATO} radius={[0, 0, 0, 0]} maxBarSize={40} />
                    <Bar dataKey="Eventual" stackId="a" fill={COLOR_EVENTUAL} radius={[3, 3, 0, 0]} maxBarSize={40} />
                    {showLY && (
                      <Line
                        type="monotone"
                        dataKey="LY"
                        name="2025 (LY)"
                        stroke={COLOR_LY}
                        strokeWidth={1.5}
                        strokeDasharray="4 2"
                        dot={false}
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="Distribuição por Origem">
              {data.by_origem.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={data.by_origem}
                      dataKey="valor"
                      nameKey="origem"
                      cx="50%"
                      cy="48%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={2}
                      label={({ name, percent }: { name: string; percent: number }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      labelLine={{ stroke: '#4b5563' }}
                    >
                      {data.by_origem.map((entry) => (
                        <Cell
                          key={entry.origem}
                          fill={ORIGEM_COLOR[entry.origem] ?? COLOR_FIN}
                        />
                      ))}
                      <Label
                        content={({ viewBox }) => {
                          const vb = viewBox as { cx: number; cy: number }
                          return <DonutCenter cx={vb.cx} cy={vb.cy} total={origemTotal} />
                        }}
                        position="center"
                      />
                    </Pie>
                    <Tooltip
                      formatter={(v: number) => [FMT_BRL(v), 'Total']}
                      contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                      itemStyle={{ color: '#e5e7eb' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          {/* Row 2: Top Fornecedores + Por Filial */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <ChartCard title="Top 15 Fornecedores">
              {topFornecedores.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <BarChart
                    data={topFornecedores}
                    layout="vertical"
                    margin={{ top: 0, right: 60, left: 0, bottom: 0 }}
                  >
                    <XAxis
                      type="number"
                      tickFormatter={FMT_COMPACT}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="pessoa"
                      width={150}
                      tick={{ fontSize: 10, fill: '#d1d5db' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: number) => [FMT_BRL(v), 'Total']}
                      contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                      itemStyle={{ color: '#e5e7eb' }}
                      cursor={{ fill: '#1f2937' }}
                    />
                    <Bar dataKey="valor" radius={[0, 3, 3, 0]} maxBarSize={18}>
                      {topFornecedores.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={ORIGEM_COLOR[entry.origem] ?? COLOR_FIN}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="Por Filial">
              {filiaisData.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <BarChart
                    data={filiaisData}
                    margin={{ top: 5, right: 10, left: 10, bottom: 40 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                    <XAxis
                      dataKey="filial"
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      axisLine={{ stroke: '#4b5563' }}
                      tickLine={false}
                      angle={-35}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis
                      tickFormatter={FMT_COMPACT}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      axisLine={false}
                      tickLine={false}
                      width={60}
                    />
                    <Tooltip
                      formatter={(v: number) => [FMT_BRL(v), 'Total']}
                      contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                      itemStyle={{ color: '#e5e7eb' }}
                      cursor={{ fill: '#1f2937' }}
                    />
                    <Bar dataKey="valor" fill={COLOR_TEAL} radius={[3, 3, 0, 0]} maxBarSize={48} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          {/* Row 3: Tabela de lançamentos */}
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <h2 className="text-sm font-semibold text-gray-300">
                Lançamentos
                <span className="ml-2 text-xs font-normal text-gray-500">({totalRows} registros)</span>
              </h2>
              {/* Pagination controls */}
              {totalPages > 1 && (
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 rounded border border-gray-700 hover:border-gray-500 disabled:opacity-40 transition-colors"
                  >
                    ← Ant.
                  </button>
                  <span>
                    Página {page + 1} de {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-3 py-1 rounded border border-gray-700 hover:border-gray-500 disabled:opacity-40 transition-colors"
                  >
                    Próx. →
                  </button>
                </div>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-left">
                    {['Pessoa / Fornecedor', 'Conta', 'Valor', 'Vencimento', 'Liquidação', 'Filial', 'Origem', 'Tipo'].map((h) => (
                      <th key={h} className={`pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-500 ${h === 'Valor' ? 'text-right' : ''}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {pageRows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-800/40 transition-colors">
                      <td className="py-2 pr-4 max-w-[180px] truncate text-gray-100 font-medium text-xs" title={row.PESSOA}>
                        {row.PESSOA}
                      </td>
                      <td className="py-2 pr-4 max-w-[160px] truncate text-gray-400 text-xs" title={row.CONTA ?? ''}>
                        {row.CONTA || '—'}
                      </td>
                      <td className="py-2 pr-4 text-right font-semibold text-gray-100 text-xs whitespace-nowrap">
                        {FMT_BRL(row.VALOR ?? 0)}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-400 whitespace-nowrap">
                        {row.DATAVENCIMENTO ? row.DATAVENCIMENTO.slice(0, 10) : '—'}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-400 whitespace-nowrap">
                        {row.DATALIQUIDACAO ? row.DATALIQUIDACAO.slice(0, 10) : '—'}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-400">
                        {row.FILIAL}
                      </td>
                      <td className="py-2 pr-4">
                        <OrigemBadge origem={row.ORIGEM} />
                      </td>
                      <td className="py-2">
                        <TipoBadge tipo={row.TIPO_DOC} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {totalRows === 0 && (
                <p className="py-10 text-sm text-center text-gray-500">
                  Nenhum lançamento encontrado.
                </p>
              )}
            </div>

            {/* Bottom pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4 text-xs text-gray-400">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1 rounded border border-gray-700 hover:border-gray-500 disabled:opacity-40 transition-colors"
                >
                  ← Anterior
                </button>
                <span>Página {page + 1} de {totalPages} · {PAGE_SIZE} por página</span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1 rounded border border-gray-700 hover:border-gray-500 disabled:opacity-40 transition-colors"
                >
                  Próxima →
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB: PREVISÃO                                                        */}
      {/* ════════════════════════════════════════════════════════════════════ */}

      {activeTab === 'previsao' && (
        <div className="space-y-6">

          {forecastError && (
            <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 text-sm text-red-300">
              {forecastError}
            </div>
          )}

          {forecastLoading && !forecast && (
            <SkeletonGrid />
          )}

          {forecast && (
            <>
              {/* Forecast KPIs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <KPICard
                  title="Total 2025 Real"
                  value={forecast.total_2025}
                  color="#6b7280"
                  subtitle="ano encerrado"
                />
                <KPICard
                  title="2026 Real (YTD)"
                  value={forecast.total_2026_real}
                  color="#3b82f6"
                  subtitle="meses realizados"
                />
                <KPICard
                  title="Projeção Dez/2026"
                  value={forecast.total_2026_projecao}
                  color="#93c5fd"
                  subtitle="estimativa restante"
                />
                <KPICard
                  title="Estimado Ano 2026"
                  value={forecast.total_2026_estimado}
                  color="#14b8a6"
                  subtitle="real + projeção"
                />
              </div>

              {/* Forecast AreaChart */}
              <ChartCard title="Evolução Real vs Projetada — 2026">
                {forecastChartData.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-12">Sem dados de previsão</p>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={forecastChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                      <defs>
                        <linearGradient id="gradReal" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={COLOR_2026} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={COLOR_2026} stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="gradProj" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={COLOR_PROJ} stopOpacity={0.2} />
                          <stop offset="95%" stopColor={COLOR_PROJ} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="mes" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={{ stroke: '#4b5563' }} tickLine={false} />
                      <YAxis tickFormatter={FMT_COMPACT} tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} width={65} />
                      <Tooltip
                        formatter={(v: number, name: string) => [FMT_BRL(v), name === 'real' ? 'Realizado' : 'Projetado']}
                        contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                        itemStyle={{ color: '#e5e7eb' }}
                        cursor={{ stroke: '#4b5563' }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af', paddingTop: 8 }} />
                      {/* Confidence band */}
                      <Area
                        type="monotone"
                        dataKey="valor_max"
                        stroke="none"
                        fill={COLOR_PROJ}
                        fillOpacity={0.12}
                        name="Intervalo"
                        legendType="none"
                      />
                      <Area
                        type="monotone"
                        dataKey="valor_min"
                        stroke="none"
                        fill="#111827"
                        fillOpacity={1}
                        name="Intervalo Min"
                        legendType="none"
                      />
                      <Area
                        type="monotone"
                        dataKey="real"
                        name="Realizado"
                        stroke={COLOR_2026}
                        strokeWidth={2}
                        fill="url(#gradReal)"
                        connectNulls={false}
                        dot={false}
                      />
                      <Area
                        type="monotone"
                        dataKey="projecao"
                        name="Projetado"
                        stroke={COLOR_PROJ}
                        strokeWidth={2}
                        strokeDasharray="5 3"
                        fill="url(#gradProj)"
                        connectNulls={false}
                        dot={false}
                      />
                      <ReferenceLine
                        x={shortMonth(currentMonth)}
                        stroke="#f59e0b"
                        strokeDasharray="3 3"
                        label={{ value: 'Hoje', fill: '#f59e0b', fontSize: 10, position: 'top' }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </ChartCard>

              {/* 2025 vs 2026 grouped bar — only render if showLY has data */}
              {yoyChartData.length > 0 && (
                <ChartCard title="Comparativo 2025 vs 2026 por Mês">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={yoyChartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                      <XAxis dataKey="mes" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={{ stroke: '#4b5563' }} tickLine={false} />
                      <YAxis tickFormatter={FMT_COMPACT} tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} width={65} />
                      <Tooltip
                        formatter={(v: number) => [FMT_BRL(v)]}
                        contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                        itemStyle={{ color: '#e5e7eb' }}
                        cursor={{ fill: '#1f2937' }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af', paddingTop: 8 }} />
                      <Bar dataKey="2025" fill={COLOR_2025} radius={[3, 3, 0, 0]} maxBarSize={28} />
                      <Bar dataKey="2026" fill={COLOR_2026} radius={[3, 3, 0, 0]} maxBarSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              )}

              {/* Supplier forecast table */}
              {forecast.by_fornecedor.length > 0 && (
                <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
                  <h2 className="text-sm font-semibold text-gray-300 mb-4">
                    Projeção por Fornecedor
                  </h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-800">
                          {[
                            'Fornecedor',
                            'Executado',
                            'Média/Mês',
                            'Meses Rest.',
                            'Projeção Rest.',
                            'Total Estimado',
                            'Tendência',
                          ].map((h) => (
                            <th
                              key={h}
                              className={`pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-500 ${
                                ['Executado', 'Média/Mês', 'Projeção Rest.', 'Total Estimado'].includes(h) ? 'text-right' : ''
                              }`}
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-800/60">
                        {[...forecast.by_fornecedor]
                          .sort((a, b) => b.total_estimado_ano - a.total_estimado_ano)
                          .map((f, i) => (
                            <tr key={i} className="hover:bg-gray-800/40 transition-colors">
                              <td className="py-2 pr-4 max-w-[200px] truncate text-gray-100 font-medium" title={f.pessoa}>
                                {f.pessoa}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-300 whitespace-nowrap">
                                {FMT_BRL(f.valor_executado)}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-400 whitespace-nowrap">
                                {FMT_BRL(f.media_mensal)}
                              </td>
                              <td className="py-2 pr-4 text-center text-gray-400">
                                {f.meses_restantes}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-300 whitespace-nowrap">
                                {FMT_BRL(f.valor_projetado_restante)}
                              </td>
                              <td className="py-2 pr-4 text-right font-semibold text-white whitespace-nowrap">
                                {FMT_BRL(f.total_estimado_ano)}
                              </td>
                              <td className="py-2">
                                <TendenciaBadge t={f.tendencia} />
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Methodology note */}
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 flex items-start gap-3">
                <span className="text-gray-500 text-lg mt-0.5">ℹ</span>
                <div>
                  <p className="text-xs font-semibold text-gray-400">Metodologia de Projeção</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Modelo: {forecast.modelo || 'Regressão Linear + Média Móvel 3m'} &nbsp;·&nbsp;
                    Dados de referência: Jul/2025 – hoje &nbsp;·&nbsp;
                    Intervalo de confiança 90%
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
