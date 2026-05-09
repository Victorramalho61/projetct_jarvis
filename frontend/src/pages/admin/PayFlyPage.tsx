import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { apiFetch } from '../../lib/api'

// ── Formatters ─────────────────────────────────────────────────────────────────

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const FMT_COMPACT = (v: number) => {
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`
  return `R$${v.toFixed(0)}`
}

const FMT_DATE = (s: string | null | undefined) => {
  if (!s) return '—'
  try { return new Intl.DateTimeFormat('pt-BR').format(new Date(s + 'T00:00:00')) }
  catch { return s }
}

const FMT_DATETIME = (s: string | null | undefined) => {
  if (!s) return '—'
  try { return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(s)) }
  catch { return s }
}

// ── Types ──────────────────────────────────────────────────────────────────────

type PayFlyTab = 'investimentos' | 'monitoramento' | 'governanca' | 'midia' | 'chamados'

interface PayFlySupplier {
  fornecedor: string
  cod_fornecedor: string
  categoria: string
  tipo: 'Contrato' | 'Eventual'
  total: number
  qtd: number
  primeira_data: string | null
  ultima_data: string | null
  is_pj_collaborator: boolean
}

interface PayFlySeries {
  competencia: string
  total: number
  qtd: number
}

interface InvestmentsResponse {
  fornecedores: PayFlySupplier[]
  serie_mensal: PayFlySeries[]
  totais: { total: number; qtd_fornecedores: number }
  por_categoria: { categoria: string; total: number }[]
  por_tipo: { tipo: string; total: number; pct: number }[]
}

interface Comprometimento {
  fornecedor: string
  categoria: string
  total_pendente: number
  qtd: number
  proxima_vencimento: string | null
  ultima_vencimento: string | null
  parcelas: { datavencimento: string | null; valor: number; historico: string }[]
}

interface PayFlyDetail {
  ap: number | null
  fornecedor: string
  categoria: string
  historico: string
  datavencimento: string | null
  dataliquidacao: string | null
  valor: number
  status_par: string
  filial: string
  empresa: string
}

interface MediaPost {
  id: string
  platform: string
  title: string
  url: string
  snippet: string | null
  source: string | null
  published_at: string | null
  sentiment: 'positivo' | 'negativo' | 'neutro'
  sentiment_score: number | null
}

interface MediaMetrics {
  ref_month: string
  platform: string
  posts_count: number
  positive_count: number
  negative_count: number
  neutral_count: number
}

interface FreshDashboard {
  group_id: number | null
  group_name: string | null
  total: number
  abertos: number
  pendentes: number
  resolvidos: number
  fechados: number
  aguardando_fornecedor: number
  pct_abertos: number
  pct_fechados: number
  pct_aguardando: number
  sla_compliance_pct: number
  avg_resolution_time_hours: number | null
  by_priority: Record<string, number>
  trend_total: number
  trend_fechados: number
  error?: string
}

interface FreshTicket {
  id: number
  subject: string
  status: number
  priority: number
  created_at: string
  updated_at: string
  resolved_at: string | null
  closed_at: string | null
  due_by: string | null
  sla_breached: boolean | null
  resolution_time_min: number | null
  agent_name: string | null
  group_name: string | null
}

// ── Constants ──────────────────────────────────────────────────────────────────

const TABS: { id: PayFlyTab; label: string }[] = [
  { id: 'investimentos', label: 'Investimentos' },
  { id: 'monitoramento', label: 'Monitoramento' },
  { id: 'governanca',    label: 'Governança & Auditoria' },
  { id: 'midia',         label: 'Mídia & Redes Sociais' },
  { id: 'chamados',      label: 'Chamados' },
]

const FS_STATUS: Record<number, { label: string; cls: string }> = {
  2: { label: 'Aberto',              cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  3: { label: 'Pendente',            cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  4: { label: 'Resolvido',           cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  5: { label: 'Fechado',             cls: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
  6: { label: 'Aguard. Fornecedor',  cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
}

const FS_PRIORITY: Record<number, { label: string; cls: string }> = {
  1: { label: 'Baixa',   cls: 'text-gray-500' },
  2: { label: 'Média',   cls: 'text-blue-600 dark:text-blue-400' },
  3: { label: 'Alta',    cls: 'text-amber-600 dark:text-amber-400' },
  4: { label: 'Urgente', cls: 'text-red-600 dark:text-red-400 font-semibold' },
}

const SENTIMENT_BADGE: Record<string, string> = {
  positivo: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  negativo: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  neutro:   'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}

const CATEGORIA_BADGE: Record<string, string> = {
  'PayFly':        'bg-brand-soft text-brand-deep dark:bg-brand-green/10 dark:text-brand-mid',
  'Desenvolvimento': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  'Infraestrutura':  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
}

const TIPO_BADGE: Record<string, string> = {
  'Contrato': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  'Eventual': 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}

const TIPO_COLORS: Record<string, string> = {
  'Contrato': '#6366f1',
  'Eventual': '#e5e7eb',
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent }: {
  label: string; value: string; sub?: string; accent?: boolean
}) {
  return (
    <div className={`rounded-xl border ${accent ? 'border-brand-green/30 bg-brand-soft dark:bg-brand-green/10' : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900'} p-5`}>
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ? 'text-brand-deep dark:text-brand-mid' : 'text-gray-900 dark:text-gray-100'}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
    </div>
  )
}

function TrendArrow({ value }: { value: number }) {
  if (value === 0) return <span className="text-gray-400 text-xs">→</span>
  if (value > 0) return <span className="text-red-500 text-xs">↑ {value}</span>
  return <span className="text-green-500 text-xs">↓ {Math.abs(value)}</span>
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
      <div className="h-14 w-14 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
        <svg className="h-7 w-7 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p className="text-base font-semibold text-gray-700 dark:text-gray-300">{title}</p>
      <p className="text-sm text-gray-400">Em construção — em breve disponível.</p>
    </div>
  )
}

// ── Investimentos Tab ──────────────────────────────────────────────────────────

function InvestimentosTab({ token }: { token: string }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [year, setYear] = useState<string>('')
  const [data, setData] = useState<InvestmentsResponse | null>(null)
  const [detail, setDetail] = useState<PayFlyDetail[] | null>(null)
  const [comprometimentos, setComprometimentos] = useState<Comprometimento[]>([])
  const [expandedComp, setExpandedComp] = useState<string | null>(null)
  const [selectedSupplier, setSelectedSupplier] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const q = year ? `?year=${year}` : ''
      const [res, comp] = await Promise.all([
        apiFetch<InvestmentsResponse>(`/api/expenses/payfly/investments${q}`, { token }),
        apiFetch<Comprometimento[]>('/api/expenses/payfly/investments/comprometimentos', { token }),
      ])
      setData(res)
      setComprometimentos(comp)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar dados')
    } finally { setLoading(false) }
  }, [year, token])

  const loadDetail = useCallback(async () => {
    try {
      const q = year ? `?year=${year}` : ''
      const res = await apiFetch<PayFlyDetail[]>(`/api/expenses/payfly/investments/detail${q}`, { token })
      setDetail(res)
    } catch {
      setDetail([])
    }
  }, [year, token])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (selectedSupplier) loadDetail() }, [selectedSupplier, loadDetail])

  const detailForSupplier = detail?.filter(d => d.fornecedor === selectedSupplier) ?? []

  const chartData = (data?.serie_mensal ?? []).map(s => ({
    name: s.competencia,
    Total: s.total,
  }))

  const YEARS = ['2025', '2026', '']

  return (
    <div className="space-y-6">
      {/* Filtro de ano */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-600 dark:text-gray-400">Ano:</label>
        <div className="flex gap-1.5">
          {YEARS.map(y => (
            <button
              key={y || 'todos'}
              onClick={() => setYear(y)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                year === y
                  ? 'bg-brand-green text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {y || 'Todos'}
            </button>
          ))}
        </div>
        <button
          onClick={load}
          className="ml-auto text-sm text-brand-green hover:underline"
        >Atualizar</button>
      </div>

      {loading && (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl bg-gray-200 dark:bg-gray-800" />)}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-2 gap-4">
            <KpiCard label="Total Investido" value={FMT_BRL(data.totais.total)} accent />
            <KpiCard label="Fornecedores" value={String(data.totais.qtd_fornecedores)} sub="com gastos PayFly" />
          </div>

          {/* Breakdown por categoria */}
          {data.por_categoria.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {data.por_categoria.map(c => (
                <div
                  key={c.categoria}
                  className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 flex items-center justify-between gap-3"
                >
                  <div>
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${CATEGORIA_BADGE[c.categoria] ?? 'bg-gray-100 text-gray-600'}`}>
                      {c.categoria}
                    </span>
                  </div>
                  <p className="text-base font-bold text-gray-800 dark:text-gray-100 tabular-nums">
                    {FMT_BRL(c.total)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Donut: Contrato vs Eventual */}
          {data.por_tipo.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Tipo de Gasto</h3>
                <div className="flex items-center gap-6">
                  <ResponsiveContainer width={120} height={120}>
                    <PieChart>
                      <Pie data={data.por_tipo} dataKey="total" cx="50%" cy="50%" innerRadius={32} outerRadius={52} paddingAngle={2}>
                        {data.por_tipo.map(entry => (
                          <Cell key={entry.tipo} fill={TIPO_COLORS[entry.tipo] ?? '#9ca3af'} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => FMT_BRL(v)} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2">
                    {data.por_tipo.map(t => (
                      <div key={t.tipo} className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full shrink-0" style={{ background: TIPO_COLORS[t.tipo] ?? '#9ca3af' }} />
                        <span className="text-xs text-gray-600 dark:text-gray-400">{t.tipo}</span>
                        <span className="text-xs font-semibold text-gray-800 dark:text-gray-100 tabular-nums ml-auto">{t.pct}%</span>
                      </div>
                    ))}
                    {data.por_tipo.map(t => (
                      <div key={`v-${t.tipo}`} className="text-xs text-gray-400 tabular-nums pl-5">{FMT_BRL(t.total)}</div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Comprometimentos por fornecedor */}
              {comprometimentos.length > 0 && (
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Parcelas Pendentes (Contratos)</h3>
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart data={comprometimentos} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                      <XAxis type="number" tickFormatter={FMT_COMPACT} tick={{ fontSize: 10, fill: isDark ? '#6b7280' : '#9ca3af' }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="fornecedor" width={110} tick={{ fontSize: 9, fill: isDark ? '#6b7280' : '#9ca3af' }}
                        tickFormatter={(v: string) => v.split(' ').slice(0, 2).join(' ')} axisLine={false} tickLine={false} />
                      <Tooltip formatter={(v: number) => FMT_BRL(v)} labelFormatter={(l: string) => l} contentStyle={{ background: isDark ? '#111827' : '#fff', border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`, borderRadius: 8, fontSize: 11 }} />
                      <Bar dataKey="total_pendente" fill="#6366f1" radius={[0, 4, 4, 0]} name="Pendente" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* Gráfico mensal */}
          {chartData.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Evolução Mensal</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 0, right: 8, left: 0, bottom: 0 }} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1f2937' : '#f3f4f6'} />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: isDark ? '#6b7280' : '#9ca3af' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={FMT_COMPACT}
                    tick={{ fontSize: 11, fill: isDark ? '#6b7280' : '#9ca3af' }}
                    axisLine={false}
                    tickLine={false}
                    width={70}
                  />
                  <Tooltip
                    formatter={(v: number, name: string) => [FMT_BRL(v), name]}
                    contentStyle={{
                      background: isDark ? '#111827' : '#fff',
                      border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="Total" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Tabela de fornecedores */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Gastos por Fornecedor</h3>
              <p className="text-xs text-gray-400 mt-0.5">Clique em um fornecedor para ver os documentos</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 uppercase tracking-wide">
                    <th className="px-4 py-3 text-left font-medium">Fornecedor</th>
                    <th className="px-4 py-3 text-left font-medium">Categoria</th>
                    <th className="px-4 py-3 text-right font-medium">Total</th>
                    <th className="px-4 py-3 text-center font-medium">Docs</th>
                    <th className="px-4 py-3 text-left font-medium">Período</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.fornecedores.map((f) => (
                    <>
                      <tr
                        key={f.fornecedor}
                        onClick={() => setSelectedSupplier(selectedSupplier === f.fornecedor ? null : f.fornecedor)}
                        className={`cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50 ${
                          selectedSupplier === f.fornecedor ? 'bg-brand-soft dark:bg-brand-green/5' : ''
                        }`}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-gray-800 dark:text-gray-200">{f.fornecedor}</span>
                            {f.is_pj_collaborator && (
                              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                                Colaborador PJ
                              </span>
                            )}
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${TIPO_BADGE[f.tipo] ?? 'bg-gray-100 text-gray-600'}`}>
                              {f.tipo}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${CATEGORIA_BADGE[f.categoria] ?? 'bg-gray-100 text-gray-600'}`}>
                            {f.categoria}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums text-gray-700 dark:text-gray-300">
                          {FMT_BRL(f.total)}
                        </td>
                        <td className="px-4 py-3 text-center text-gray-500">{f.qtd}</td>
                        <td className="px-4 py-3 text-xs text-gray-400">
                          {FMT_DATE(f.primeira_data)} → {FMT_DATE(f.ultima_data)}
                        </td>
                      </tr>
                      {selectedSupplier === f.fornecedor && (
                        <tr key={`${f.fornecedor}-detail`}>
                          <td colSpan={5} className="p-0">
                            <div className="bg-gray-50 dark:bg-gray-800/30 border-t border-gray-100 dark:border-gray-700 px-6 py-3">
                              {detailForSupplier.length === 0 ? (
                                <p className="text-xs text-gray-400 py-2">Carregando documentos…</p>
                              ) : (
                                <table className="w-full text-xs">
                                  <thead>
                                    <tr className="text-gray-400 uppercase tracking-wide">
                                      <th className="py-1.5 text-left font-medium">Histórico</th>
                                      <th className="py-1.5 text-left font-medium">Vencimento</th>
                                      <th className="py-1.5 text-left font-medium">Liquidação</th>
                                      <th className="py-1.5 text-right font-medium">Valor</th>
                                      <th className="py-1.5 text-center font-medium">Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                    {detailForSupplier.map((d, j) => (
                                      <tr key={j} className="text-gray-600 dark:text-gray-400">
                                        <td className="py-1.5 max-w-xs truncate" title={d.historico}>{d.historico || '—'}</td>
                                        <td className="py-1.5">{FMT_DATE(d.datavencimento)}</td>
                                        <td className="py-1.5">{FMT_DATE(d.dataliquidacao)}</td>
                                        <td className="py-1.5 text-right font-mono tabular-nums">{FMT_BRL(d.valor)}</td>
                                        <td className="py-1.5 text-center">
                                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                            d.status_par === 'pago'
                                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                              : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                                          }`}>
                                            {d.status_par === 'pago' ? 'Pago' : 'Pendente'}
                                          </span>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Comprometimentos detalhados */}
          {comprometimentos.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Parcelas Pendentes por Contrato</h3>
                <p className="text-xs text-gray-400 mt-0.5">Contratos com parcelas ainda não liquidadas no Benner</p>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {comprometimentos.map(c => (
                  <div key={c.fornecedor}>
                    <div
                      className="px-5 py-3 flex items-center justify-between gap-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                      onClick={() => setExpandedComp(expandedComp === c.fornecedor ? null : c.fornecedor)}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="font-medium text-sm text-gray-800 dark:text-gray-200 truncate">{c.fornecedor}</span>
                        <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${CATEGORIA_BADGE[c.categoria] ?? 'bg-gray-100 text-gray-600'}`}>{c.categoria}</span>
                      </div>
                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-right">
                          <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400 tabular-nums">{FMT_BRL(c.total_pendente)}</p>
                          <p className="text-xs text-gray-400">{c.qtd} parcela{c.qtd !== 1 ? 's' : ''} · até {FMT_DATE(c.ultima_vencimento)}</p>
                        </div>
                        <span className="text-gray-400 text-xs">{expandedComp === c.fornecedor ? '▲' : '▼'}</span>
                      </div>
                    </div>
                    {expandedComp === c.fornecedor && (
                      <div className="px-5 pb-3 bg-gray-50 dark:bg-gray-800/30">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-gray-400 uppercase tracking-wide">
                              <th className="py-1.5 text-left font-medium">Vencimento</th>
                              <th className="py-1.5 text-right font-medium">Valor</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                            {c.parcelas.map((p, i) => (
                              <tr key={i} className="text-gray-600 dark:text-gray-400">
                                <td className="py-1.5">{FMT_DATE(p.datavencimento)}</td>
                                <td className="py-1.5 text-right font-mono tabular-nums">{FMT_BRL(p.valor)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Mídia Tab ──────────────────────────────────────────────────────────────────

function MidiaTab({ token }: { token: string }) {
  const [posts, setPosts] = useState<MediaPost[]>([])
  const [metrics, setMetrics] = useState<MediaMetrics[]>([])
  const [sentimentFilter, setSentimentFilter] = useState<string>('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [p, m] = await Promise.all([
        apiFetch<MediaPost[]>('/api/expenses/payfly/media/posts', { token }),
        apiFetch<MediaMetrics[]>('/api/expenses/payfly/media/metrics', { token }),
      ])
      setPosts(p)
      setMetrics(m)
    } catch {
      setPosts([])
      setMetrics([])
    } finally { setLoading(false) }
  }, [token])

  useEffect(() => { load() }, [load])

  const filtered = sentimentFilter
    ? posts.filter(p => p.sentiment === sentimentFilter)
    : posts

  // Current month metrics
  const now = new Date()
  const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const prevMonth = now.getMonth() === 0
    ? `${now.getFullYear() - 1}-12`
    : `${now.getFullYear()}-${String(now.getMonth()).padStart(2, '0')}`

  const getMetrics = (month: string) =>
    metrics.find(m => m.ref_month === month && m.platform === 'google_news') ??
    { posts_count: 0, positive_count: 0, negative_count: 0, neutral_count: 0 }

  const cur = getMetrics(thisMonth)
  const prev = getMetrics(prevMonth)

  function toggleExpanded(id: string) {
    setExpanded(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  return (
    <div className="space-y-6">
      {/* Dashboard cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Posts (mês)', cur: cur.posts_count, prev: prev.posts_count },
          { label: 'Positivos', cur: cur.positive_count, prev: prev.positive_count, accent: 'green' },
          { label: 'Negativos', cur: cur.negative_count, prev: prev.negative_count, accent: 'red' },
          { label: 'Neutros', cur: cur.neutral_count, prev: prev.neutral_count },
        ].map(({ label, cur: c, prev: p, accent }) => (
          <div key={label} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
            <div className="mt-1 flex items-end gap-2">
              <p className={`text-2xl font-bold ${
                accent === 'green' ? 'text-green-600 dark:text-green-400' :
                accent === 'red'   ? 'text-red-600 dark:text-red-400'    :
                'text-gray-900 dark:text-gray-100'
              }`}>{c}</p>
              <TrendArrow value={c - p} />
            </div>
            <p className="mt-0.5 text-xs text-gray-400">mês anterior: {p}</p>
          </div>
        ))}
      </div>

      {/* Filtro de sentimento */}
      <div className="flex items-center gap-2">
        {['', 'positivo', 'negativo', 'neutro'].map(s => (
          <button
            key={s || 'todos'}
            onClick={() => setSentimentFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              sentimentFilter === s
                ? 'bg-brand-green text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            {s ? s.charAt(0).toUpperCase() + s.slice(1) : 'Todos'}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400">{filtered.length} publicações</span>
      </div>

      {loading && (
        <div className="animate-pulse space-y-2">
          {[...Array(5)].map((_, i) => <div key={i} className="h-16 rounded-xl bg-gray-200 dark:bg-gray-800" />)}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-12 text-sm text-gray-400">
          <p>Nenhuma publicação encontrada.</p>
          <p className="mt-1 text-xs">O agente de monitoramento busca dados periodicamente via Google News RSS.</p>
        </div>
      )}

      {/* Lista de posts */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {filtered.map(post => (
            <div key={post.id} className="p-4">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <a
                      href={post.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-gray-800 dark:text-gray-200 hover:text-brand-green dark:hover:text-brand-mid truncate max-w-xl"
                    >
                      {post.title}
                    </a>
                    <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${SENTIMENT_BADGE[post.sentiment]}`}>
                      {post.sentiment}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-400">
                    {post.source && <span>{post.source}</span>}
                    <span>·</span>
                    <span>{FMT_DATETIME(post.published_at)}</span>
                    <span>·</span>
                    <span className="uppercase tracking-wide">{post.platform.replace('_', ' ')}</span>
                  </div>
                  {post.snippet && (
                    <button
                      onClick={() => toggleExpanded(post.id)}
                      className="mt-1 text-xs text-brand-green hover:underline"
                    >
                      {expanded.has(post.id) ? 'Ocultar prévia ▲' : 'Ver prévia ▼'}
                    </button>
                  )}
                  {expanded.has(post.id) && post.snippet && (
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
                      {post.snippet}
                    </p>
                  )}
                </div>
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 h-8 w-8 rounded-lg border border-gray-200 dark:border-gray-700 flex items-center justify-center hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  title="Abrir matéria"
                >
                  <svg className="h-3.5 w-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Chamados Tab ───────────────────────────────────────────────────────────────

function ChamadosTab({ token }: { token: string }) {
  const [dash, setDash] = useState<FreshDashboard | null>(null)
  const [tickets, setTickets] = useState<FreshTicket[]>([])
  const [ticketFilter, setTicketFilter] = useState<'abertos' | 'fechados' | 'todos'>('abertos')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const loadDash = useCallback(async () => {
    setLoading(true)
    try {
      const d = await apiFetch<FreshDashboard>('/api/freshservice/payfly/dashboard', { token })
      setDash(d)
    } catch {
      setDash(null)
    } finally { setLoading(false) }
  }, [token])

  const loadTickets = useCallback(async () => {
    setLoadingTickets(true)
    try {
      const r = await apiFetch<{ data: FreshTicket[]; total: number }>(
        `/api/freshservice/payfly/tickets?status_filter=${ticketFilter}&page=${page}&page_size=50`,
        { token }
      )
      setTickets(r.data)
      setTotal(r.total)
    } catch {
      setTickets([])
    } finally { setLoadingTickets(false) }
  }, [token, ticketFilter, page])

  useEffect(() => { loadDash() }, [loadDash])
  useEffect(() => { loadTickets() }, [loadTickets])

  function toggleExpanded(id: number) {
    setExpanded(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  return (
    <div className="space-y-6">
      {loading && (
        <div className="animate-pulse grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl bg-gray-200 dark:bg-gray-800" />)}
        </div>
      )}

      {dash?.error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-900/20 p-4 text-sm text-amber-700 dark:text-amber-400">
          {dash.error}
        </div>
      )}

      {dash && !loading && (
        <>
          {/* Dashboard de status */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total</p>
              <div className="mt-1 flex items-end gap-2">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{dash.total}</p>
                <TrendArrow value={dash.trend_total} />
              </div>
              {dash.group_name && <p className="mt-0.5 text-xs text-gray-400">{dash.group_name}</p>}
            </div>

            <div className="rounded-xl border border-blue-200 dark:border-blue-800/50 bg-blue-50 dark:bg-blue-900/10 p-5">
              <p className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wide">Abertos</p>
              <p className="mt-1 text-2xl font-bold text-blue-700 dark:text-blue-300">{dash.abertos + dash.pendentes}</p>
              <p className="mt-0.5 text-xs text-blue-400">{dash.pct_abertos.toFixed(1)}% do total</p>
            </div>

            <div className="rounded-xl border border-green-200 dark:border-green-800/50 bg-green-50 dark:bg-green-900/10 p-5">
              <p className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wide">Fechados</p>
              <div className="mt-1 flex items-end gap-2">
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">{dash.resolvidos + dash.fechados}</p>
                <TrendArrow value={dash.trend_fechados} />
              </div>
              <p className="mt-0.5 text-xs text-green-400">{dash.pct_fechados.toFixed(1)}% do total</p>
            </div>

            <div className="rounded-xl border border-purple-200 dark:border-purple-800/50 bg-purple-50 dark:bg-purple-900/10 p-5">
              <p className="text-xs font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wide">Aguard. Fornecedor</p>
              <p className="mt-1 text-2xl font-bold text-purple-700 dark:text-purple-300">{dash.aguardando_fornecedor}</p>
              <p className="mt-0.5 text-xs text-purple-400">{dash.pct_aguardando.toFixed(1)}% do total</p>
            </div>
          </div>

          {/* SLA + Resolução */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">SLA Compliance</p>
              <div className="flex items-center gap-3">
                <p className={`text-3xl font-bold ${dash.sla_compliance_pct >= 80 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {dash.sla_compliance_pct.toFixed(1)}%
                </p>
                <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${dash.sla_compliance_pct >= 80 ? 'bg-green-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(dash.sla_compliance_pct, 100)}%` }}
                  />
                </div>
              </div>
              <p className="mt-1 text-xs text-gray-400">Chamados resolvidos dentro do prazo</p>
            </div>

            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Tempo Médio de Resolução</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                {dash.avg_resolution_time_hours != null
                  ? `${dash.avg_resolution_time_hours}h`
                  : '—'}
              </p>
              {/* Breakdown por prioridade */}
              <div className="mt-2 flex gap-3 flex-wrap">
                {Object.entries(dash.by_priority).map(([p, c]) => {
                  const pr = FS_PRIORITY[Number(p)]
                  return pr ? (
                    <span key={p} className={`text-xs ${pr.cls}`}>
                      {pr.label}: {c}
                    </span>
                  ) : null
                })}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Listagem de tickets */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Chamados</h3>
          <div className="flex gap-1.5 ml-auto">
            {(['abertos', 'fechados', 'todos'] as const).map(f => (
              <button
                key={f}
                onClick={() => { setTicketFilter(f); setPage(1) }}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  ticketFilter === f
                    ? 'bg-brand-green text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {loadingTickets ? (
          <div className="animate-pulse space-y-2 p-4">
            {[...Array(5)].map((_, i) => <div key={i} className="h-10 rounded bg-gray-200 dark:bg-gray-800" />)}
          </div>
        ) : tickets.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">Nenhum chamado encontrado.</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 uppercase tracking-wide">
                    <th className="px-4 py-3 text-left font-medium">ID</th>
                    <th className="px-4 py-3 text-left font-medium">Assunto</th>
                    <th className="px-4 py-3 text-center font-medium">Status</th>
                    <th className="px-4 py-3 text-center font-medium">Prioridade</th>
                    <th className="px-4 py-3 text-left font-medium">Abertura</th>
                    <th className="px-4 py-3 text-center font-medium">SLA</th>
                    <th className="px-4 py-3 text-left font-medium">Agente</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {tickets.map(t => (
                    <>
                      <tr
                        key={t.id}
                        onClick={() => toggleExpanded(t.id)}
                        className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                      >
                        <td className="px-4 py-3 font-mono text-xs text-gray-500">#{t.id}</td>
                        <td className="px-4 py-3 max-w-xs">
                          <span className="text-gray-800 dark:text-gray-200 font-medium line-clamp-1">{t.subject}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${FS_STATUS[t.status]?.cls ?? ''}`}>
                            {FS_STATUS[t.status]?.label ?? `Status ${t.status}`}
                          </span>
                        </td>
                        <td className={`px-4 py-3 text-center text-xs ${FS_PRIORITY[t.priority]?.cls ?? ''}`}>
                          {FS_PRIORITY[t.priority]?.label ?? `P${t.priority}`}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">{FMT_DATETIME(t.created_at)}</td>
                        <td className="px-4 py-3 text-center">
                          {t.sla_breached === true ? (
                            <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Violado</span>
                          ) : t.sla_breached === false ? (
                            <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Ok</span>
                          ) : <span className="text-gray-400 text-xs">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">{t.agent_name ?? '—'}</td>
                      </tr>
                      {expanded.has(t.id) && (
                        <tr key={`${t.id}-detail`}>
                          <td colSpan={5} className="p-0">
                            <div className="bg-gray-50 dark:bg-gray-800/30 border-t border-gray-100 dark:border-gray-700 px-6 py-3 text-xs text-gray-600 dark:text-gray-400">
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div><span className="font-medium">Prazo (SLA):</span> {FMT_DATETIME(t.due_by)}</div>
                                <div><span className="font-medium">Resolvido em:</span> {FMT_DATETIME(t.resolved_at)}</div>
                                <div><span className="font-medium">Fechado em:</span> {FMT_DATETIME(t.closed_at)}</div>
                                <div><span className="font-medium">Tempo resolução:</span> {t.resolution_time_min ? `${Math.round(t.resolution_time_min / 60)}h` : '—'}</div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginação */}
            {total > 50 && (
              <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between text-xs text-gray-500">
                <span>{total} chamados no total</span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                    className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >← Anterior</button>
                  <span className="px-3 py-1">Página {page}</span>
                  <button
                    disabled={page * 50 >= total}
                    onClick={() => setPage(p => p + 1)}
                    className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >Próxima →</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function PayFlyPage() {
  const { token } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const activeTab = (searchParams.get('tab') as PayFlyTab) ?? 'investimentos'

  function setTab(t: PayFlyTab) {
    navigate(`/admin/payfly?tab=${t}`, { replace: true })
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">PayFly</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Acompanhamento de investimentos, chamados, mídia e governança
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800">
        <nav className="flex gap-1 overflow-x-auto">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === t.id
                  ? 'border-brand-green text-brand-green dark:text-brand-mid'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'investimentos' && <InvestimentosTab token={token ?? ''} />}
      {activeTab === 'monitoramento' && <Placeholder title="Monitoramento" />}
      {activeTab === 'governanca'    && <Placeholder title="Governança & Auditoria" />}
      {activeTab === 'midia'         && <MidiaTab token={token ?? ''} />}
      {activeTab === 'chamados'      && <ChamadosTab token={token ?? ''} />}
    </div>
  )
}
