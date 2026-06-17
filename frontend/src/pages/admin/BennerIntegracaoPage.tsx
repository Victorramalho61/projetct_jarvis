import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";

// ── tipos ─────────────────────────────────────────────────────────────────────

interface ErroItem {
  id: number;
  produto: string;
  reserva: string;
  situacao: number;
  situacao_label: string;
  mensagem: string;
  data: string;
  sistema: string;
  cliente: string;
}

interface Snapshot {
  capturado_em: string;
  total: number;
  ok: number;
  erros: number;
  taxa_erro_pct: number;
  por_produto: Record<string, { ok: number; erros: number }>;
  erros_recentes: ErroItem[];
}

interface RpaCategoria {
  categoria: string;
  label: string;
  total: number;
  resolvidos: number;
  aguardando_input: number;
  pendente: number;
  taxa_resolucao_pct: number;
}

interface RpaSummary {
  total_acumulado: number;
  por_status: Record<string, number>;
  resolvidos_hoje: number;
  por_categoria: RpaCategoria[];
  rpa_ativo: boolean;
}

interface RpaErro {
  id: number;
  benner_handle: number;
  produto: string;
  sistema_origem: string;
  codigo_reserva: string;
  rpa_status: string;
  rpa_categoria: string;
  categoria_label: string;
  rpa_tentativas: number;
  rpa_ultima_acao: string | null;
  rpa_resultado: string | null;
  capturado_em: string;
  mensagem?: string;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function minutesAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "agora";
  if (mins === 1) return "1 min atrás";
  if (mins < 60) return `${mins} min atrás`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h atrás`;
}

function SituacaoBadge({ label, s }: { label: string; s: number }) {
  const cls =
    s === 1
      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
      : s === 20
      ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
      : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function RpaStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pendente:        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    processando:     "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    resolvido:       "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    aguardando_input:"bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    ignorado:        "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400",
  };
  const labels: Record<string, string> = {
    pendente: "Pendente", processando: "Processando",
    resolvido: "Resolvido", aguardando_input: "Aguarda input", ignorado: "Ignorado",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${map[status] || map.pendente}`}>
      {labels[status] || status}
    </span>
  );
}

function shortMsg(msg: string | null | undefined): string {
  if (!msg) return "—";
  const parts = msg.split(/[→>]/);
  const last = parts[parts.length - 1].trim();
  return last.length > 10 ? last : msg;
}

// ── componente principal ──────────────────────────────────────────────────────

type Tab = "monitoramento" | "rpa";

export default function BennerIntegracaoPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>("monitoramento");

  // ── estado monitoramento ─────────────────────────────────────────────────
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtProduto, setFiltProduto] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  // ── estado RPA ───────────────────────────────────────────────────────────
  const [rpaSummary, setRpaSummary] = useState<RpaSummary | null>(null);
  const [rpaQueue, setRpaQueue] = useState<RpaErro[]>([]);
  const [rpaHistory, setRpaHistory] = useState<RpaErro[]>([]);
  const [rpaLoading, setRpaLoading] = useState(false);
  const [rpaError, setRpaError] = useState<string | null>(null);
  const [rpaAction, setRpaAction] = useState<number | null>(null);

  // ── carregamento ─────────────────────────────────────────────────────────

  const loadSnap = useCallback(async (initial = false) => {
    if (!token) return;
    if (initial) setLoading(true);
    setError(null);
    try {
      const d = await apiFetch<Snapshot>("/api/monitoring/benner/latest", { token });
      setSnap(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar dados.");
    } finally {
      if (initial) setLoading(false);
    }
  }, [token]);

  const loadRpa = useCallback(async () => {
    if (!token) return;
    setRpaLoading(true);
    setRpaError(null);
    try {
      const [summary, queue, history] = await Promise.all([
        apiFetch<RpaSummary>("/api/monitoring/benner/rpa/summary", { token }),
        apiFetch<{ items: RpaErro[] }>("/api/monitoring/benner/rpa/queue?limit=50", { token }),
        apiFetch<{ items: RpaErro[] }>("/api/monitoring/benner/rpa/history?limit=50", { token }),
      ]);
      setRpaSummary(summary);
      setRpaQueue(queue.items);
      setRpaHistory(history.items);
    } catch (e) {
      setRpaError(e instanceof ApiError ? e.message : "Erro ao carregar dados RPA.");
    } finally {
      setRpaLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadSnap(true);
  }, [loadSnap]);

  useEffect(() => {
    if (tab === "rpa") loadRpa();
  }, [tab, loadRpa]);

  // ── ações RPA ────────────────────────────────────────────────────────────

  async function rpaAction_(id: number, action: "resolve" | "ignore" | "retry") {
    setRpaAction(id);
    try {
      await apiFetch(`/api/monitoring/benner/rpa/${id}/${action}`, { token, method: "POST" });
      await loadRpa();
    } catch {
      // silently ignore
    } finally {
      setRpaAction(null);
    }
  }

  function toggleRow(id: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  // ── dados derivados ──────────────────────────────────────────────────────

  const produtos = snap
    ? Object.entries(snap.por_produto).sort((a, b) => (b[1].erros + b[1].ok) - (a[1].erros + a[1].ok))
    : [];

  const errosFiltrados = (snap?.erros_recentes ?? []).filter(e => {
    if (filtProduto && e.produto !== filtProduto) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!e.mensagem?.toLowerCase().includes(q) &&
          !e.reserva?.toLowerCase().includes(q) &&
          !e.sistema?.toLowerCase().includes(q) &&
          !e.cliente?.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const taxaCor =
    !snap ? "text-gray-400"
    : snap.taxa_erro_pct < 10 ? "text-green-600 dark:text-green-400"
    : snap.taxa_erro_pct < 25 ? "text-orange-500 dark:text-orange-400"
    : "text-red-600 dark:text-red-400";

  // ── render ────────────────────────────────────────────────────────────────

  if (loading && tab === "monitoramento") {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-brand-green border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">Integrações Benner</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Log de reservas integradas — coleta diária (07h BRT)
          {snap && (
            <span className="ml-2 text-gray-400">
              · Snapshot de {fmt(snap.capturado_em)}
            </span>
          )}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        {(["monitoramento", "rpa"] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-brand-green text-brand-green"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {t === "monitoramento" ? "Monitoramento" : "Automações RPA"}
            {t === "rpa" && rpaSummary && rpaSummary.por_status.aguardando_input > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-orange-500 text-white text-[9px] font-bold">
                {rpaSummary.por_status.aguardando_input}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── TAB: MONITORAMENTO ─────────────────────────────────────────────── */}
      {tab === "monitoramento" && (
        <>
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          {!snap && !error && (
            <div className="text-center py-16 text-sm text-gray-400">
              Nenhum snapshot disponível. O scheduler coleta dados diariamente às 07h BRT.
            </div>
          )}

          {snap && (
            <>
              {/* KPI cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: "Total", value: snap.total.toLocaleString("pt-BR"), color: "text-gray-800 dark:text-gray-100" },
                  { label: "OK", value: snap.ok.toLocaleString("pt-BR"), color: "text-green-600 dark:text-green-400" },
                  { label: "Erros", value: snap.erros.toLocaleString("pt-BR"), color: "text-red-600 dark:text-red-400" },
                  { label: "Taxa de erro", value: `${snap.taxa_erro_pct}%`, color: taxaCor },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</p>
                    <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Barra ok/erro global */}
              {snap.total > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Proporção geral</span>
                    <span className="text-xs text-gray-400">{snap.ok} OK · {snap.erros} erros</span>
                  </div>
                  <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-700">
                    <div className="bg-green-500 transition-all duration-500" style={{ width: `${(snap.ok / snap.total) * 100}%` }} />
                    <div className="bg-red-500 transition-all duration-500" style={{ width: `${(snap.erros / snap.total) * 100}%` }} />
                  </div>
                </div>
              )}

              {/* Por produto */}
              {produtos.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                  <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Por produto</h2>
                  <div className="space-y-2.5">
                    {produtos.map(([prod, v]) => {
                      const total = v.ok + v.erros;
                      const pctErro = total ? (v.erros / total) * 100 : 0;
                      return (
                        <div key={prod}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate max-w-[120px]">{prod}</span>
                            <div className="flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400">
                              <span className="text-green-600 dark:text-green-400">✓{v.ok}</span>
                              {v.erros > 0 && <span className="text-red-600 dark:text-red-400">✗{v.erros}</span>}
                            </div>
                          </div>
                          <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-700">
                            {total > 0 && (
                              <>
                                <div className="bg-green-500" style={{ width: `${100 - pctErro}%` }} />
                                <div className="bg-red-500" style={{ width: `${pctErro}%` }} />
                              </>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Tabela de erros */}
              <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between flex-wrap gap-2">
                  <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Erros recentes
                    <span className="ml-1.5 text-xs font-normal text-gray-400">({errosFiltrados.length})</span>
                  </h2>
                  <div className="flex items-center gap-2 flex-wrap">
                    <input
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Buscar mensagem, reserva, sistema…"
                      className="h-7 text-xs px-2.5 rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-brand-green w-52"
                    />
                    <select
                      value={filtProduto}
                      onChange={e => setFiltProduto(e.target.value)}
                      className="h-7 text-xs px-2 rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-brand-green"
                    >
                      <option value="">Todos os produtos</option>
                      {[...new Set((snap.erros_recentes ?? []).map(e => e.produto).filter(Boolean))].sort().map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {errosFiltrados.length === 0 ? (
                  <div className="px-4 py-10 text-center text-sm text-gray-400 dark:text-gray-500">
                    {snap.erros === 0 ? "Nenhum erro nas últimas 24 h" : "Nenhum erro corresponde ao filtro"}
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-50 dark:bg-gray-700/50 text-left text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          <th className="px-3 py-2.5 font-medium w-[1px]"></th>
                          <th className="px-3 py-2.5 font-medium whitespace-nowrap">Data/Hora</th>
                          <th className="px-3 py-2.5 font-medium">Produto</th>
                          <th className="px-3 py-2.5 font-medium">Reserva</th>
                          <th className="px-3 py-2.5 font-medium">Status</th>
                          <th className="px-3 py-2.5 font-medium">Sistema</th>
                          <th className="px-3 py-2.5 font-medium">Cliente</th>
                          <th className="px-3 py-2.5 font-medium">Erro</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {errosFiltrados.map((e, idx) => {
                          const isOpen = expanded.has(e.id);
                          const short = shortMsg(e.mensagem);
                          const hasMore = e.mensagem && e.mensagem.length > short.length + 5;
                          return (
                            <>
                              <tr
                                key={`${e.id}-${idx}`}
                                onClick={() => hasMore && toggleRow(e.id)}
                                className={`transition-colors ${hasMore ? "cursor-pointer" : ""} hover:bg-gray-50 dark:hover:bg-gray-700/30`}
                              >
                                <td className="px-2 py-2.5 text-gray-400">
                                  {hasMore ? (
                                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`transition-transform ${isOpen ? "rotate-90" : ""}`}>
                                      <polyline points="9 18 15 12 9 6"/>
                                    </svg>
                                  ) : null}
                                </td>
                                <td className="px-3 py-2.5 whitespace-nowrap text-gray-500 dark:text-gray-400 tabular-nums">{fmt(e.data)}</td>
                                <td className="px-3 py-2.5 whitespace-nowrap">
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                    {e.produto || "—"}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 font-mono whitespace-nowrap text-gray-700 dark:text-gray-300">{e.reserva || "—"}</td>
                                <td className="px-3 py-2.5 whitespace-nowrap"><SituacaoBadge label={e.situacao_label} s={e.situacao} /></td>
                                <td className="px-3 py-2.5 whitespace-nowrap text-gray-500 dark:text-gray-400">{e.sistema || "—"}</td>
                                <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[140px] truncate" title={e.cliente}>{e.cliente || "—"}</td>
                                <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400 max-w-[220px] truncate" title={e.mensagem}>{short}</td>
                              </tr>
                              {isOpen && (
                                <tr key={`${e.id}-${idx}-detail`} className="bg-gray-50 dark:bg-gray-700/20">
                                  <td colSpan={8} className="px-6 py-3">
                                    <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Mensagem completa</p>
                                    <p className="text-xs text-gray-700 dark:text-gray-300 font-mono leading-relaxed whitespace-pre-wrap break-all">{e.mensagem}</p>
                                  </td>
                                </tr>
                              )}
                            </>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <p className="text-center text-[11px] text-gray-400 dark:text-gray-500">
                Snapshot de {fmt(snap.capturado_em)} · coleta automática diária (07h BRT) · banco D-1
              </p>
            </>
          )}
        </>
      )}

      {/* ── TAB: AUTOMAÇÕES RPA ───────────────────────────────────────────── */}
      {tab === "rpa" && (
        <>
          {rpaLoading && (
            <div className="flex items-center justify-center h-40">
              <div className="w-8 h-8 border-4 border-brand-green border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {rpaError && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
              {rpaError}
            </div>
          )}

          {!rpaLoading && rpaSummary && (
            <>
              {/* Aviso RPA inativo */}
              {!rpaSummary.rpa_ativo && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 flex items-start gap-2.5">
                  <svg className="shrink-0 mt-0.5 text-blue-500" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-blue-800 dark:text-blue-300">Fase de acumulação ativa — RPA aguarda validação</p>
                    <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                      Os erros estão sendo coletados e classificados. O motor de execução será ativado após revisão com a equipe.
                    </p>
                  </div>
                </div>
              )}

              {/* KPIs RPA */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {[
                  { label: "Total acumulado", value: rpaSummary.total_acumulado, color: "text-gray-800 dark:text-gray-100" },
                  { label: "Pendentes", value: rpaSummary.por_status.pendente || 0, color: "text-yellow-600 dark:text-yellow-400" },
                  { label: "Resolvidos hoje", value: rpaSummary.resolvidos_hoje, color: "text-green-600 dark:text-green-400" },
                  { label: "Aguard. input", value: rpaSummary.por_status.aguardando_input || 0, color: "text-orange-600 dark:text-orange-400" },
                  { label: "Ignorados", value: rpaSummary.por_status.ignorado || 0, color: "text-gray-500 dark:text-gray-400" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</p>
                    <p className={`text-2xl font-bold tabular-nums ${color}`}>{value.toLocaleString("pt-BR")}</p>
                  </div>
                ))}
              </div>

              {/* Por categoria */}
              {rpaSummary.por_categoria.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                    <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Distribuição por categoria</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-50 dark:bg-gray-700/50 text-left text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          <th className="px-4 py-2.5 font-medium">Categoria</th>
                          <th className="px-4 py-2.5 font-medium text-right">Total</th>
                          <th className="px-4 py-2.5 font-medium text-right">Pendentes</th>
                          <th className="px-4 py-2.5 font-medium text-right">Resolvidos</th>
                          <th className="px-4 py-2.5 font-medium text-right">Aguard. input</th>
                          <th className="px-4 py-2.5 font-medium">Taxa auto</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {rpaSummary.por_categoria.map(c => (
                          <tr key={c.categoria} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                            <td className="px-4 py-2.5 font-medium text-gray-700 dark:text-gray-300">{c.label}</td>
                            <td className="px-4 py-2.5 text-right text-gray-500 tabular-nums">{c.total}</td>
                            <td className="px-4 py-2.5 text-right text-yellow-600 dark:text-yellow-400 tabular-nums">{c.pendente}</td>
                            <td className="px-4 py-2.5 text-right text-green-600 dark:text-green-400 tabular-nums">{c.resolvidos}</td>
                            <td className="px-4 py-2.5 text-right text-orange-600 dark:text-orange-400 tabular-nums">{c.aguardando_input}</td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-1.5 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden">
                                  <div className="h-full bg-green-500" style={{ width: `${c.taxa_resolucao_pct}%` }} />
                                </div>
                                <span className="text-[11px] text-gray-500 tabular-nums w-8 text-right">{c.taxa_resolucao_pct}%</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Fila aguardando input */}
              {rpaQueue.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-orange-200 dark:border-orange-800/50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-orange-100 dark:border-orange-800/30 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
                    <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                      Aguardando input
                      <span className="ml-1.5 text-xs font-normal text-gray-400">({rpaQueue.length})</span>
                    </h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-orange-50 dark:bg-orange-900/10 text-left text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          <th className="px-3 py-2.5 font-medium">Produto</th>
                          <th className="px-3 py-2.5 font-medium">Sistema</th>
                          <th className="px-3 py-2.5 font-medium">Reserva</th>
                          <th className="px-3 py-2.5 font-medium">Categoria</th>
                          <th className="px-3 py-2.5 font-medium">Tentativas</th>
                          <th className="px-3 py-2.5 font-medium">Resultado RPA</th>
                          <th className="px-3 py-2.5 font-medium">Ações</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {rpaQueue.map(e => (
                          <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                            <td className="px-3 py-2.5">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                {e.produto || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">{e.sistema_origem || "—"}</td>
                            <td className="px-3 py-2.5 font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{e.codigo_reserva || "—"}</td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{e.categoria_label || e.rpa_categoria || "—"}</td>
                            <td className="px-3 py-2.5 text-center tabular-nums text-gray-500">{e.rpa_tentativas}</td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[200px] truncate" title={e.rpa_resultado || ""}>{e.rpa_resultado || "—"}</td>
                            <td className="px-3 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={() => rpaAction_(e.id, "resolve")}
                                  disabled={rpaAction === e.id}
                                  className="px-2 py-1 text-[10px] font-medium rounded bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 disabled:opacity-50 transition-colors"
                                >
                                  Resolver
                                </button>
                                <button
                                  onClick={() => rpaAction_(e.id, "retry")}
                                  disabled={rpaAction === e.id}
                                  className="px-2 py-1 text-[10px] font-medium rounded bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400 disabled:opacity-50 transition-colors"
                                >
                                  Retry
                                </button>
                                <button
                                  onClick={() => rpaAction_(e.id, "ignore")}
                                  disabled={rpaAction === e.id}
                                  className="px-2 py-1 text-[10px] font-medium rounded bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-400 disabled:opacity-50 transition-colors"
                                >
                                  Ignorar
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {rpaQueue.length === 0 && rpaSummary.total_acumulado === 0 && (
                <div className="text-center py-16 text-sm text-gray-400">
                  Nenhum erro acumulado ainda. O coletor roda diariamente às 07h BRT junto com o snapshot.
                </div>
              )}

              {/* Histórico de execuções */}
              {rpaHistory.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                    <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                      Histórico de execuções
                      <span className="ml-1.5 text-xs font-normal text-gray-400">({rpaHistory.length} mais recentes)</span>
                    </h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-50 dark:bg-gray-700/50 text-left text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          <th className="px-3 py-2.5 font-medium">Última ação</th>
                          <th className="px-3 py-2.5 font-medium">Produto</th>
                          <th className="px-3 py-2.5 font-medium">Sistema</th>
                          <th className="px-3 py-2.5 font-medium">Reserva</th>
                          <th className="px-3 py-2.5 font-medium">Categoria</th>
                          <th className="px-3 py-2.5 font-medium">Status</th>
                          <th className="px-3 py-2.5 font-medium">Resultado</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {rpaHistory.map(e => (
                          <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                            <td className="px-3 py-2.5 whitespace-nowrap text-gray-500 dark:text-gray-400 tabular-nums">{fmt(e.rpa_ultima_acao)}</td>
                            <td className="px-3 py-2.5">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                {e.produto || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">{e.sistema_origem || "—"}</td>
                            <td className="px-3 py-2.5 font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{e.codigo_reserva || "—"}</td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{e.categoria_label || e.rpa_categoria || "—"}</td>
                            <td className="px-3 py-2.5"><RpaStatusBadge status={e.rpa_status} /></td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[220px] truncate" title={e.rpa_resultado || ""}>{e.rpa_resultado || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
