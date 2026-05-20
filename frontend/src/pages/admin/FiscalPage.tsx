import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import { apiFetch } from "../../lib/api";
import Icon from "../../components/Icon";

// ─── Tipos ───────────────────────────────────────────────────────────────────

interface FiscalCompany {
  id: string;
  cnpj: string;
  nome: string;
  regime: string;
  sync_nfe_ativo: boolean;
  sync_cte_ativo: boolean;
  sync_nfse_ativo: boolean;
  ndd_last_sync_at: string | null;
  ndd_access_token: string | null;
  ndd_token_expires_at: string | null;
  cert_expiry: string | null;
  ultima_sync: string | null;
}

interface NfseStats {
  total_notas: number;
  valor_total: number;
  valor_iss: number;
  por_municipio: Record<string, number>;
  por_status: Record<string, number>;
}

interface NfseDoc {
  id: string;
  company_id: string;
  chave_acesso: string;
  numero: string;
  emitente_cnpj: string;
  emitente_nome: string;
  destinatario_cnpj: string;
  destinatario_nome: string;
  data_emissao: string;
  valor_total: number;
  valor_iss: number | null;
  municipio_nome: string;
  status: string;
  ndd_sync_at: string | null;
}

interface SyncLog {
  id: string;
  tipo: string;
  status: string;
  documentos_novos: number;
  documentos_cancelados: number;
  erro_msg: string | null;
  janela: string;
  executado_em: string;
}

// ─── Formatadores ────────────────────────────────────────────────────────────

const FMT_BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 2 });
const FMT_NUM = new Intl.NumberFormat("pt-BR");
const fmtDate = (s: string | null) => s ? new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const fmtDay  = (s: string | null) => s ? new Date(s + "T12:00:00").toLocaleDateString("pt-BR") : "—";

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, isDark }: { label: string; value: string; sub?: string; isDark: boolean }) {
  return (
    <div className={`rounded-xl border p-5 flex flex-col gap-1 ${isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
      <span className={`text-xs font-medium uppercase tracking-wide ${isDark ? "text-gray-400" : "text-gray-500"}`}>{label}</span>
      <span className={`text-2xl font-bold ${isDark ? "text-white" : "text-gray-900"}`}>{value}</span>
      {sub && <span className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>{sub}</span>}
    </div>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  pendente:    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  conferido:   "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  divergencia: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  cancelado:   "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600";
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{status}</span>;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type Tab = "dashboard" | "nfse" | "sync";

export default function FiscalPage() {
  const { token } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [tab, setTab] = useState<Tab>("dashboard");

  // companies
  const [companies, setCompanies] = useState<FiscalCompany[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>("");

  // period
  const now = new Date();
  const [ano, setAno] = useState(now.getFullYear());
  const [mes, setMes] = useState(now.getMonth() + 1);

  // stats
  const [stats, setStats] = useState<NfseStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // NFSe table
  const [docs, setDocs] = useState<NfseDoc[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsOffset, setDocsOffset] = useState(0);
  const DOCS_LIMIT = 50;

  // NFSe filters
  const [q, setQ] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterMunicipio, setFilterMunicipio] = useState("");
  const [filterCnpj, setFilterCnpj] = useState("");

  // sync logs
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");

  // ── Load companies ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token }).then((data) => {
      setCompanies(data);
      if (data.length > 0 && !selectedCompany) setSelectedCompany(data[0].id);
    }).catch(() => {});
  }, [token]);

  // ── Load stats ─────────────────────────────────────────────────────────────
  const loadStats = useCallback(() => {
    if (!token) return;
    setStatsLoading(true);
    const params = new URLSearchParams({ ano: String(ano), mes: String(mes) });
    if (selectedCompany) params.set("company_id", selectedCompany);
    apiFetch<NfseStats>(`/api/fiscal/nfse/stats?${params}`, { token })
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [token, ano, mes, selectedCompany]);

  useEffect(() => { if (tab === "dashboard") loadStats(); }, [tab, loadStats]);

  // ── Load NFSe table ────────────────────────────────────────────────────────
  const loadDocs = useCallback(() => {
    if (!token) return;
    setDocsLoading(true);
    const params = new URLSearchParams({ limit: String(DOCS_LIMIT), offset: String(docsOffset) });
    if (selectedCompany) params.set("company_id", selectedCompany);
    if (q)               params.set("q", q);
    if (filterStatus)    params.set("status", filterStatus);
    if (filterMunicipio) params.set("municipio", filterMunicipio);
    if (filterCnpj)      params.set("emitente_cnpj", filterCnpj);
    apiFetch<{ data: NfseDoc[] }>(`/api/fiscal/nfse?${params}`, { token })
      .then((r) => setDocs(r.data ?? []))
      .catch(() => setDocs([]))
      .finally(() => setDocsLoading(false));
  }, [token, selectedCompany, q, filterStatus, filterMunicipio, filterCnpj, docsOffset]);

  useEffect(() => { if (tab === "nfse") loadDocs(); }, [tab, loadDocs]);

  // ── Load sync logs ─────────────────────────────────────────────────────────
  const loadSyncLogs = useCallback(() => {
    if (!token || !selectedCompany) return;
    setSyncLoading(true);
    apiFetch<SyncLog[]>(`/api/fiscal/${selectedCompany}/sync/logs?limit=20`, { token })
      .then(setSyncLogs)
      .catch(() => setSyncLogs([]))
      .finally(() => setSyncLoading(false));
  }, [token, selectedCompany]);

  useEffect(() => { if (tab === "sync") loadSyncLogs(); }, [tab, loadSyncLogs]);

  // ── Trigger manual NFSe sync ───────────────────────────────────────────────
  const triggerSync = async () => {
    if (!token || syncing) return;
    setSyncing(true);
    setSyncMsg("");
    try {
      await apiFetch("/api/fiscal/nfse/sync/run", { token, method: "POST" });
      setSyncMsg("Sync NFSe iniciado em background — aguarde alguns minutos.");
      setTimeout(() => loadSyncLogs(), 5000);
    } catch {
      setSyncMsg("Erro ao iniciar sync. Verifique se o token NDD está configurado.");
    } finally {
      setSyncing(false);
    }
  };

  // ── Derived ────────────────────────────────────────────────────────────────
  const currentCompany = useMemo(
    () => companies.find((c) => c.id === selectedCompany),
    [companies, selectedCompany]
  );

  const topMunicipios = useMemo(() => {
    if (!stats?.por_municipio) return [];
    return Object.entries(stats.por_municipio)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8);
  }, [stats]);

  const MONTHS = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  const YEARS = [now.getFullYear() - 1, now.getFullYear()];

  // ── UI Helpers ─────────────────────────────────────────────────────────────
  const base = isDark ? "bg-gray-900 text-gray-100 min-h-screen" : "bg-gray-50 text-gray-900 min-h-screen";
  const card = isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200";
  const inp  = `border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400" : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"}`;
  const tabCls = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${tab === t
      ? isDark ? "bg-gray-700 text-white" : "bg-white text-gray-900 shadow"
      : isDark ? "text-gray-400 hover:text-gray-200" : "text-gray-500 hover:text-gray-700"}`;

  return (
    <div className={base}>
      <div className="max-w-[1440px] mx-auto p-6 space-y-6">

        {/* ── Header ── */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Fiscal</h1>
            <p className={`text-sm mt-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>
              NFSe · NFe · CTe — NDD Digital
            </p>
          </div>

          {/* Company selector */}
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedCompany}
              onChange={(e) => setSelectedCompany(e.target.value)}
              className={`${inp} min-w-[180px]`}
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.nome}</option>
              ))}
            </select>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className={`flex gap-1 p-1 rounded-xl w-fit ${isDark ? "bg-gray-800" : "bg-gray-100"}`}>
          <button className={tabCls("dashboard")} onClick={() => setTab("dashboard")}>Dashboard</button>
          <button className={tabCls("nfse")}      onClick={() => setTab("nfse")}>NFSe</button>
          <button className={tabCls("sync")}       onClick={() => setTab("sync")}>Sync</button>
        </div>

        {/* ════════════════════ TAB: DASHBOARD ════════════════════ */}
        {tab === "dashboard" && (
          <div className="space-y-6">
            {/* Period selector */}
            <div className="flex flex-wrap gap-3 items-center">
              <select value={ano} onChange={(e) => setAno(+e.target.value)} className={`${inp} w-24`}>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
              <select value={mes} onChange={(e) => setMes(+e.target.value)} className={`${inp} w-28`}>
                {MONTHS.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
              </select>
              <button
                onClick={loadStats}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
              >
                Atualizar
              </button>
            </div>

            {/* KPIs */}
            {statsLoading ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className={`rounded-xl border p-5 h-24 animate-pulse ${card}`} />
                ))}
              </div>
            ) : stats ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KPICard label="Total NFSe" value={FMT_NUM.format(stats.total_notas)} isDark={isDark} />
                <KPICard label="Valor Total" value={FMT_BRL.format(stats.valor_total)} isDark={isDark} />
                <KPICard label="ISS" value={FMT_BRL.format(stats.valor_iss)} isDark={isDark} />
                <KPICard
                  label="Pendentes"
                  value={FMT_NUM.format(stats.por_status?.pendente ?? 0)}
                  sub={`Conferidos: ${FMT_NUM.format(stats.por_status?.conferido ?? 0)}`}
                  isDark={isDark}
                />
              </div>
            ) : (
              <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Nenhum dado para o período.</p>
            )}

            {/* Por status + por município */}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Status */}
                <div className={`rounded-xl border p-5 ${card}`}>
                  <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>Por Status</h2>
                  <div className="space-y-2">
                    {Object.entries(stats.por_status).map(([s, n]) => (
                      <div key={s} className="flex items-center justify-between gap-3">
                        <StatusBadge status={s} />
                        <span className="font-mono text-sm font-medium">{FMT_NUM.format(n)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Municípios */}
                <div className={`rounded-xl border p-5 ${card}`}>
                  <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>Top Municípios</h2>
                  <div className="space-y-2">
                    {topMunicipios.length === 0 && (
                      <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Nenhum município.</p>
                    )}
                    {topMunicipios.map(([mun, n]) => (
                      <div key={mun} className="flex items-center justify-between gap-2">
                        <span className={`text-sm truncate ${isDark ? "text-gray-300" : "text-gray-700"}`}>{mun || "—"}</span>
                        <span className="font-mono text-sm font-medium shrink-0">{FMT_NUM.format(n)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Company info */}
            {currentCompany && (
              <div className={`rounded-xl border p-5 ${card}`}>
                <h2 className={`text-sm font-semibold mb-3 ${isDark ? "text-gray-300" : "text-gray-700"}`}>Empresa</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>CNPJ</span>
                    <p className="font-mono mt-0.5">{currentCompany.cnpj}</p>
                  </div>
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>Regime</span>
                    <p className="mt-0.5 capitalize">{currentCompany.regime.replace("_", " ")}</p>
                  </div>
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>Último sync NFSe</span>
                    <p className="mt-0.5">{fmtDate(currentCompany.ndd_last_sync_at)}</p>
                  </div>
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>Token NDD</span>
                    <p className={`mt-0.5 font-medium ${currentCompany.ndd_access_token ? "text-green-500" : "text-red-500"}`}>
                      {currentCompany.ndd_access_token ? "Configurado" : "Não configurado"}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════════════════════ TAB: NFSe ════════════════════ */}
        {tab === "nfse" && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap gap-3">
              <input
                type="text"
                placeholder="Busca (emitente, município, natureza...)"
                value={q}
                onChange={(e) => { setQ(e.target.value); setDocsOffset(0); }}
                className={`${inp} flex-1 min-w-[200px]`}
              />
              <input
                type="text"
                placeholder="CNPJ emitente"
                value={filterCnpj}
                onChange={(e) => { setFilterCnpj(e.target.value); setDocsOffset(0); }}
                className={`${inp} w-40 font-mono`}
              />
              <input
                type="text"
                placeholder="Município"
                value={filterMunicipio}
                onChange={(e) => { setFilterMunicipio(e.target.value); setDocsOffset(0); }}
                className={`${inp} w-36`}
              />
              <select
                value={filterStatus}
                onChange={(e) => { setFilterStatus(e.target.value); setDocsOffset(0); }}
                className={`${inp} w-36`}
              >
                <option value="">Todos status</option>
                <option value="pendente">Pendente</option>
                <option value="conferido">Conferido</option>
                <option value="divergencia">Divergência</option>
                <option value="cancelado">Cancelado</option>
              </select>
              <button
                onClick={() => { setDocsOffset(0); loadDocs(); }}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
              >
                Buscar
              </button>
            </div>

            {/* Table */}
            <div className={`rounded-xl border overflow-hidden ${card}`}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className={`border-b text-left ${isDark ? "border-gray-700 bg-gray-750" : "border-gray-200 bg-gray-50"}`}>
                      <th className="px-4 py-3 font-medium">Data</th>
                      <th className="px-4 py-3 font-medium">Emitente</th>
                      <th className="px-4 py-3 font-medium">Município</th>
                      <th className="px-4 py-3 font-medium text-right">Valor</th>
                      <th className="px-4 py-3 font-medium text-right">ISS</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium font-mono text-xs">Chave</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docsLoading ? (
                      [...Array(8)].map((_, i) => (
                        <tr key={i} className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                          {[...Array(7)].map((_, j) => (
                            <td key={j} className="px-4 py-3">
                              <div className={`h-4 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : docs.length === 0 ? (
                      <tr>
                        <td colSpan={7} className={`px-4 py-8 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                          Nenhuma NFSe encontrada para os filtros selecionados.
                        </td>
                      </tr>
                    ) : (
                      docs.map((doc) => (
                        <tr
                          key={doc.id}
                          className={`border-b transition-colors ${isDark ? "border-gray-700 hover:bg-gray-750" : "border-gray-100 hover:bg-gray-50"}`}
                        >
                          <td className="px-4 py-3 whitespace-nowrap">{fmtDay(doc.data_emissao)}</td>
                          <td className="px-4 py-3 max-w-[180px]">
                            <div className="truncate" title={doc.emitente_nome}>{doc.emitente_nome || doc.emitente_cnpj}</div>
                            <div className={`text-xs font-mono ${isDark ? "text-gray-400" : "text-gray-500"}`}>{doc.emitente_cnpj}</div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">{doc.municipio_nome || "—"}</td>
                          <td className="px-4 py-3 text-right font-mono whitespace-nowrap">{FMT_BRL.format(doc.valor_total ?? 0)}</td>
                          <td className="px-4 py-3 text-right font-mono whitespace-nowrap">{doc.valor_iss != null ? FMT_BRL.format(doc.valor_iss) : "—"}</td>
                          <td className="px-4 py-3"><StatusBadge status={doc.status} /></td>
                          <td className="px-4 py-3 font-mono text-xs max-w-[120px]">
                            <div className="truncate" title={doc.chave_acesso}>{doc.chave_acesso?.slice(0, 12)}…</div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className={`flex items-center justify-between px-4 py-3 border-t text-sm ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                <span className={isDark ? "text-gray-400" : "text-gray-500"}>
                  {docs.length} registros
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={docsOffset === 0}
                    onClick={() => setDocsOffset(Math.max(0, docsOffset - DOCS_LIMIT))}
                    className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    ← Anterior
                  </button>
                  <button
                    disabled={docs.length < DOCS_LIMIT}
                    onClick={() => setDocsOffset(docsOffset + DOCS_LIMIT)}
                    className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    Próximo →
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════ TAB: SYNC ════════════════════ */}
        {tab === "sync" && (
          <div className="space-y-6">
            {/* Company sync info + trigger */}
            {currentCompany && (
              <div className={`rounded-xl border p-5 ${card}`}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-3">
                    <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                      Status do Sync — {currentCompany.nome}
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className={isDark ? "text-gray-400" : "text-gray-500"}>Token NDD</span>
                        <p className={`mt-0.5 font-medium ${currentCompany.ndd_access_token ? "text-green-500" : "text-red-500"}`}>
                          {currentCompany.ndd_access_token ? "✓ Ativo" : "✗ Não configurado"}
                        </p>
                      </div>
                      <div>
                        <span className={isDark ? "text-gray-400" : "text-gray-500"}>Último sync NFSe</span>
                        <p className="mt-0.5">{fmtDate(currentCompany.ndd_last_sync_at)}</p>
                      </div>
                      <div>
                        <span className={isDark ? "text-gray-400" : "text-gray-500"}>Próximo (agendado)</span>
                        <p className="mt-0.5">05:00 diário</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 items-end">
                    <button
                      onClick={triggerSync}
                      disabled={syncing || !currentCompany.ndd_access_token}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                    >
                      {syncing ? (
                        <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Icon name="zap" size={14} />
                      )}
                      Sync NFSe agora
                    </button>
                    {!currentCompany.ndd_access_token && (
                      <p className="text-xs text-red-500">Configure o token NDD primeiro</p>
                    )}
                  </div>
                </div>
                {syncMsg && (
                  <p className={`mt-3 text-sm p-3 rounded-lg ${syncMsg.includes("Erro") ? "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400" : "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"}`}>
                    {syncMsg}
                  </p>
                )}
              </div>
            )}

            {/* Sync logs */}
            <div className={`rounded-xl border overflow-hidden ${card}`}>
              <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                <h2 className="text-sm font-semibold">Últimos Syncs</h2>
                <button
                  onClick={loadSyncLogs}
                  className={`text-xs px-3 py-1.5 rounded border transition-colors ${isDark ? "border-gray-600 hover:bg-gray-700" : "border-gray-300 hover:bg-gray-50"}`}
                >
                  Atualizar
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className={`border-b text-left ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                      <th className="px-4 py-3 font-medium">Executado em</th>
                      <th className="px-4 py-3 font-medium">Tipo</th>
                      <th className="px-4 py-3 font-medium">Janela</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium text-right">Novos</th>
                      <th className="px-4 py-3 font-medium">Erro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncLoading ? (
                      [...Array(5)].map((_, i) => (
                        <tr key={i} className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                          {[...Array(6)].map((_, j) => (
                            <td key={j} className="px-4 py-3">
                              <div className={`h-4 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : syncLogs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className={`px-4 py-8 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                          Nenhum log de sync encontrado.
                        </td>
                      </tr>
                    ) : (
                      syncLogs.map((log) => (
                        <tr key={log.id} className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs">{fmtDate(log.executado_em)}</td>
                          <td className="px-4 py-3">{log.tipo}</td>
                          <td className="px-4 py-3 text-xs">{log.janela}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              log.status === "ok"      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" :
                              log.status === "parcial" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300" :
                                                         "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                            }`}>
                              {log.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right font-mono">{log.documentos_novos}</td>
                          <td className="px-4 py-3 max-w-[200px]">
                            {log.erro_msg ? (
                              <span className="text-red-500 text-xs truncate block" title={log.erro_msg}>{log.erro_msg.slice(0, 60)}…</span>
                            ) : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
