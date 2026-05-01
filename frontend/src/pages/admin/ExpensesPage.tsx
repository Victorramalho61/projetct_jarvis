import { useCallback, useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell,
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useAuth } from "../../context/AuthContext";
import { ApiError, apiFetch } from "../../lib/api";
import type { ExpenseDashboard, ExpenseByCategoria, ExpenseRow } from "../../types/expenses";

const FMT_BRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

const CHART_COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];

function toISO(d: Date) { return d.toISOString().slice(0, 10); }
const today = toISO(new Date());
const ago90 = toISO(new Date(Date.now() - 90 * 86_400_000));

// ── Sub-components ────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, accent }: { label: string; value: string; sub: string; accent: string }) {
  return (
    <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">{label}</p>
      <p className={`mt-2 text-[22px] font-bold leading-none ${accent}`}>{value}</p>
      <p className="mt-1.5 text-xs text-gray-400 dark:text-gray-500">{sub}</p>
    </div>
  );
}

function FilterSelect({ value, onChange, placeholder, options }: {
  value: string; onChange: (v: string) => void; placeholder: string; options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-brand-green/50"
    >
      <option value="">{placeholder}: Todos</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function OrigemBadge({ origem }: { origem: string }) {
  const styles: Record<string, string> = {
    "Contrato":       "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
    "Ordem de Compra":"bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
    "Financeiro":     "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${styles[origem] ?? "bg-gray-100 text-gray-600"}`}>
      {origem}
    </span>
  );
}

function CategoriaBadge({ categoria }: { categoria: string }) {
  const styles: Record<string, string> = {
    "Recorrente": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    "Ocasional":  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    "Pontual":    "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${styles[categoria] ?? "bg-gray-100 text-gray-600"}`}>
      {categoria}
    </span>
  );
}

function TipoBadge({ tipo }: { tipo: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
      tipo === "Efetivo"
        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
        : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
    }`}>
      {tipo}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ExpensesPage() {
  const { token } = useAuth();
  const [data, setData] = useState<ExpenseDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [fromDate, setFromDate] = useState(ago90);
  const [toDate, setToDate] = useState(today);

  const [filterTipo, setFilterTipo] = useState("");
  const [filterOrigem, setFilterOrigem] = useState("");
  const [filterFilial, setFilterFilial] = useState("");
  const [filterCategoria, setFilterCategoria] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<ExpenseDashboard>(
        `/api/expenses/dashboard?from=${fromDate}&to=${toDate}`,
        { token },
      );
      setData(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao carregar dados de gastos.");
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, token]);

  useEffect(() => { load(); }, [load]);

  const uniqueOrigem = [...new Set((data?.rows ?? []).map((r) => r.ORIGEM).filter(Boolean))] as string[];
  const uniqueFilial = [...new Set((data?.rows ?? []).map((r) => r.FILIAL).filter(Boolean))] as string[];

  const filteredRows: ExpenseRow[] = (data?.rows ?? []).filter((r) => {
    if (filterTipo && r.TIPO_DOC !== filterTipo) return false;
    if (filterOrigem && r.ORIGEM !== filterOrigem) return false;
    if (filterFilial && r.FILIAL !== filterFilial) return false;
    if (filterCategoria && r.CATEGORIA !== filterCategoria) return false;
    return true;
  });

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">

      {/* Header + period filter */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Gastos de Tecnologia</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Despesas do departamento de TI (K_GESTOR 23)</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="h-9 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-green/30"
          />
          <span className="text-gray-400 text-sm">até</span>
          <input
            type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="h-9 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-green/30"
          />
          <button
            onClick={load} disabled={loading}
            className="h-9 px-4 rounded-lg bg-brand-green text-white text-sm font-semibold hover:bg-brand-deep disabled:opacity-50 transition-colors"
          >
            {loading ? "Carregando…" : "Aplicar"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Skeleton */}
      {loading && !data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* KPI cards — linha 1: totais */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard label="Total Gasto" value={FMT_BRL(data.kpis.total_valor)} sub={`${data.kpis.count_parcelas} parcelas`} accent="text-emerald-600 dark:text-emerald-400" />
            <KPICard label="Recorrente / Contratual" value={FMT_BRL(data.kpis.total_recorrente)} sub="fornecedores ≥ 3 meses" accent="text-blue-600 dark:text-blue-400" />
            <KPICard label="Pagamento Pontual" value={FMT_BRL(data.kpis.total_pontual)} sub="fornecedor 1 único mês" accent="text-orange-600 dark:text-orange-400" />
            <KPICard label="Média Mensal" value={FMT_BRL(data.kpis.media_mensal)} sub="no período selecionado" accent="text-purple-600 dark:text-purple-400" />
          </div>
          {/* KPI cards — linha 2: efetivo vs previsão */}
          <div className="grid grid-cols-2 gap-4">
            <KPICard label="Efetivo" value={FMT_BRL(data.kpis.total_efetivo)} sub={`${data.kpis.count_efetivo} parcelas confirmadas`} accent="text-emerald-600 dark:text-emerald-400" />
            <KPICard label="Previsão" value={FMT_BRL(data.kpis.total_previsao)} sub={`${data.kpis.count_previsao} parcelas previstas`} accent="text-amber-600 dark:text-amber-400" />
          </div>

          {/* Categoria breakdown */}
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Recorrente vs Pontual</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {data.by_categoria.map((c: ExpenseByCategoria) => {
                const pct = data.kpis.total_valor > 0 ? (c.valor / data.kpis.total_valor) * 100 : 0;
                const color = c.categoria === "Recorrente" ? "bg-emerald-500" : c.categoria === "Ocasional" ? "bg-blue-500" : "bg-orange-400";
                return (
                  <button key={c.categoria} onClick={() => setFilterCategoria(filterCategoria === c.categoria ? "" : c.categoria)}
                    className={`text-left p-4 rounded-lg border-2 transition-colors ${filterCategoria === c.categoria ? "border-brand-green bg-brand-soft dark:bg-brand-green/10" : "border-gray-100 dark:border-gray-800 hover:border-gray-200 dark:hover:border-gray-700"}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`w-3 h-3 rounded-full ${color}`} />
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{c.categoria}</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{FMT_BRL(c.valor)}</p>
                    <div className="mt-2 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-gray-400">{pct.toFixed(1)}% do total</p>
                  </button>
                );
              })}
            </div>
            {filterCategoria && (
              <button onClick={() => setFilterCategoria("")} className="mt-3 text-xs text-brand-green hover:underline">
                Limpar filtro de categoria
              </button>
            )}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {/* Evolução mensal */}
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Evolução Mensal</h2>
              {data.by_month.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">Sem dados no período</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={data.by_month} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v: number) => `R$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} width={55} />
                    <Tooltip formatter={(v: number) => [FMT_BRL(v), "Total"]} />
                    <Line type="monotone" dataKey="valor" stroke="#10b981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Top 10 contas */}
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Top 10 Contas</h2>
              {data.by_conta.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">Sem dados no período</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={data.by_conta.slice(0, 10)}
                    layout="vertical"
                    margin={{ top: 0, right: 55, left: 0, bottom: 0 }}
                  >
                    <XAxis type="number" tickFormatter={(v: number) => `R$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="conta" width={150} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => [FMT_BRL(v), "Total"]} />
                    <Bar dataKey="valor" radius={[0, 3, 3, 0]}>
                      {data.by_conta.slice(0, 10).map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Tabela de lançamentos */}
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                Lançamentos
                <span className="ml-2 text-xs font-normal text-gray-400">({filteredRows.length} registros)</span>
              </h2>
              <div className="flex gap-2 flex-wrap">
                <FilterSelect value={filterCategoria} onChange={setFilterCategoria} placeholder="Categoria" options={["Recorrente", "Ocasional", "Pontual"]} />
                <FilterSelect value={filterTipo} onChange={setFilterTipo} placeholder="Tipo" options={["Efetivo", "Previsao"]} />
                <FilterSelect value={filterOrigem} onChange={setFilterOrigem} placeholder="Origem" options={uniqueOrigem} />
                <FilterSelect value={filterFilial} onChange={setFilterFilial} placeholder="Filial" options={uniqueFilial} />
                {(filterTipo || filterOrigem || filterFilial || filterCategoria) && (
                  <button
                    onClick={() => { setFilterTipo(""); setFilterOrigem(""); setFilterFilial(""); setFilterCategoria(""); }}
                    className="h-8 px-3 rounded-md text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-700 transition-colors"
                  >
                    Limpar
                  </button>
                )}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-800 text-left">
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Pessoa / Fornecedor</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Conta</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 text-right">Valor</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Vencimento</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Liquidação</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Origem</th>
                    <th className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Categoria</th>
                    <th className="pb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Tipo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800/60">
                  {filteredRows.slice(0, 300).map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                      <td className="py-2 pr-4 max-w-[200px] truncate text-gray-900 dark:text-gray-100 font-medium" title={row.PESSOA}>
                        {row.PESSOA}
                      </td>
                      <td className="py-2 pr-4 max-w-[180px] truncate text-gray-500 dark:text-gray-400 text-xs" title={row.CONTA ?? ""}>
                        {row.CONTA || "—"}
                      </td>
                      <td className="py-2 pr-4 text-right font-semibold text-gray-900 dark:text-gray-100 whitespace-nowrap">
                        {FMT_BRL(row.VALOR ?? 0)}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.DATAVENCIMENTO ? row.DATAVENCIMENTO.slice(0, 10) : "—"}
                      </td>
                      <td className="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.DATALIQUIDACAO ? row.DATALIQUIDACAO.slice(0, 10) : "—"}
                      </td>
                      <td className="py-2 pr-4">
                        <OrigemBadge origem={row.ORIGEM} />
                      </td>
                      <td className="py-2 pr-4">
                        <CategoriaBadge categoria={row.CATEGORIA} />
                      </td>
                      <td className="py-2">
                        <TipoBadge tipo={row.TIPO_DOC} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {filteredRows.length > 300 && (
                <p className="mt-4 text-xs text-gray-400 dark:text-gray-500 text-center">
                  Exibindo 300 de {filteredRows.length} registros. Use os filtros para refinar.
                </p>
              )}
              {filteredRows.length === 0 && (
                <p className="py-10 text-sm text-center text-gray-400 dark:text-gray-500">
                  Nenhum lançamento encontrado para os filtros selecionados.
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
