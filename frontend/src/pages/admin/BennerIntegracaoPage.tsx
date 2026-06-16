import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";

// ── tipos ────────────────────────────────────────────────────────────────────

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

// ── helpers ──────────────────────────────────────────────────────────────────

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

// Extrai a parte mais útil da mensagem (último segmento após "→")
function shortMsg(msg: string | null | undefined): string {
  if (!msg) return "—";
  const parts = msg.split(/[→>]/);
  const last = parts[parts.length - 1].trim();
  return last.length > 10 ? last : msg;
}

// ── componente principal ─────────────────────────────────────────────────────

export default function BennerIntegracaoPage() {
  const { token } = useAuth();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtProduto, setFiltProduto] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (initial = false) => {
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

  useEffect(() => {
    load(true);
    intervalRef.current = setInterval(() => load(), 5 * 60_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [load]);

  function toggleRow(id: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  // ── dados derivados ───────────────────────────────────────────────────────

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-brand-green border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">Integrações Benner</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Log de reservas integradas — últimas 24 h
            {snap && (
              <span className="ml-2 text-gray-400">
                · Atualizado {minutesAgo(snap.capturado_em)}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 transition-colors"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/>
          </svg>
          Atualizar
        </button>
      </div>

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
                <div
                  className="bg-green-500 transition-all duration-500"
                  style={{ width: `${(snap.ok / snap.total) * 100}%` }}
                />
                <div
                  className="bg-red-500 transition-all duration-500"
                  style={{ width: `${(snap.erros / snap.total) * 100}%` }}
                />
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
                {snap.erros === 0
                  ? "Nenhum erro nas últimas 24 h"
                  : "Nenhum erro corresponde ao filtro"}
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
                                <svg
                                  width="11" height="11" viewBox="0 0 24 24" fill="none"
                                  stroke="currentColor" strokeWidth="2.5"
                                  strokeLinecap="round" strokeLinejoin="round"
                                  className={`transition-transform ${isOpen ? "rotate-90" : ""}`}
                                >
                                  <polyline points="9 18 15 12 9 6"/>
                                </svg>
                              ) : null}
                            </td>
                            <td className="px-3 py-2.5 whitespace-nowrap text-gray-500 dark:text-gray-400 tabular-nums">
                              {fmt(e.data)}
                            </td>
                            <td className="px-3 py-2.5 whitespace-nowrap">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                {e.produto || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 font-mono whitespace-nowrap text-gray-700 dark:text-gray-300">
                              {e.reserva || "—"}
                            </td>
                            <td className="px-3 py-2.5 whitespace-nowrap">
                              <SituacaoBadge label={e.situacao_label} s={e.situacao} />
                            </td>
                            <td className="px-3 py-2.5 whitespace-nowrap text-gray-500 dark:text-gray-400">
                              {e.sistema || "—"}
                            </td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[140px] truncate" title={e.cliente}>
                              {e.cliente || "—"}
                            </td>
                            <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400 max-w-[220px] truncate" title={e.mensagem}>
                              {short}
                            </td>
                          </tr>
                          {isOpen && (
                            <tr key={`${e.id}-${idx}-detail`} className="bg-gray-50 dark:bg-gray-700/20">
                              <td colSpan={8} className="px-6 py-3">
                                <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Mensagem completa</p>
                                <p className="text-xs text-gray-700 dark:text-gray-300 font-mono leading-relaxed whitespace-pre-wrap break-all">
                                  {e.mensagem}
                                </p>
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

          {/* Footer */}
          <p className="text-center text-[11px] text-gray-400 dark:text-gray-500">
            Snapshot de {fmt(snap.capturado_em)} · coleta automática diária (07h BRT) · banco D-1
          </p>
        </>
      )}
    </div>
  );
}
