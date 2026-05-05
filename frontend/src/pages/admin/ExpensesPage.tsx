import { useCallback, useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { ApiError, apiFetch } from '../../lib/api'
import type {
  ExpenseDashboard,
  ExpenseRow,
  ForecastDashboard,
  ForecastFornecedor,
} from '../../types/expenses'
import KPICard from '../../components/expenses/KPICard'
import YearSelector from '../../components/expenses/YearSelector'
import ForecastChart from '../../components/expenses/ForecastChart'
import DonutOrigem from '../../components/expenses/DonutOrigem'
import FornecedoresRadial from '../../components/expenses/FornecedoresRadial'

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
const COLOR_LY       = '#9ca3af'
const COLOR_2025     = '#6b7280'
const COLOR_2026     = '#3b82f6'
const COLOR_TEAL     = '#14b8a6'

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
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-28 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
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
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-xs shadow-xl">
      <p className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-gray-800 dark:text-gray-200 font-medium">{FMT_BRL(p.value ?? 0)}</span>
        </div>
      ))}
    </div>
  )
}


// ── Supplier accordion ────────────────────────────────────────────────────────

interface SupplierGroup {
  pessoa: string
  total: number
  count: number
  origens: string[]
  rows: ExpenseRow[]
}

function buildSupplierGroups(rows: ExpenseRow[]): SupplierGroup[] {
  const map = new Map<string, SupplierGroup>()
  for (const row of rows) {
    const key = row.PESSOA || 'Sem fornecedor'
    if (!map.has(key)) {
      map.set(key, { pessoa: key, total: 0, count: 0, origens: [], rows: [] })
    }
    const g = map.get(key)!
    g.total += row.VALOR ?? 0
    g.count += 1
    g.rows.push(row)
    if (row.ORIGEM && !g.origens.includes(row.ORIGEM)) g.origens.push(row.ORIGEM)
  }
  return [...map.values()].sort((a, b) => b.total - a.total)
}

function SupplierAccordion({
  groups,
  fmtBrl,
}: {
  groups: SupplierGroup[]
  fmtBrl: (v: number) => string
}) {
  const [expanded, setExpanded] = useState<string | null>(null)

  function toggle(key: string) {
    setExpanded((prev) => (prev === key ? null : key))
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Gastos por Fornecedor
          <span className="ml-2 text-xs font-normal text-gray-500">({groups.length} fornecedores)</span>
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              <th className="px-5 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500">Fornecedor</th>
              <th className="px-5 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Parcelas</th>
              <th className="px-5 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Total</th>
              <th className="px-5 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500">Origem</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60">
        {groups.map((g) => {
          const isOpen = expanded === g.pessoa
          return (
            <>
              <tr
                key={g.pessoa}
                onClick={() => toggle(g.pessoa)}
                className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors cursor-pointer"
              >
                <td className="px-5 py-3">
                  <span className="font-medium text-gray-800 dark:text-gray-100 break-words">{g.pessoa}</span>
                </td>
                <td className="px-5 py-3 text-right text-gray-500 tabular-nums whitespace-nowrap">{g.count}</td>
                <td className="px-5 py-3 text-right font-semibold text-gray-900 dark:text-white tabular-nums whitespace-nowrap">{fmtBrl(g.total)}</td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1">{g.origens.map((o) => <OrigemBadge key={o} origem={o} />)}</div>
                </td>
                <td className="px-3 py-3 text-center text-gray-400 w-8">
                  <span className={`inline-block transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`}>›</span>
                </td>
              </tr>

              {/* Detalhe expandido — row aninhada com subtabela */}
              {isOpen && (
                <tr key={`${g.pessoa}-det`} className="bg-gray-50/70 dark:bg-gray-800/20">
                  <td colSpan={5} className="px-0 py-0">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="border-y border-gray-200 dark:border-gray-700">
                          {['Histórico', 'Conta', 'Valor', 'Vencimento', 'Liquidação', 'Filial', 'Origem', 'Tipo'].map((h) => (
                            <th key={h} className={`px-5 py-2 text-[10px] font-semibold uppercase tracking-wide text-gray-400 ${h === 'Valor' ? 'text-right' : 'text-left'}`}>
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800/40">
                        {g.rows.map((row, i) => (
                          <tr key={i} className="hover:bg-white dark:hover:bg-gray-800/30 transition-colors">
                            <td className="px-5 py-2 max-w-[200px] truncate text-gray-600 dark:text-gray-400 text-[10px]" title={row.HISTORICO ?? row.DOCUMENTODIGITADO ?? ''}>{row.HISTORICO || row.DOCUMENTODIGITADO || '—'}</td>
                            <td className="px-5 py-2 max-w-[160px] truncate text-gray-600 dark:text-gray-400" title={row.CONTA ?? ''}>{row.CONTA || '—'}</td>
                            <td className="px-5 py-2 text-right font-semibold text-gray-800 dark:text-gray-100 whitespace-nowrap tabular-nums">{fmtBrl(row.VALOR ?? 0)}</td>
                            <td className="px-5 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap tabular-nums">{row.DATAVENCIMENTO ? row.DATAVENCIMENTO.slice(0, 10) : '—'}</td>
                            <td className="px-5 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap tabular-nums">{row.DATALIQUIDACAO ? row.DATALIQUIDACAO.slice(0, 10) : '—'}</td>
                            <td className="px-5 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{row.FILIAL}</td>
                            <td className="px-5 py-2"><OrigemBadge origem={row.ORIGEM} /></td>
                            <td className="px-5 py-2"><TipoBadge tipo={row.TIPO_DOC} /></td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-gray-200 dark:border-gray-700">
                          <td className="px-5 py-2 text-[10px] text-gray-400">{g.count} lançamentos</td>
                          <td />
                          <td className="px-5 py-2 text-right font-bold text-gray-900 dark:text-white whitespace-nowrap tabular-nums">{fmtBrl(g.total)}</td>
                          <td colSpan={5} />
                        </tr>
                      </tfoot>
                    </table>
                  </td>
                </tr>
              )}
            </>
          )
        })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Eventual detail section ───────────────────────────────────────────────────

function EventualDetailTable({ rows, fmtBrl }: { rows: ExpenseRow[]; fmtBrl: (v: number) => string }) {
  const eventualRows = rows
    .filter((r) => r.CATEGORIA === 'Eventual')
    .sort((a, b) => (b.VALOR ?? 0) - (a.VALOR ?? 0))

  if (eventualRows.length === 0) return null

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Detalhamento — Gastos Eventuais
          <span className="ml-2 text-xs font-normal text-gray-500">({eventualRows.length} lançamentos)</span>
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              {['Fornecedor', 'Histórico / Descrição', 'Valor', 'Liquidação', 'Filial'].map((h) => (
                <th key={h} className={`px-5 py-2.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500 ${h === 'Valor' ? 'text-right' : 'text-left'}`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60">
            {eventualRows.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                <td className="px-5 py-2.5 font-medium text-gray-800 dark:text-gray-100 max-w-[160px] truncate" title={row.PESSOA}>{row.PESSOA || '—'}</td>
                <td className="px-5 py-2.5 text-gray-600 dark:text-gray-400 max-w-[280px] truncate" title={row.HISTORICO ?? ''}>{row.HISTORICO || row.DOCUMENTODIGITADO || '—'}</td>
                <td className="px-5 py-2.5 text-right font-semibold text-gray-900 dark:text-white whitespace-nowrap tabular-nums">{fmtBrl(row.VALOR ?? 0)}</td>
                <td className="px-5 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap tabular-nums">{row.DATALIQUIDACAO ? row.DATALIQUIDACAO.slice(0, 10) : '—'}</td>
                <td className="px-5 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">{row.FILIAL}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Comparison 2025 vs 2026 tab ───────────────────────────────────────────────

const SHORT_MONTHS_LIST = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

function ComparisonTab({
  byOrigemMensal,
  yoyMensal,
  currentYear,
  fmtBrl,
  fmtCompact,
  chartGrid,
  chartTick,
}: {
  byOrigemMensal: { mes: string; contrato: number; eventual: number }[]
  yoyMensal: Record<string, { contrato: number; eventual: number }>
  currentYear: number
  fmtBrl: (v: number) => string
  fmtCompact: (v: number) => string
  chartGrid: string
  chartTick: string
}) {
  const priorYear = currentYear - 1

  // Build month-by-month comparison
  const months = Array.from({ length: 12 }, (_, i) => {
    const mm = String(i + 1).padStart(2, '0')
    const curKey = `${currentYear}-${mm}`
    const priKey = `${priorYear}-${mm}`
    const cur = byOrigemMensal.find((m) => m.mes === curKey)
    const pri = yoyMensal[priKey]
    const curTotal = (cur?.contrato ?? 0) + (cur?.eventual ?? 0)
    const priTotal = (pri?.contrato ?? 0) + (pri?.eventual ?? 0)
    const pct = priTotal > 0 ? ((curTotal / priTotal - 1) * 100) : null
    return {
      mes: SHORT_MONTHS_LIST[i],
      [`${priorYear}_cont`]: pri?.contrato ?? null,
      [`${priorYear}_ev`]: pri?.eventual ?? null,
      [`${priorYear}`]: priTotal > 0 ? priTotal : null,
      [`${currentYear}_cont`]: cur?.contrato ?? null,
      [`${currentYear}_ev`]: cur?.eventual ?? null,
      [`${currentYear}`]: curTotal > 0 ? curTotal : null,
      pct,
    }
  })

  const priTotal = Object.values(yoyMensal).reduce((s, v) => s + v.contrato + v.eventual, 0)
  const curTotal = byOrigemMensal.reduce((s, m) => s + m.contrato + m.eventual, 0)
  const priCont = Object.values(yoyMensal).reduce((s, v) => s + v.contrato, 0)
  const curCont = byOrigemMensal.reduce((s, m) => s + m.contrato, 0)
  const priEv = Object.values(yoyMensal).reduce((s, v) => s + v.eventual, 0)
  const curEv = byOrigemMensal.reduce((s, m) => s + m.eventual, 0)

  function pctBadge(cur: number, pri: number) {
    if (pri === 0) return null
    const p = ((cur / pri - 1) * 100).toFixed(1)
    const up = cur > pri
    return (
      <span className={`text-[10px] font-semibold ${up ? 'text-red-500' : 'text-emerald-500'}`}>
        {up ? '▲' : '▼'} {Math.abs(Number(p))}%
      </span>
    )
  }

  const COLOR_PRI = '#6b7280'
  const COLOR_CUR = '#3b82f6'

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Total Geral', pri: priTotal, cur: curTotal },
          { label: 'Contratos', pri: priCont, cur: curCont },
          { label: 'Eventual', pri: priEv, cur: curEv },
        ].map(({ label, pri, cur }) => (
          <div key={label} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 mb-3">{label}</p>
            <div className="flex items-end justify-between gap-2">
              <div>
                <p className="text-[10px] text-gray-400 mb-0.5">{priorYear}</p>
                <p className="text-lg font-bold text-gray-400 tabular-nums">{fmtCompact(pri)}</p>
              </div>
              <div className="text-center">{pctBadge(cur, pri)}</div>
              <div className="text-right">
                <p className="text-[10px] text-gray-400 mb-0.5">{currentYear}</p>
                <p className="text-lg font-bold text-blue-500 tabular-nums">{fmtCompact(cur)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Grouped bar chart */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
          Evolução Mensal — {priorYear} vs {currentYear}
        </h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={months} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} vertical={false} />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: chartTick }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={fmtCompact} tick={{ fontSize: 10, fill: chartTick }} axisLine={false} tickLine={false} width={65} />
            <Tooltip
              formatter={(v: number) => [fmtBrl(v)]}
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
              itemStyle={{ color: '#e5e7eb' }}
              cursor={{ fill: 'rgba(255,255,255,0.05)' }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: chartTick, paddingTop: 8 }} />
            <Bar dataKey={String(priorYear)} name={String(priorYear)} fill={COLOR_PRI} radius={[3, 3, 0, 0]} maxBarSize={24} />
            <Bar dataKey={String(currentYear)} name={String(currentYear)} fill={COLOR_CUR} radius={[3, 3, 0, 0]} maxBarSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Month-by-month table */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Detalhamento Mês a Mês</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500">Mês</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-gray-400">{priorYear} Cont.</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-gray-400">{priorYear} Ev.</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-gray-400">{priorYear} Total</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-blue-400">{currentYear} Cont.</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-blue-400">{currentYear} Ev.</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wide text-blue-400">{currentYear} Total</th>
                <th className="px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-wide text-gray-500">Δ%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60">
              {months.map((m) => {
                const priT = (m[String(priorYear)] as number | null) ?? 0
                const curT = (m[String(currentYear)] as number | null) ?? 0
                const hasData = priT > 0 || curT > 0
                if (!hasData) return null
                return (
                  <tr key={m.mes} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-2.5 font-semibold text-gray-700 dark:text-gray-300">{m.mes}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-gray-500">{(m[`${priorYear}_cont`] as number | null) ? fmtBrl(m[`${priorYear}_cont`] as number) : '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-gray-500">{(m[`${priorYear}_ev`] as number | null) ? fmtBrl(m[`${priorYear}_ev`] as number) : '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-medium text-gray-700 dark:text-gray-300">{priT > 0 ? fmtBrl(priT) : '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-blue-400">{(m[`${currentYear}_cont`] as number | null) ? fmtBrl(m[`${currentYear}_cont`] as number) : '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-blue-400">{(m[`${currentYear}_ev`] as number | null) ? fmtBrl(m[`${currentYear}_ev`] as number) : '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-blue-500">{curT > 0 ? fmtBrl(curT) : '—'}</td>
                    <td className="px-4 py-2.5 text-center">
                      {m.pct != null ? (
                        <span className={`font-semibold ${m.pct > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                          {m.pct > 0 ? '+' : ''}{(m.pct as number).toFixed(1)}%
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 font-semibold">
                <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300 text-[11px]">TOTAL</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-gray-500">{fmtBrl(priCont)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-gray-500">{fmtBrl(priEv)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-gray-700 dark:text-gray-300">{fmtBrl(priTotal)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-blue-400">{fmtBrl(curCont)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-blue-400">{fmtBrl(curEv)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-blue-500">{fmtBrl(curTotal)}</td>
                <td className="px-4 py-2.5 text-center">
                  {priTotal > 0 ? (
                    <span className={`font-semibold ${curTotal > priTotal ? 'text-red-400' : 'text-emerald-400'}`}>
                      {curTotal > priTotal ? '+' : ''}{(((curTotal / priTotal) - 1) * 100).toFixed(1)}%
                    </span>
                  ) : '—'}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

type ActiveTab = 'gastos' | 'previsao' | 'comparacao'

export default function ExpensesPage() {
  const { token } = useAuth()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  // Theme-aware chart colors
  const chartGrid   = isDark ? '#374151' : '#e5e7eb'
  const chartTick   = isDark ? '#9ca3af' : '#6b7280'
  const tooltipBg   = isDark ? '#111827' : '#ffffff'
  const tooltipBorder = isDark ? '#374151' : '#e5e7eb'
  const tooltipText = isDark ? '#e5e7eb' : '#1f2937'
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

  const supplierGroups = buildSupplierGroups(filteredRows)

  // Build monthly chart data: merge by_origem_mensal with yoy
  const monthlyChartData = (data?.by_origem_mensal ?? []).map((m) => {
    const lyKey = m.mes.replace(String(year), String(year - 1))
    return {
      mes: shortMonth(m.mes),
      mesKey: m.mes,
      Contrato: m.contrato,
      Eventual: m.eventual,
      Total: m.contrato + m.eventual,
      LY: data?.yoy?.[lyKey] ?? null,
    }
  })

  const showLY = year === 2026 && Object.keys(data?.yoy ?? {}).length > 0

  // Donut total
  const origemTotal = (data?.by_origem ?? []).reduce((s, o) => s + o.valor, 0)

  // Top 5 fornecedores
  const topFornecedores = [...(data?.by_fornecedor ?? [])]
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 5)

  // Filiais sorted desc
  const filiaisData = [...(data?.by_filial ?? [])].sort((a, b) => b.valor - a.valor).slice(0, 5)

  // DonutOrigem data (after origemTotal)
  const ORIGEM_COLORS_LIST = ['#3b82f6', '#8b5cf6', '#6b7280', '#f97316']
  const origemData = (data?.by_origem ?? []).map((o) => ({
    name: o.origem,
    value: o.valor,
    pct: origemTotal > 0 ? Math.round((o.valor / origemTotal) * 100) : 0,
  }))

  // FornecedoresRadial data (after topFornecedores)
  const RADIAL_COLORS = ['#3b82f6', '#8b5cf6', '#14b8a6', '#f97316', '#ef4444']
  const maxForn = topFornecedores[0]?.valor ?? 1
  const fornecedoresRadialData = topFornecedores.map((f) => ({
    name: f.pessoa.length > 28 ? f.pessoa.slice(0, 26) + '…' : f.pessoa,
    value: f.valor,
    pct: Math.round((f.valor / maxForn) * 100),
  }))

  // ForecastChart data — filter to forecast year only, use stacked band
  const forecastMapped = (forecast?.meses ?? [])
    .filter((m) => m.mes.startsWith('2026'))
    .map((m) => {
      const minV = m.valor_min ?? null
      const maxV = m.valor_max ?? null
      return {
        mes: shortMonth(m.mes),
        real: m.tipo === 'real'     ? m.valor : null,
        proj: m.tipo === 'projecao' ? m.valor : null,
        base: minV,
        band: (minV != null && maxV != null) ? maxV - minV : null,
      }
    })

  // YoY comparison chart (months that exist in both years)
  const yoyChartData = (data?.by_origem_mensal ?? []).map((m) => {
    const lyKey = m.mes.replace(String(year), String(year - 1))
    return {
      mes: shortMonth(m.mes),
      [String(year)]: m.contrato + m.eventual,
      [String(year - 1)]: data?.yoy?.[lyKey] ?? null,
    }
  }).filter((d) => d[String(year - 1)] !== null)

  // Current month key for reference line
  const currentMonth = new Date().toISOString().slice(0, 7) // "2026-05"

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 p-6 space-y-6 max-w-[1440px] mx-auto">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard Financeiro — TI</h1>
          <p className="text-sm text-gray-500 mt-1">
            VTC Operadora Logística · Despesas do departamento de TI (K_GESTOR 23)
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <YearSelector value={year} onChange={(y) => { setYear(y); setData(null) }} />
          {data?.last_updated && (
            <span className="text-[11px] text-gray-400 tabular-nums">
              Atualizado: {new Date(data.last_updated).toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              })}
            </span>
          )}
        </div>
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
            value={FMT_BRL(data.kpis.total_ytd?.valor ?? data.kpis.total_valor)}
            loading={loading}
            accentColor="blue"
            subtitle={`${data.kpis.count_parcelas} parcelas`}
            comparison={[
              ...(data.kpis.total_ytd?.vs_mes_anterior ? [{
                label: 'vs. Mês Ant.',
                value: `${data.kpis.total_ytd.vs_mes_anterior.pct > 0 ? '+' : ''}${data.kpis.total_ytd.vs_mes_anterior.pct.toFixed(1)}%`,
                positive: data.kpis.total_ytd.vs_mes_anterior.direcao === 'baixa',
              }] : []),
              ...(data.kpis.total_ytd?.vs_ly ? [{
                label: `vs. ${year - 1}`,
                value: `${data.kpis.total_ytd.vs_ly.pct > 0 ? '+' : ''}${data.kpis.total_ytd.vs_ly.pct.toFixed(1)}%`,
                positive: data.kpis.total_ytd.vs_ly.direcao === 'baixa',
              }] : []),
            ]}
          />
          <KPICard
            title="Contratos"
            value={FMT_BRL(data.kpis.contratos?.valor ?? data.kpis.total_recorrente)}
            loading={loading}
            accentColor="violet"
            subtitle="despesas recorrentes"
            comparison={[
              ...(data.kpis.contratos?.vs_mes_anterior ? [{
                label: 'vs. Mês Ant.',
                value: `${data.kpis.contratos.vs_mes_anterior.pct > 0 ? '+' : ''}${data.kpis.contratos.vs_mes_anterior.pct.toFixed(1)}%`,
                positive: data.kpis.contratos.vs_mes_anterior.direcao === 'baixa',
              }] : []),
            ]}
          />
          <KPICard
            title="Eventual"
            value={FMT_BRL(data.kpis.eventual?.valor ?? data.kpis.total_eventual)}
            loading={loading}
            accentColor="amber"
            subtitle="compras e pontuais"
            comparison={[
              ...(data.kpis.eventual?.vs_mes_anterior ? [{
                label: 'vs. Mês Ant.',
                value: `${data.kpis.eventual.vs_mes_anterior.pct > 0 ? '+' : ''}${data.kpis.eventual.vs_mes_anterior.pct.toFixed(1)}%`,
                positive: data.kpis.eventual.vs_mes_anterior.direcao === 'baixa',
              }] : []),
            ]}
          />
          <KPICard
            title="Média Mensal"
            value={FMT_BRL(data.kpis.media_mensal_kpi?.valor ?? data.kpis.media_mensal_valor ?? data.kpis.media_mensal)}
            loading={loading}
            accentColor="teal"
            subtitle="no ano selecionado"
            comparison={[]}
          />
        </div>
      ) : null}

      {/* ── Sub-tabs ───────────────────────────────────────────────────────── */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-800 pb-0">
        {([
          { id: 'gastos', label: 'Gastos' },
          { id: 'previsao', label: 'Previsão' },
          { id: 'comparacao', label: `${year - 1} vs ${year}` },
        ] as { id: ActiveTab; label: string }[]).map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`px-5 py-2.5 text-sm font-semibold rounded-t-lg transition-colors -mb-px border-b-2 ${
              activeTab === id
                ? 'border-blue-500 text-blue-400 bg-white dark:bg-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-900/50'
            }`}
          >
            {label}
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
              className="h-9 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            >
              <option value="">Filial: Todas</option>
              {(data.filiais ?? []).map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>

            <div className="flex rounded-lg border border-gray-300 dark:border-gray-700 overflow-hidden">
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
                      : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
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
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
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
                      wrapperStyle={{ fontSize: 11, color: chartTick, paddingTop: 8 }}
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

            <DonutOrigem
              data={origemData}
              colors={ORIGEM_COLORS_LIST}
            />
          </div>

          {/* Row 2: Top Fornecedores + Por Filial */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <FornecedoresRadial
              data={fornecedoresRadialData}
              colors={RADIAL_COLORS}
            />

            <ChartCard title="Por Filial">
              {filiaisData.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-12">Sem dados</p>
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <BarChart
                    data={filiaisData}
                    margin={{ top: 5, right: 10, left: 10, bottom: 40 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} vertical={false} />
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

          {/* Row 3: Accordion por fornecedor */}
          <SupplierAccordion groups={supplierGroups} fmtBrl={FMT_BRL} />

          {/* Row 3b: Detalhamento eventuais */}
          <EventualDetailTable rows={filteredRows} fmtBrl={FMT_BRL} />

          {/* Row 4: Tabela de lançamentos (paginada) */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                Lançamentos
                <span className="ml-2 text-xs font-normal text-gray-500">({totalRows} registros)</span>
              </h2>
              {/* Pagination controls */}
              {totalPages > 1 && (
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 rounded border border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500 disabled:opacity-40 transition-colors"
                  >
                    ← Ant.
                  </button>
                  <span>
                    Página {page + 1} de {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-3 py-1 rounded border border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500 disabled:opacity-40 transition-colors"
                  >
                    Próx. →
                  </button>
                </div>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-800 text-left">
                    {['Pessoa / Fornecedor', 'Conta', 'Valor', 'Vencimento', 'Liquidação', 'Filial', 'Origem', 'Tipo'].map((h) => (
                      <th key={h} className={`pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-500 ${h === 'Valor' ? 'text-right' : ''}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60">
                  {pageRows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                      <td className="py-2 pr-4 max-w-[180px] truncate text-gray-800 dark:text-gray-100 font-medium text-xs" title={row.PESSOA}>
                        {row.PESSOA}
                      </td>
                      <td className="py-2 pr-4 max-w-[160px] truncate text-gray-500 dark:text-gray-400 text-xs" title={row.CONTA ?? ''}>
                        {row.CONTA || '—'}
                      </td>
                      <td className="py-2 pr-4 text-right font-semibold text-gray-800 dark:text-gray-100 text-xs whitespace-nowrap">
                        {FMT_BRL(row.VALOR ?? 0)}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.DATAVENCIMENTO ? row.DATAVENCIMENTO.slice(0, 10) : '—'}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.DATALIQUIDACAO ? row.DATALIQUIDACAO.slice(0, 10) : '—'}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400">
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
                  value={FMT_BRL(forecast.total_2025 ?? 0)}
                  accentColor="green"
                  subtitle="ano encerrado"
                  comparison={[]}
                />
                <KPICard
                  title="2026 Real (YTD)"
                  value={FMT_BRL(forecast.total_2026_real ?? 0)}
                  accentColor="blue"
                  subtitle="meses realizados"
                  comparison={[
                    {
                      label: 'vs. 2025 mesmo período',
                      value: forecast.total_2025
                        ? `${(((forecast.total_2026_real ?? 0) / (forecast.total_2025 / 12 * ((new Date().getMonth()) || 1))) - 1 * 100).toFixed(1)}%`
                        : null,
                    },
                  ]}
                />
                <KPICard
                  title="Projeção Dez/2026"
                  value={FMT_BRL(forecast.total_2026_projecao ?? 0)}
                  accentColor="violet"
                  subtitle="estimativa restante"
                  comparison={[{ label: 'Modelo', value: forecast.modelo ?? null }]}
                />
                <KPICard
                  title="Estimado Ano 2026"
                  value={FMT_BRL(forecast.total_2026_estimado ?? 0)}
                  accentColor="teal"
                  subtitle="real + projeção"
                  comparison={[
                    {
                      label: 'vs. 2025 total',
                      value: forecast.total_2025
                        ? `${(((forecast.total_2026_estimado ?? 0) / forecast.total_2025 - 1) * 100).toFixed(1)}%`
                        : null,
                      positive: forecast.total_2025
                        ? (forecast.total_2026_estimado ?? 0) < forecast.total_2025
                        : null,
                    },
                  ]}
                />
              </div>

              {/* Forecast Chart — novo componente com ComposedChart */}
              <ForecastChart
                data={forecastMapped}
                todayLabel={shortMonth(currentMonth)}
              />

              {/* 2025 vs 2026 grouped bar — only render if showLY has data */}
              {yoyChartData.length > 0 && (
                <ChartCard title="Comparativo 2025 vs 2026 por Mês">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={yoyChartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} vertical={false} />
                      <XAxis dataKey="mes" tick={{ fontSize: 11, fill: chartTick }} axisLine={{ stroke: chartGrid }} tickLine={false} />
                      <YAxis tickFormatter={FMT_COMPACT} tick={{ fontSize: 10, fill: chartTick }} axisLine={false} tickLine={false} width={65} />
                      <Tooltip
                        formatter={(v: number) => [FMT_BRL(v)]}
                        contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12, color: tooltipText }}
                        itemStyle={{ color: tooltipText }}
                        cursor={{ fill: '#1f2937' }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11, color: chartTick, paddingTop: 8 }} />
                      <Bar dataKey={String(year - 1)} fill={COLOR_2025} radius={[3, 3, 0, 0]} maxBarSize={28} />
                      <Bar dataKey={String(year)} fill={COLOR_2026} radius={[3, 3, 0, 0]} maxBarSize={28} />
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
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60">
                        {[...forecast.by_fornecedor]
                          .sort((a, b) => b.total_estimado_ano - a.total_estimado_ano)
                          .map((f, i) => (
                            <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                              <td className="py-2 pr-4 max-w-[200px] truncate text-gray-800 dark:text-gray-100 font-medium" title={f.pessoa}>
                                {f.pessoa}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                {FMT_BRL(f.valor_executado)}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-500 dark:text-gray-400 whitespace-nowrap">
                                {FMT_BRL(f.media_mensal)}
                              </td>
                              <td className="py-2 pr-4 text-center text-gray-500 dark:text-gray-400">
                                {f.meses_restantes}
                              </td>
                              <td className="py-2 pr-4 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                {FMT_BRL(f.valor_projetado_restante)}
                              </td>
                              <td className="py-2 pr-4 text-right font-semibold text-gray-900 dark:text-white whitespace-nowrap">
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
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 p-4 flex items-start gap-3">
                <span className="text-gray-400 text-lg mt-0.5">ℹ</span>
                <div>
                  <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">Metodologia de Projeção</p>
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

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB: COMPARAÇÃO                                                     */}
      {/* ════════════════════════════════════════════════════════════════════ */}

      {activeTab === 'comparacao' && (
        <div className="space-y-6">
          {loading && !data ? (
            <SkeletonGrid />
          ) : data ? (
            Object.keys(data.yoy_mensal ?? {}).length === 0 && year < 2026 ? (
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-12 text-center">
                <p className="text-4xl mb-3">📊</p>
                <p className="text-gray-600 dark:text-gray-400 font-medium">
                  Selecione o ano 2026 para ver a comparação com 2025
                </p>
              </div>
            ) : (
              <ComparisonTab
                byOrigemMensal={data.by_origem_mensal}
                yoyMensal={data.yoy_mensal ?? {}}
                currentYear={year}
                fmtBrl={FMT_BRL}
                fmtCompact={FMT_COMPACT}
                chartGrid={chartGrid}
                chartTick={chartTick}
              />
            )
          ) : null}
        </div>
      )}
    </div>
  )
}
