import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { apiFetch } from '../../lib/api'
import type {
  BennerContract,
  Contract,
  ContractOccurrence,
  ContractPayment,
  ContractStatus,
  DivergenceResult,
  GovernanceDashboard,
} from '../../types/governance'

// ── Formatters ─────────────────────────────────────────────────────────────────

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

const FMT_DATE = (s: string | null | undefined) => {
  if (!s) return '—'
  try {
    return new Intl.DateTimeFormat('pt-BR').format(new Date(s + 'T00:00:00'))
  } catch {
    return s
  }
}

const DIAS_BADGE = (dias: number | undefined) => {
  if (dias === undefined || dias === null) return null
  if (dias < 0) return <span className="badge-red">Vencido</span>
  if (dias <= 30) return <span className="badge-red">{dias}d</span>
  if (dias <= 60) return <span className="badge-amber">{dias}d</span>
  if (dias <= 90) return <span className="badge-yellow">{dias}d</span>
  return <span className="badge-green">{dias}d</span>
}

// ── Tab type ───────────────────────────────────────────────────────────────────

type GovernanceTab = 'overview' | 'acompanhamento' | 'contratos'

// ── Status badge ───────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<ContractStatus, string> = {
  vigente:    'Vigente',
  vencendo:   'Vencendo',
  vencido:    'Vencido',
  rescindido: 'Rescindido',
  suspenso:   'Suspenso',
}

const STATUS_CLASS: Record<ContractStatus, string> = {
  vigente:    'badge-green',
  vencendo:   'badge-amber',
  vencido:    'badge-red',
  rescindido: 'badge-gray',
  suspenso:   'badge-yellow',
}

function StatusBadge({ status }: { status: ContractStatus }) {
  return <span className={STATUS_CLASS[status]}>{STATUS_LABELS[status]}</span>
}

const DIVERGENCE_CLASS: Record<string, string> = {
  ok:       'text-green-600 dark:text-green-400',
  a_maior:  'text-red-600 dark:text-red-400',
  a_menor:  'text-amber-600 dark:text-amber-400',
  nao_pago: 'text-red-600 dark:text-red-400',
  extra:    'text-purple-600 dark:text-purple-400',
}

const DIVERGENCE_LABELS: Record<string, string> = {
  ok:       '✓ OK',
  a_maior:  '▲ Maior',
  a_menor:  '▼ Menor',
  nao_pago: '✗ Não pago',
  extra:    '+ Extra',
}

// ── KPI Card ───────────────────────────────────────────────────────────────────

function KPICard({
  label, value, sub, accent,
}: {
  label: string; value: string | number; sub?: string; accent?: string
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`mt-1.5 text-2xl font-bold ${accent ?? 'text-gray-900 dark:text-white'}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  )
}

// ── Tab 1: Visão Geral ─────────────────────────────────────────────────────────

function OverviewTab({
  dashboard,
  onSelectContract,
}: {
  dashboard: GovernanceDashboard
  onSelectContract: (id: string) => void
}) {
  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Contratos Vigentes" value={dashboard.contratos_vigentes} />
        <KPICard
          label="Vencendo em 30d"
          value={dashboard.vencendo_30d}
          accent={dashboard.vencendo_30d > 0 ? 'text-red-600 dark:text-red-400' : undefined}
          sub={dashboard.vencendo_60d > 0 ? `${dashboard.vencendo_60d} em 60d` : undefined}
        />
        <KPICard
          label="Ocorrências Pendentes"
          value={dashboard.ocorrencias_pendentes}
          accent={dashboard.ocorrencias_pendentes > 0 ? 'text-amber-600 dark:text-amber-400' : undefined}
          sub={dashboard.valor_glosas_pendentes > 0 ? FMT_BRL(dashboard.valor_glosas_pendentes) : undefined}
        />
        <KPICard
          label="Valor Total Contratos"
          value={FMT_BRL(dashboard.valor_total_contratos)}
          sub={`${dashboard.total_contratos} contrato${dashboard.total_contratos !== 1 ? 's' : ''}`}
        />
      </div>

      {/* Alertas — contratos vencendo */}
      {dashboard.contracts.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Contratos Urgentes</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="px-5 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Contrato</th>
                  <th className="px-5 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Fornecedor</th>
                  <th className="px-5 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-5 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Vence em</th>
                  <th className="px-5 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Valor Mensal</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {dashboard.contracts.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-gray-100">
                      {c.numero ? `${c.numero} — ` : ''}{c.titulo}
                    </td>
                    <td className="px-5 py-3 text-gray-600 dark:text-gray-400">{c.fornecedor_nome}</td>
                    <td className="px-5 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-5 py-3">{DIAS_BADGE(c.dias_para_vencer)}</td>
                    <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">
                      {c.valor_mensal ? FMT_BRL(c.valor_mensal) : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => onSelectContract(c.id)}
                        className="text-xs text-brand-green hover:underline"
                      >
                        Ver →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {dashboard.last_updated && (
            <p className="px-5 py-2 text-[11px] text-gray-400 border-t border-gray-100 dark:border-gray-800">
              Atualizado: {new Date(dashboard.last_updated).toLocaleString('pt-BR')}
            </p>
          )}
        </div>
      )}

      {dashboard.contracts.length === 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-12 text-center">
          <p className="text-sm text-gray-400">Nenhum contrato cadastrado.</p>
          <p className="mt-1 text-xs text-gray-400">Acesse a aba "Contratos" para cadastrar o primeiro.</p>
        </div>
      )}
    </div>
  )
}

// ── Tab 2: Acompanhamento ──────────────────────────────────────────────────────

function AcompanhamentoTab({
  contracts,
  token,
}: {
  contracts: Contract[]
  token: string | null
}) {
  const [selectedId, setSelectedId] = useState<string>('')
  const [payments, setPayments] = useState<ContractPayment[]>([])
  const [divergences, setDivergences] = useState<DivergenceResult | null>(null)
  const [occurrences, setOccurrences] = useState<ContractOccurrence[]>([])
  const [loading, setLoading] = useState(false)

  const selected = contracts.find((c) => c.id === selectedId)

  const load = useCallback(
    async (id: string) => {
      if (!id) return
      setLoading(true)
      try {
        const [p, d, o] = await Promise.all([
          apiFetch<ContractPayment[]>(`/api/expenses/governance/contracts/${id}/payments`, { token }),
          apiFetch<DivergenceResult>(`/api/expenses/governance/contracts/${id}/divergences`, { token }),
          apiFetch<ContractOccurrence[]>(`/api/expenses/governance/contracts/${id}/occurrences`, { token }),
        ])
        setPayments(p)
        setDivergences(d)
        setOccurrences(o)
      } catch {
        // errors shown inline
      } finally {
        setLoading(false)
      }
    },
    [token],
  )

  useEffect(() => {
    if (selectedId) load(selectedId)
  }, [selectedId, load])

  return (
    <div className="space-y-5">
      {/* Seletor */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300 shrink-0">Contrato:</label>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="flex-1 max-w-md rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green/40"
        >
          <option value="">Selecione um contrato…</option>
          {contracts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.numero ? `${c.numero} — ` : ''}{c.titulo} ({c.fornecedor_nome})
            </option>
          ))}
        </select>
      </div>

      {!selectedId && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-12 text-center">
          <p className="text-sm text-gray-400">Selecione um contrato para visualizar o acompanhamento.</p>
        </div>
      )}

      {selectedId && selected && (
        <>
          {/* Header do contrato */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <div className="flex flex-wrap items-start gap-3 justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                  {selected.numero ? `${selected.numero} — ` : ''}{selected.titulo}
                </h3>
                <p className="text-sm text-gray-500 mt-0.5">{selected.fornecedor_nome}</p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge status={selected.status} />
                {DIAS_BADGE(selected.dias_para_vencer)}
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-gray-400 text-xs uppercase tracking-wide">Valor mensal</p>
                <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                  {selected.valor_mensal ? FMT_BRL(selected.valor_mensal) : '—'}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase tracking-wide">Valor total</p>
                <p className="font-semibold text-gray-900 dark:text-white mt-0.5">{FMT_BRL(selected.valor_total)}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase tracking-wide">Início</p>
                <p className="font-semibold text-gray-900 dark:text-white mt-0.5">{FMT_DATE(selected.data_inicio)}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase tracking-wide">Fim</p>
                <p className="font-semibold text-gray-900 dark:text-white mt-0.5">{FMT_DATE(selected.data_fim)}</p>
              </div>
            </div>
          </div>

          {loading && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 text-center">
              <p className="text-sm text-gray-400 animate-pulse">Carregando dados do Benner…</p>
            </div>
          )}

          {!loading && divergences && (
            <>
              {/* Resumo de divergência */}
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Total Previsto</p>
                  <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{FMT_BRL(divergences.total_previsto)}</p>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Total Pago (Benner)</p>
                  <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{FMT_BRL(divergences.total_pago)}</p>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Delta</p>
                  <p className={`mt-1 text-lg font-bold ${divergences.delta_total === 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {divergences.delta_total >= 0 ? '+' : ''}{FMT_BRL(divergences.delta_total)}
                  </p>
                </div>
              </div>

              {/* Timeline de parcelas */}
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Confronto Mês a Mês</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                        <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Mês</th>
                        <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Previsto</th>
                        <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Pago</th>
                        <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Delta</th>
                        <th className="px-4 py-2.5 text-center text-[11px] font-medium text-gray-500 uppercase">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                      {divergences.divergencias.map((d) => (
                        <tr
                          key={d.mes}
                          className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${d.tipo !== 'ok' ? 'bg-red-50/30 dark:bg-red-900/5' : ''}`}
                        >
                          <td className="px-4 py-2.5 font-medium text-gray-700 dark:text-gray-300">{d.mes}</td>
                          <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{FMT_BRL(d.previsto)}</td>
                          <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{FMT_BRL(d.pago)}</td>
                          <td className="px-4 py-2.5 text-right font-semibold">
                            <span className={d.delta === 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                              {d.delta >= 0 ? '+' : ''}{FMT_BRL(d.delta)}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <span className={`text-xs font-medium ${DIVERGENCE_CLASS[d.tipo]}`}>
                              {DIVERGENCE_LABELS[d.tipo]}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Pagamentos Benner */}
          {!loading && payments.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Pagamentos no Benner</h3>
                <span className="text-xs text-gray-400">{payments.length} parcelas</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">AP</th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Mês</th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Vencimento</th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Liquidação</th>
                      <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Valor</th>
                      <th className="px-4 py-2.5 text-center text-[11px] font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Filial</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                    {payments.map((p) => (
                      <tr key={p.ap} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{p.ap}</td>
                        <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">{p.mes}</td>
                        <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{FMT_DATE(p.datavencimento)}</td>
                        <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{FMT_DATE(p.dataliquidacao)}</td>
                        <td className="px-4 py-2.5 text-right font-medium text-gray-900 dark:text-white">{FMT_BRL(p.valor)}</td>
                        <td className="px-4 py-2.5 text-center">
                          {p.status_par === 'pago'
                            ? <span className="badge-green">Pago</span>
                            : <span className="badge-amber">Pendente</span>}
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 text-xs">{p.filial}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Ocorrências vinculadas */}
          {!loading && occurrences.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Ocorrências</h3>
              </div>
              <div className="divide-y divide-gray-50 dark:divide-gray-800">
                {occurrences.map((o) => (
                  <div key={o.id} className="px-5 py-3 flex items-start gap-3">
                    <span className={`mt-0.5 text-xs font-semibold uppercase px-2 py-0.5 rounded-full ${
                      o.tipo === 'glosa' || o.tipo === 'multa' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                      o.tipo === 'desconto' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                      'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                    }`}>
                      {o.tipo}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700 dark:text-gray-300">{o.descricao}</p>
                      {o.competencia && <p className="text-xs text-gray-400 mt-0.5">Competência: {o.competencia}</p>}
                    </div>
                    {o.valor != null && (
                      <span className={`text-sm font-semibold shrink-0 ${o.valor < 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                        {FMT_BRL(o.valor)}
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                      o.status === 'pendente' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                      o.status === 'aplicado' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                      'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                    }`}>
                      {o.status}
                    </span>
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

// ── Tab 3: Contratos ───────────────────────────────────────────────────────────

function ContratosTab({
  contracts,
  token,
  onRefresh,
}: {
  contracts: Contract[]
  token: string | null
  onRefresh: () => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [showDiscover, setShowDiscover] = useState(false)
  const [bennerList, setBennerList] = useState<BennerContract[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [saving, setSaving] = useState(false)
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [form, setForm] = useState({
    titulo: '',
    fornecedor_nome: '',
    valor_total: '',
    valor_mensal: '',
    qtd_parcelas: '',
    data_inicio: '',
    data_fim: '',
    modalidade: 'servico',
    status: 'vigente',
    numero: '',
    objeto: '',
    benner_documento_match: '',
    fornecedor_benner_handle: '',
    observacoes: '',
  })

  const filteredContracts = filterStatus
    ? contracts.filter((c) => c.status === filterStatus)
    : contracts

  async function handleDiscover() {
    setDiscovering(true)
    try {
      const list = await apiFetch<BennerContract[]>('/api/expenses/governance/discover', { token })
      setBennerList(list)
      setShowDiscover(true)
    } catch (e: any) {
      alert(`Erro ao consultar Benner: ${e.message}`)
    } finally {
      setDiscovering(false)
    }
  }

  function prefillFromBenner(b: BennerContract) {
    setForm((f) => ({
      ...f,
      fornecedor_nome: b.fornecedor,
      benner_documento_match: b.num_contrato ?? '',
      fornecedor_benner_handle: String(b.fornecedor_handle ?? ''),
      valor_total: String(b.total_valor ?? ''),
      numero: b.num_contrato ?? '',
    }))
    setShowDiscover(false)
    setShowForm(true)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: Record<string, any> = {
        titulo: form.titulo,
        fornecedor_nome: form.fornecedor_nome,
        valor_total: parseFloat(form.valor_total),
        data_inicio: form.data_inicio,
        data_fim: form.data_fim,
        modalidade: form.modalidade,
        status: form.status,
      }
      if (form.numero) payload.numero = form.numero
      if (form.objeto) payload.objeto = form.objeto
      if (form.observacoes) payload.observacoes = form.observacoes
      if (form.benner_documento_match) payload.benner_documento_match = form.benner_documento_match
      if (form.fornecedor_benner_handle) payload.fornecedor_benner_handle = parseInt(form.fornecedor_benner_handle)
      if (form.valor_mensal) payload.valor_mensal = parseFloat(form.valor_mensal)
      if (form.qtd_parcelas) payload.qtd_parcelas = parseInt(form.qtd_parcelas)
      await apiFetch('/api/expenses/governance/contracts', { method: 'POST', token, json: payload })
      setShowForm(false)
      setForm({ titulo:'', fornecedor_nome:'', valor_total:'', valor_mensal:'', qtd_parcelas:'', data_inicio:'', data_fim:'', modalidade:'servico', status:'vigente', numero:'', objeto:'', benner_documento_match:'', fornecedor_benner_handle:'', observacoes:'' })
      onRefresh()
    } catch (err: any) {
      alert(`Erro ao salvar: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-green/40"
        >
          <option value="">Todos os status</option>
          <option value="vigente">Vigente</option>
          <option value="vencendo">Vencendo</option>
          <option value="vencido">Vencido</option>
          <option value="rescindido">Rescindido</option>
          <option value="suspenso">Suspenso</option>
        </select>
        <div className="flex-1" />
        <button
          onClick={handleDiscover}
          disabled={discovering}
          className="btn-secondary text-sm"
        >
          {discovering ? 'Consultando…' : 'Importar do Benner'}
        </button>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="btn-primary text-sm"
        >
          {showForm ? 'Cancelar' : '+ Novo Contrato'}
        </button>
      </div>

      {/* Benner discovery list */}
      {showDiscover && bennerList.length > 0 && (
        <div className="rounded-xl border border-brand-green/30 bg-white dark:bg-gray-900 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Contratos encontrados no Benner ({bennerList.length})
            </h3>
            <button onClick={() => setShowDiscover(false)} className="text-gray-400 hover:text-gray-600 text-xs">Fechar</button>
          </div>
          <div className="max-h-72 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-800">
            {bennerList.map((b) => (
              <div key={b.benner_handle} className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{b.fornecedor}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {b.num_contrato ?? `Handle ${b.benner_handle}`} · {b.qtd_parcelas} parcelas · {FMT_BRL(b.total_valor)}
                  </p>
                </div>
                <button
                  onClick={() => prefillFromBenner(b)}
                  className="text-xs text-brand-green hover:underline shrink-0"
                >
                  Usar este →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Novo contrato form */}
      {showForm && (
        <form
          onSubmit={handleSave}
          className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 space-y-4"
        >
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 pb-2 border-b border-gray-100 dark:border-gray-800">
            Novo Contrato
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="form-label">Título *</label>
              <input required value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}
                className="form-input" placeholder="Ex: Suporte Microsoft 365" />
            </div>
            <div>
              <label className="form-label">Número do contrato</label>
              <input value={form.numero} onChange={e => setForm(f => ({ ...f, numero: e.target.value }))}
                className="form-input" placeholder="Ex: CME/2024-001" />
            </div>
            <div>
              <label className="form-label">Fornecedor *</label>
              <input required value={form.fornecedor_nome} onChange={e => setForm(f => ({ ...f, fornecedor_nome: e.target.value }))}
                className="form-input" placeholder="Nome do fornecedor" />
            </div>
            <div>
              <label className="form-label">Modalidade</label>
              <select value={form.modalidade} onChange={e => setForm(f => ({ ...f, modalidade: e.target.value }))}
                className="form-input">
                <option value="servico">Serviço</option>
                <option value="fornecimento">Fornecimento</option>
                <option value="manutencao">Manutenção</option>
                <option value="licenca">Licença</option>
                <option value="outro">Outro</option>
              </select>
            </div>
            <div>
              <label className="form-label">Status</label>
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="form-input">
                <option value="vigente">Vigente</option>
                <option value="vencendo">Vencendo</option>
                <option value="vencido">Vencido</option>
                <option value="rescindido">Rescindido</option>
                <option value="suspenso">Suspenso</option>
              </select>
            </div>
            <div>
              <label className="form-label">Data início *</label>
              <input required type="date" value={form.data_inicio} onChange={e => setForm(f => ({ ...f, data_inicio: e.target.value }))}
                className="form-input" />
            </div>
            <div>
              <label className="form-label">Data fim *</label>
              <input required type="date" value={form.data_fim} onChange={e => setForm(f => ({ ...f, data_fim: e.target.value }))}
                className="form-input" />
            </div>
            <div>
              <label className="form-label">Valor total (R$) *</label>
              <input required type="number" step="0.01" value={form.valor_total} onChange={e => setForm(f => ({ ...f, valor_total: e.target.value }))}
                className="form-input" placeholder="0,00" />
            </div>
            <div>
              <label className="form-label">Valor mensal (R$)</label>
              <input type="number" step="0.01" value={form.valor_mensal} onChange={e => setForm(f => ({ ...f, valor_mensal: e.target.value }))}
                className="form-input" placeholder="0,00" />
            </div>
            <div>
              <label className="form-label">Qtd. parcelas</label>
              <input type="number" value={form.qtd_parcelas} onChange={e => setForm(f => ({ ...f, qtd_parcelas: e.target.value }))}
                className="form-input" placeholder="12" />
            </div>
            <div>
              <label className="form-label">Handle Benner (fornecedor)</label>
              <input type="number" value={form.fornecedor_benner_handle} onChange={e => setForm(f => ({ ...f, fornecedor_benner_handle: e.target.value }))}
                className="form-input" placeholder="Handle GN_PESSOAS" />
            </div>
            <div>
              <label className="form-label">Match DOCUMENTODIGITADO (Benner)</label>
              <input value={form.benner_documento_match} onChange={e => setForm(f => ({ ...f, benner_documento_match: e.target.value }))}
                className="form-input" placeholder="Ex: CME/2024-001" />
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="form-label">Objeto</label>
              <textarea value={form.objeto} onChange={e => setForm(f => ({ ...f, objeto: e.target.value }))}
                className="form-input resize-none" rows={2} placeholder="Descrição do objeto contratado" />
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="form-label">Observações</label>
              <textarea value={form.observacoes} onChange={e => setForm(f => ({ ...f, observacoes: e.target.value }))}
                className="form-input resize-none" rows={2} />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving} className="btn-primary text-sm">
              {saving ? 'Salvando…' : 'Salvar Contrato'}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">
              Cancelar
            </button>
          </div>
        </form>
      )}

      {/* Lista de contratos */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
        {filteredContracts.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-sm text-gray-400">Nenhum contrato encontrado.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                  <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase">Contrato</th>
                  <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase">Fornecedor</th>
                  <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase">Modalidade</th>
                  <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase">Vence em</th>
                  <th className="px-5 py-3 text-right text-[11px] font-medium text-gray-500 uppercase">Mensal</th>
                  <th className="px-5 py-3 text-right text-[11px] font-medium text-gray-500 uppercase">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {filteredContracts.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <td className="px-5 py-3">
                      <p className="font-medium text-gray-900 dark:text-white">{c.titulo}</p>
                      {c.numero && <p className="text-xs text-gray-400 mt-0.5">{c.numero}</p>}
                    </td>
                    <td className="px-5 py-3 text-gray-600 dark:text-gray-400">{c.fornecedor_nome}</td>
                    <td className="px-5 py-3 text-gray-500 capitalize">{c.modalidade}</td>
                    <td className="px-5 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{FMT_DATE(c.data_fim)}</span>
                        {DIAS_BADGE(c.dias_para_vencer)}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">
                      {c.valor_mensal ? FMT_BRL(c.valor_mensal) : '—'}
                    </td>
                    <td className="px-5 py-3 text-right font-medium text-gray-900 dark:text-white">
                      {FMT_BRL(c.valor_total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function GovernancePage() {
  const { token } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const activeTab = (searchParams.get('tab') as GovernanceTab) ?? 'overview'

  function setTab(t: GovernanceTab) {
    navigate(`/admin/governanca?tab=${t}`, { replace: true })
  }

  const [dashboard, setDashboard] = useState<GovernanceDashboard | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    try {
      setError(null)
      const [dash, clist] = await Promise.all([
        apiFetch<GovernanceDashboard>('/api/expenses/governance/dashboard', { token }),
        apiFetch<Contract[]>('/api/expenses/governance/contracts', { token }),
      ])
      setDashboard(dash)
      setContracts(clist)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { loadAll() }, [loadAll])

  function handleSelectContract(id: string) {
    navigate(`/admin/governanca?tab=acompanhamento&contract=${id}`, { replace: true })
  }

  const TABS: { id: GovernanceTab; label: string }[] = [
    { id: 'overview',       label: 'Visão Geral' },
    { id: 'acompanhamento', label: 'Acompanhamento' },
    { id: 'contratos',      label: 'Contratos' },
  ]

  return (
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">Governança de Contratos</h1>
          <p className="text-sm text-gray-500 mt-0.5">Gestão contratual de TI — confronto Benner vs contratos cadastrados</p>
        </div>
        <button onClick={loadAll} className="btn-secondary text-sm shrink-0">Atualizar</button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800">
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
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

      {/* Content */}
      {loading ? (
        <div className="py-20 text-center">
          <p className="text-sm text-gray-400 animate-pulse">Carregando governança…</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 p-5">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          <button onClick={loadAll} className="mt-3 text-xs text-red-600 dark:text-red-400 hover:underline">Tentar novamente</button>
        </div>
      ) : (
        <>
          {activeTab === 'overview' && dashboard && (
            <OverviewTab dashboard={dashboard} onSelectContract={handleSelectContract} />
          )}
          {activeTab === 'acompanhamento' && (
            <AcompanhamentoTab contracts={contracts} token={token} />
          )}
          {activeTab === 'contratos' && (
            <ContratosTab contracts={contracts} token={token} onRefresh={loadAll} />
          )}
        </>
      )}
    </div>
  )
}
