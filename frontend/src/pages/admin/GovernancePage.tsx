import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { apiFetch } from '../../lib/api'
import type {
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

type AdherenceResult = {
  status: string
  total_executado: number
  total_pago: number
  a_pagar: number
  novas_ocorrencias: number
  divergencias: { mes: string; previsto: number; pago: number; delta: number; tipo: string }[]
}

function OccurrenceBadge({ tipo }: { tipo: string }) {
  const cls =
    tipo.startsWith('divergencia_valor_maior') ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
    tipo.startsWith('divergencia_valor_menor') ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
    tipo === 'glosa' || tipo === 'multa'        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
    tipo === 'desconto'                         ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
    'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
  const label =
    tipo === 'divergencia_valor_maior' ? '▲ Valor Maior' :
    tipo === 'divergencia_valor_menor' ? '▼ Valor Menor' :
    tipo
  return <span className={`mt-0.5 text-xs font-semibold uppercase px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
}

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
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<AdherenceResult | null>(null)

  const selected = contracts.find((c) => c.id === selectedId)

  const totalExecutado = payments.reduce((s, p) => s + (p.valor ?? 0), 0)
  const totalPago      = payments.filter((p) => p.status_par === 'pago').reduce((s, p) => s + (p.valor ?? 0), 0)
  const aPagar         = Math.max(0, (selected?.valor_total ?? 0) - totalPago)

  const load = useCallback(
    async (id: string) => {
      if (!id) return
      setLoading(true)
      setCheckResult(null)
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

  async function handleCheckAdherence() {
    if (!selectedId) return
    setChecking(true)
    try {
      const result = await apiFetch<AdherenceResult>(
        `/api/expenses/governance/contracts/${selectedId}/check-adherence`,
        { method: 'POST', token },
      )
      setCheckResult(result)
      // Reload occurrences in case new ones were created
      const o = await apiFetch<ContractOccurrence[]>(
        `/api/expenses/governance/contracts/${selectedId}/occurrences`, { token }
      )
      setOccurrences(o)
    } catch (e: any) {
      alert(`Erro ao verificar aderência: ${e.message}`)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Seletor */}
      <div className="flex items-center gap-3 flex-wrap">
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
        {selectedId && (
          <button
            onClick={handleCheckAdherence}
            disabled={checking || loading}
            className="btn-primary text-sm shrink-0"
          >
            {checking ? 'Verificando…' : 'Verificar Aderência'}
          </button>
        )}
      </div>

      {/* Resultado da verificação de aderência */}
      {checkResult && (
        <div className={`rounded-xl border p-4 ${
          checkResult.status === 'ok'
            ? 'border-green-200 dark:border-green-900/50 bg-green-50 dark:bg-green-900/10'
            : 'border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10'
        }`}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <p className={`text-sm font-semibold ${checkResult.status === 'ok' ? 'text-green-700 dark:text-green-400' : 'text-amber-700 dark:text-amber-400'}`}>
              {checkResult.status === 'ok' ? '✓ Aderente ao contrato' : '⚠ Divergências encontradas'}
            </p>
            {checkResult.novas_ocorrencias > 0 && (
              <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
                {checkResult.novas_ocorrencias} nova{checkResult.novas_ocorrencias > 1 ? 's ocorrência registrada(s)' : ' ocorrência registrada'}
              </span>
            )}
            <button onClick={() => setCheckResult(null)} className="text-xs text-gray-400 hover:text-gray-600">Fechar</button>
          </div>
        </div>
      )}

      {!selectedId && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-12 text-center">
          <p className="text-sm text-gray-400">Selecione um contrato para visualizar o acompanhamento.</p>
        </div>
      )}

      {selectedId && selected && (
        <>
          {/* Cruzamento cadastral: Jarvis × Benner */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Cruzamento Cadastral</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-gray-100 dark:divide-gray-800">
              {/* Jarvis */}
              <div className="px-5 py-4 space-y-2">
                <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3">Cadastro Jarvis</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <div><p className="text-gray-400 text-xs">Título</p><p className="font-medium text-gray-900 dark:text-white">{selected.titulo}</p></div>
                  <div><p className="text-gray-400 text-xs">Nº Contrato</p><p className="font-medium text-gray-900 dark:text-white">{selected.numero || '—'}</p></div>
                  <div><p className="text-gray-400 text-xs">Fornecedor</p><p className="font-medium text-gray-900 dark:text-white">{selected.fornecedor_nome}</p></div>
                  <div><p className="text-gray-400 text-xs">Modalidade</p><p className="font-medium text-gray-900 dark:text-white capitalize">{selected.modalidade}</p></div>
                  <div><p className="text-gray-400 text-xs">Início</p><p className="font-medium text-gray-900 dark:text-white">{FMT_DATE(selected.data_inicio)}</p></div>
                  <div><p className="text-gray-400 text-xs">Fim</p><p className="font-medium text-gray-900 dark:text-white">{FMT_DATE(selected.data_fim)}</p></div>
                  <div><p className="text-gray-400 text-xs">Valor Mensal</p><p className="font-semibold text-gray-900 dark:text-white">{selected.valor_mensal ? FMT_BRL(selected.valor_mensal) : '—'}</p></div>
                  <div><p className="text-gray-400 text-xs">Valor Total</p><p className="font-semibold text-gray-900 dark:text-white">{FMT_BRL(selected.valor_total)}</p></div>
                </div>
              </div>
              {/* Benner */}
              <div className="px-5 py-4 space-y-2">
                <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3">Vínculo Benner</p>
                {(selected as any).benner_documento_match || (selected as any).fornecedor_benner_handle ? (
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <div>
                      <p className="text-gray-400 text-xs">DOCUMENTODIGITADO</p>
                      <p className="font-medium text-gray-900 dark:text-white font-mono">{(selected as any).benner_documento_match || '—'}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">Handle Fornecedor</p>
                      <p className="font-medium text-gray-900 dark:text-white font-mono">{(selected as any).fornecedor_benner_handle || '—'}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">Parcelas Benner</p>
                      <p className="font-semibold text-gray-900 dark:text-white">{payments.length}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">Última liquidação</p>
                      <p className="font-medium text-gray-900 dark:text-white">
                        {payments.filter(p => p.dataliquidacao).slice(-1)[0]?.dataliquidacao
                          ? FMT_DATE(payments.filter(p => p.dataliquidacao).slice(-1)[0].dataliquidacao)
                          : '—'}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400">Sem vínculo Benner configurado.<br/>
                    <span className="text-xs">Edite o contrato e preencha o Handle ou Nº do documento.</span>
                  </p>
                )}
              </div>
            </div>
          </div>

          {loading && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 text-center">
              <p className="text-sm text-gray-400 animate-pulse">Carregando dados do Benner…</p>
            </div>
          )}

          {!loading && payments.length > 0 && (
            <>
              {/* Cards financeiros */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Valor Contratado</p>
                  <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{FMT_BRL(selected.valor_total)}</p>
                  {selected.valor_mensal && <p className="text-xs text-gray-400 mt-1">{FMT_BRL(selected.valor_mensal)}/mês</p>}
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Total Executado</p>
                  <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{FMT_BRL(totalExecutado)}</p>
                  <p className="text-xs text-gray-400 mt-1">{payments.length} AP{payments.length > 1 ? 's' : ''} no Benner</p>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Total Pago</p>
                  <p className="mt-1 text-lg font-bold text-green-600 dark:text-green-400">{FMT_BRL(totalPago)}</p>
                  <p className="text-xs text-gray-400 mt-1">{payments.filter(p => p.status_par === 'pago').length} liquidados</p>
                </div>
                <div className={`rounded-xl border p-4 ${aPagar > 0 ? 'border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-900/10' : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900'}`}>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">A Pagar</p>
                  <p className={`mt-1 text-lg font-bold ${aPagar > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}`}>
                    {FMT_BRL(aPagar)}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{payments.filter(p => p.status_par !== 'pago').length} pendentes</p>
                </div>
              </div>
            </>
          )}

          {!loading && divergences && divergences.divergencias.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Confronto Mês a Mês — Aderência ao Contrato</h3>
                <div className="flex gap-3 text-xs text-gray-400">
                  <span className="text-green-600 dark:text-green-400 font-medium">
                    {divergences.divergencias.filter(d => d.tipo === 'ok').length} ok
                  </span>
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    {divergences.divergencias.filter(d => d.tipo === 'a_maior').length} ▲ maior
                  </span>
                  <span className="text-amber-600 dark:text-amber-400 font-medium">
                    {divergences.divergencias.filter(d => d.tipo === 'a_menor' || d.tipo === 'nao_pago').length} ▼ menor/np
                  </span>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                      <th className="px-4 py-2.5 text-left text-[11px] font-medium text-gray-500 uppercase">Mês</th>
                      <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Contratado</th>
                      <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Executado</th>
                      <th className="px-4 py-2.5 text-right text-[11px] font-medium text-gray-500 uppercase">Diferença</th>
                      <th className="px-4 py-2.5 text-center text-[11px] font-medium text-gray-500 uppercase">Aderência</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                    {divergences.divergencias.map((d) => (
                      <tr
                        key={d.mes}
                        className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${
                          d.tipo === 'a_maior' ? 'bg-red-50/40 dark:bg-red-900/5' :
                          d.tipo === 'a_menor' || d.tipo === 'nao_pago' ? 'bg-amber-50/40 dark:bg-amber-900/5' : ''
                        }`}
                      >
                        <td className="px-4 py-2.5 font-medium text-gray-700 dark:text-gray-300">{d.mes}</td>
                        <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{FMT_BRL(d.previsto)}</td>
                        <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{FMT_BRL(d.pago)}</td>
                        <td className="px-4 py-2.5 text-right font-semibold">
                          <span className={
                            d.delta === 0 ? 'text-green-600 dark:text-green-400' :
                            d.delta > 0   ? 'text-red-600 dark:text-red-400' :
                            'text-amber-600 dark:text-amber-400'
                          }>
                            {d.delta >= 0 ? '+' : ''}{FMT_BRL(d.delta)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <span className={`text-xs font-semibold ${DIVERGENCE_CLASS[d.tipo]}`}>
                            {DIVERGENCE_LABELS[d.tipo]}
                          </span>
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t-2 border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 font-semibold">
                      <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">Total</td>
                      <td className="px-4 py-2.5 text-right text-gray-700 dark:text-gray-300">{FMT_BRL(divergences.total_previsto)}</td>
                      <td className="px-4 py-2.5 text-right text-gray-700 dark:text-gray-300">{FMT_BRL(divergences.total_pago)}</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className={divergences.delta_total === 0 ? 'text-green-600 dark:text-green-400' : divergences.delta_total > 0 ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}>
                          {divergences.delta_total >= 0 ? '+' : ''}{FMT_BRL(divergences.delta_total)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-xs font-bold ${divergences.status === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {divergences.status === 'ok' ? '✓ Aderente' : '⚠ Divergente'}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Pagamentos Benner */}
          {!loading && payments.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Parcelas no Benner</h3>
                <span className="text-xs text-gray-400">{payments.length} AP{payments.length > 1 ? 's' : ''}</span>
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
                        <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{p.dataliquidacao ? FMT_DATE(p.dataliquidacao) : <span className="text-amber-500">—</span>}</td>
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
              <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Ocorrências</h3>
                <span className="text-xs text-gray-400">{occurrences.filter(o => o.status === 'pendente').length} pendentes</span>
              </div>
              <div className="divide-y divide-gray-50 dark:divide-gray-800">
                {occurrences.map((o) => (
                  <div key={o.id} className="px-5 py-3 flex items-start gap-3">
                    <OccurrenceBadge tipo={o.tipo} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700 dark:text-gray-300">{o.descricao}</p>
                      {o.competencia && <p className="text-xs text-gray-400 mt-0.5">Competência: {o.competencia}</p>}
                    </div>
                    {o.valor != null && (
                      <span className={`text-sm font-semibold shrink-0 ${o.valor < 0 ? 'text-red-600 dark:text-red-400' : o.valor > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                        {o.valor >= 0 ? '+' : ''}{FMT_BRL(o.valor)}
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
          onClick={() => setShowForm((v) => !v)}
          className="btn-primary text-sm"
        >
          {showForm ? 'Cancelar' : '+ Novo Contrato'}
        </button>
      </div>

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
