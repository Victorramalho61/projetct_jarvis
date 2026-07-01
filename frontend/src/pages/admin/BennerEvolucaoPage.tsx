import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";

// ── tipos ─────────────────────────────────────────────────────────────────────

interface EvolucaoItem {
  periodo: string;
  produto: string;
  sistema_origem: string;
  rpa_categoria: string;
  total: number;
  resolvidos: number;
  aguardando: number;
  ignorado: number;
  pendente: number;
}

interface EvolucaoResponse {
  series: EvolucaoItem[];
  filtros_disponiveis: {
    produtos: string[];
    sistemas: string[];
    categorias: { key: string; label: string }[];
  };
}

interface PeriodoAgregado {
  periodo: string;
  total: number;
  resolvidos: number;
  aguardando: number;
  ignorado: number;
  pendente: number;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtPeriodo(p: string, tipo: "dia" | "mes"): string {
  if (tipo === "mes") {
    const [ano, mes] = p.split("-");
    const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
    return `${nomes[parseInt(mes) - 1]}/${ano.slice(2)}`;
  }
  const [, mes, dia] = p.split("-");
  return `${dia}/${mes}`;
}

function taxaResolucao(r: { resolvidos: number; total: number }): string {
  if (!r.total) return "—";
  return `${Math.round((r.resolvidos / r.total) * 100)}%`;
}

// ── barra de status composta ──────────────────────────────────────────────────

function StatusBar({ item, max }: { item: PeriodoAgregado; max: number }) {
  const h = max > 0 ? Math.max(4, Math.round((item.total / max) * 80)) : 4;
  const total = item.total || 1;
  const pRes = (item.resolvidos / total) * 100;
  const pAg  = (item.aguardando / total) * 100;
  const pIg  = (item.ignorado / total) * 100;
  const pPen = (item.pendente / total) * 100;

  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-[10px] text-gray-400 dark:text-gray-500 font-tabular-nums">{item.total}</span>
      <div
        className="w-6 rounded-t overflow-hidden flex flex-col-reverse"
        style={{ height: h }}
        title={`Total: ${item.total} | Resolvidos: ${item.resolvidos} | Aguardando: ${item.aguardando} | Ignorados: ${item.ignorado} | Pendentes: ${item.pendente}`}
      >
        <div style={{ height: `${pRes}%` }} className="bg-green-500 dark:bg-green-600 shrink-0" />
        <div style={{ height: `${pAg}%` }}  className="bg-orange-400 dark:bg-orange-500 shrink-0" />
        <div style={{ height: `${pIg}%` }}  className="bg-gray-300 dark:bg-gray-600 shrink-0" />
        <div style={{ height: `${pPen}%` }} className="bg-yellow-400 dark:bg-yellow-500 shrink-0" />
      </div>
    </div>
  );
}

// ── componente principal ──────────────────────────────────────────────────────

export default function BennerEvolucaoPage() {
  const { token } = useAuth();

  const [tipoPeriodo, setTipoPeriodo] = useState<"dia" | "mes">("dia");
  const [filtProduto, setFiltProduto] = useState("");
  const [filtSistema, setFiltSistema] = useState("");
  const [filtCategoria, setFiltCategoria] = useState("");

  const [data, setData] = useState<EvolucaoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortCol, setSortCol] = useState<keyof EvolucaoItem>("periodo");
  const [sortAsc, setSortAsc] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const dias = tipoPeriodo === "dia" ? 30 : 365;
      const params = new URLSearchParams({
        periodo: tipoPeriodo,
        dias: String(dias),
      });
      if (filtProduto)  params.set("produto",    filtProduto);
      if (filtSistema)  params.set("sistema",    filtSistema);
      if (filtCategoria) params.set("categoria", filtCategoria);
      const d = await apiFetch<EvolucaoResponse>(
        `/api/monitoring/benner/rpa/evolucao?${params}`,
        { token }
      );
      setData(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }, [token, tipoPeriodo, filtProduto, filtSistema, filtCategoria]);

  useEffect(() => { load(); }, [load]);

  // KPIs agregados do período
  const kpis = useMemo(() => {
    const s = data?.series ?? [];
    const total     = s.reduce((a, r) => a + r.total, 0);
    const resolvidos = s.reduce((a, r) => a + r.resolvidos, 0);
    const aguardando = s.reduce((a, r) => a + r.aguardando, 0);
    const ignorado   = s.reduce((a, r) => a + r.ignorado, 0);
    const pendente   = s.reduce((a, r) => a + r.pendente, 0);
    const taxa = total ? Math.round((resolvidos / total) * 100) : 0;
    return { total, resolvidos, aguardando, ignorado, pendente, taxa };
  }, [data]);

  // Agrega por período para o gráfico
  const chartData = useMemo<PeriodoAgregado[]>(() => {
    const map: Record<string, PeriodoAgregado> = {};
    for (const r of data?.series ?? []) {
      if (!map[r.periodo]) {
        map[r.periodo] = { periodo: r.periodo, total: 0, resolvidos: 0, aguardando: 0, ignorado: 0, pendente: 0 };
      }
      map[r.periodo].total      += r.total;
      map[r.periodo].resolvidos += r.resolvidos;
      map[r.periodo].aguardando += r.aguardando;
      map[r.periodo].ignorado   += r.ignorado;
      map[r.periodo].pendente   += r.pendente;
    }
    return Object.values(map).sort((a, b) => a.periodo.localeCompare(b.periodo));
  }, [data]);

  const chartMax = useMemo(() => Math.max(...chartData.map(d => d.total), 1), [chartData]);

  // Tabela ordenada
  const tableRows = useMemo(() => {
    const rows = [...(data?.series ?? [])];
    rows.sort((a, b) => {
      const va = a[sortCol] ?? "";
      const vb = b[sortCol] ?? "";
      const cmp = typeof va === "number" && typeof vb === "number"
        ? va - vb
        : String(va).localeCompare(String(vb));
      return sortAsc ? cmp : -cmp;
    });
    return rows;
  }, [data, sortCol, sortAsc]);

  function toggleSort(col: keyof EvolucaoItem) {
    if (sortCol === col) setSortAsc(v => !v);
    else { setSortCol(col); setSortAsc(false); }
  }

  function Th({ col, label }: { col: keyof EvolucaoItem; label: string }) {
    const active = sortCol === col;
    return (
      <th
        onClick={() => toggleSort(col)}
        className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 cursor-pointer select-none whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200"
      >
        {label}
        {active && <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>}
      </th>
    );
  }

  const filtros = data?.filtros_disponiveis;

  return (
    <div className="p-6 space-y-6 max-w-screen-xl mx-auto">
      {/* Cabeçalho */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
          Acompanhamento — Automações RPA
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Evolução de erros e resoluções {tipoPeriodo === "dia" ? "nos últimos 30 dias" : "nos últimos 12 meses"}
        </p>
      </div>

      {/* Controles */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Toggle período */}
        <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          {(["dia", "mes"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTipoPeriodo(t); }}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                tipoPeriodo === t
                  ? "bg-brand-green text-white"
                  : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {t === "dia" ? "Diário" : "Mensal"}
            </button>
          ))}
        </div>

        {/* Filtros */}
        {filtros && (
          <>
            <select
              value={filtProduto}
              onChange={e => setFiltProduto(e.target.value)}
              className="h-8 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-green/40"
            >
              <option value="">Todos os produtos</option>
              {filtros.produtos.map(p => <option key={p} value={p}>{p}</option>)}
            </select>

            <select
              value={filtSistema}
              onChange={e => setFiltSistema(e.target.value)}
              className="h-8 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-green/40"
            >
              <option value="">Todos os sistemas</option>
              {filtros.sistemas.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            <select
              value={filtCategoria}
              onChange={e => setFiltCategoria(e.target.value)}
              className="h-8 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-green/40"
            >
              <option value="">Todos os problemas</option>
              {filtros.categorias.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>

            {(filtProduto || filtSistema || filtCategoria) && (
              <button
                onClick={() => { setFiltProduto(""); setFiltSistema(""); setFiltCategoria(""); }}
                className="h-8 px-3 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 border border-gray-200 dark:border-gray-700 transition-colors"
              >
                Limpar filtros
              </button>
            )}
          </>
        )}

        <button
          onClick={load}
          disabled={loading}
          className="ml-auto h-8 px-3 rounded-lg text-sm font-medium border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          {loading ? "Carregando…" : "Atualizar"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center h-48">
          <div className="w-8 h-8 border-4 border-brand-green border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[
              { label: "Total de erros", value: kpis.total, color: "text-gray-900 dark:text-gray-100" },
              { label: "Resolvidos", value: kpis.resolvidos, color: "text-green-600 dark:text-green-400" },
              { label: "Aguardando input", value: kpis.aguardando, color: "text-orange-600 dark:text-orange-400" },
              { label: "Ignorados", value: kpis.ignorado, color: "text-gray-500 dark:text-gray-400" },
              { label: "Taxa de resolução", value: `${kpis.taxa}%`, color: kpis.taxa >= 70 ? "text-green-600 dark:text-green-400" : kpis.taxa >= 40 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3">
                <div className="text-[11px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</div>
                <div className={`mt-1 text-2xl font-bold tabular-nums ${color}`}>{value}</div>
              </div>
            ))}
          </div>

          {/* Gráfico de barras */}
          {chartData.length > 0 && (
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Erros por {tipoPeriodo === "dia" ? "dia" : "mês"}
                </h2>
                <div className="flex items-center gap-3 text-[10px]">
                  {[
                    { color: "bg-yellow-400", label: "Pendentes" },
                    { color: "bg-gray-300 dark:bg-gray-600", label: "Ignorados" },
                    { color: "bg-orange-400", label: "Aguardando" },
                    { color: "bg-green-500", label: "Resolvidos" },
                  ].map(l => (
                    <span key={l.label} className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
                      <span className={`w-2.5 h-2.5 rounded-sm ${l.color}`} />
                      {l.label}
                    </span>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <div className="flex items-end gap-1 min-w-max pb-1" style={{ minHeight: 100 }}>
                  {chartData.map(item => (
                    <div key={item.periodo} className="flex flex-col items-center gap-1">
                      <StatusBar item={item} max={chartMax} />
                      <span className="text-[9px] text-gray-400 dark:text-gray-500 whitespace-nowrap">
                        {fmtPeriodo(item.periodo, tipoPeriodo)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Tabela detalhada */}
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                Detalhamento ({tableRows.length} registros)
              </h2>
            </div>
            {tableRows.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-gray-400 dark:text-gray-500">
                Nenhum dado encontrado para os filtros selecionados.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800/60 border-b border-gray-100 dark:border-gray-800">
                    <tr>
                      <Th col="periodo"       label="Período" />
                      <Th col="produto"       label="Produto" />
                      <Th col="sistema_origem" label="Sistema" />
                      <Th col="rpa_categoria" label="Problema" />
                      <Th col="total"         label="Total" />
                      <Th col="resolvidos"    label="Resolvidos" />
                      <Th col="aguardando"    label="Aguardando" />
                      <Th col="ignorado"      label="Ignorados" />
                      <Th col="pendente"      label="Pendentes" />
                      <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 whitespace-nowrap">Taxa</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                    {tableRows.map((r, i) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                        <td className="px-3 py-2 font-mono text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">
                          {fmtPeriodo(r.periodo, tipoPeriodo)}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
                          {r.produto || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
                          {r.sistema_origem || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
                          {(filtros?.categorias.find(c => c.key === r.rpa_categoria)?.label ?? r.rpa_categoria) || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs font-semibold tabular-nums text-gray-900 dark:text-gray-100">
                          {r.total}
                        </td>
                        <td className="px-3 py-2 text-xs tabular-nums text-green-600 dark:text-green-400">
                          {r.resolvidos || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs tabular-nums text-orange-600 dark:text-orange-400">
                          {r.aguardando || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs tabular-nums text-gray-500 dark:text-gray-400">
                          {r.ignorado || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs tabular-nums text-yellow-600 dark:text-yellow-400">
                          {r.pendente || "—"}
                        </td>
                        <td className="px-3 py-2 text-xs tabular-nums font-medium text-gray-700 dark:text-gray-300">
                          {taxaResolucao(r)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
