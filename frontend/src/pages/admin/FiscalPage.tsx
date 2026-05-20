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
  grupo: string | null;
  tipo: string | null;
  cidade: string | null;
  uf_sede: string | null;
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

// ─── Constantes de grupos ────────────────────────────────────────────────────

const GRUPOS: { id: string; label: string; color: string }[] = [
  { id: "vtclog", label: "VTC Operadora Logística",              color: "blue"   },
  { id: "voetur", label: "Voetur Turismo e Representações",      color: "green"  },
  { id: "payfly", label: "Payfly Soluções",                      color: "purple" },
];

const GROUP_COLORS: Record<string, string> = {
  blue:   "bg-blue-600",
  green:  "bg-green-600",
  purple: "bg-purple-600",
};

const GROUP_TEXT: Record<string, string> = {
  blue:   "text-blue-600 dark:text-blue-400",
  green:  "text-green-600 dark:text-green-400",
  purple: "text-purple-600 dark:text-purple-400",
};

const GROUP_BG: Record<string, string> = {
  blue:   "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800",
  green:  "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800",
  purple: "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800",
};

// ─── Formatadores ────────────────────────────────────────────────────────────

const FMT_BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const FMT_NUM = new Intl.NumberFormat("pt-BR");
const fmtDate = (s: string | null) => s ? new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const fmtDay  = (s: string | null) => s ? new Date(s + "T12:00:00").toLocaleDateString("pt-BR") : "—";
const fmtCnpj = (s: string) => s.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");

// ─── Sub-componentes ─────────────────────────────────────────────────────────

function KPICard({ label, value, sub, isDark }: { label: string; value: string; sub?: string; isDark: boolean }) {
  return (
    <div className={`rounded-xl border p-5 flex flex-col gap-1 ${isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
      <span className={`text-xs font-medium uppercase tracking-wide ${isDark ? "text-gray-400" : "text-gray-500"}`}>{label}</span>
      <span className={`text-2xl font-bold ${isDark ? "text-white" : "text-gray-900"}`}>{value}</span>
      {sub && <span className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>{sub}</span>}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  pendente:    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  conferido:   "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  divergencia: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  cancelado:   "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = "dashboard" | "nfse" | "sync";

export default function FiscalPage() {
  const { token } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [tab, setTab] = useState<Tab>("dashboard");
  const [companies, setCompanies] = useState<FiscalCompany[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(["vtclog", "voetur", "payfly"]));

  // period
  const now = new Date();
  const [ano, setAno] = useState(now.getFullYear());
  const [mes, setMes] = useState(now.getMonth() + 1);

  // data states
  const [stats, setStats]           = useState<NfseStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [docs, setDocs]             = useState<NfseDoc[]>([]);
  const [docsLoading, setDocsLoading]   = useState(false);
  const [docsOffset, setDocsOffset] = useState(0);
  const [syncLogs, setSyncLogs]     = useState<SyncLog[]>([]);
  const [syncLoading, setSyncLoading]   = useState(false);
  const [syncing, setSyncing]       = useState(false);
  const [syncMsg, setSyncMsg]       = useState("");

  // NFSe filters
  const [q, setQ]                       = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterMunicipio, setFilterMunicipio] = useState("");
  const [filterCnpj, setFilterCnpj]     = useState("");

  const DOCS_LIMIT = 50;

  // ── Load companies ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token })
      .then((data) => {
        setCompanies(data);
        // Seleciona a matriz VTC por padrão
        const vtcMatriz = data.find((c) => c.grupo === "vtclog" && c.tipo === "matriz");
        if (vtcMatriz) setSelectedId(vtcMatriz.id);
        else if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => {});
  }, [token]);

  const currentCompany = useMemo(
    () => companies.find((c) => c.id === selectedId),
    [companies, selectedId]
  );

  const currentGrupo = useMemo(
    () => GRUPOS.find((g) => g.id === currentCompany?.grupo),
    [currentCompany]
  );

  // ── Grouped companies ─────────────────────────────────────────────────────
  const grouped = useMemo(() => {
    const map: Record<string, FiscalCompany[]> = {};
    for (const c of companies) {
      const g = c.grupo ?? "outros";
      if (!map[g]) map[g] = [];
      map[g].push(c);
    }
    // Ordena: matriz primeiro dentro de cada grupo
    for (const g of Object.values(map)) {
      g.sort((a, b) => (a.tipo === "matriz" ? -1 : b.tipo === "matriz" ? 1 : 0));
    }
    return map;
  }, [companies]);

  // ── Load stats ─────────────────────────────────────────────────────────────
  const loadStats = useCallback(() => {
    if (!token) return;
    setStatsLoading(true);
    const p = new URLSearchParams({ ano: String(ano), mes: String(mes) });
    if (selectedId) p.set("company_id", selectedId);
    apiFetch<NfseStats>(`/api/fiscal/nfse/stats?${p}`, { token })
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [token, ano, mes, selectedId]);

  useEffect(() => { if (tab === "dashboard") loadStats(); }, [tab, loadStats]);

  // ── Load NFSe docs ─────────────────────────────────────────────────────────
  const loadDocs = useCallback(() => {
    if (!token) return;
    setDocsLoading(true);
    const p = new URLSearchParams({ limit: String(DOCS_LIMIT), offset: String(docsOffset) });
    if (selectedId)      p.set("company_id", selectedId);
    if (q)               p.set("q", q);
    if (filterStatus)    p.set("status", filterStatus);
    if (filterMunicipio) p.set("municipio", filterMunicipio);
    if (filterCnpj)      p.set("emitente_cnpj", filterCnpj);
    apiFetch<{ data: NfseDoc[] }>(`/api/fiscal/nfse?${p}`, { token })
      .then((r) => setDocs(r.data ?? []))
      .catch(() => setDocs([]))
      .finally(() => setDocsLoading(false));
  }, [token, selectedId, q, filterStatus, filterMunicipio, filterCnpj, docsOffset]);

  useEffect(() => { if (tab === "nfse") loadDocs(); }, [tab, loadDocs]);

  // ── Load sync logs ─────────────────────────────────────────────────────────
  const loadSyncLogs = useCallback(() => {
    if (!token || !selectedId) return;
    setSyncLoading(true);
    apiFetch<SyncLog[]>(`/api/fiscal/${selectedId}/sync/logs?limit=20`, { token })
      .then(setSyncLogs)
      .catch(() => setSyncLogs([]))
      .finally(() => setSyncLoading(false));
  }, [token, selectedId]);

  useEffect(() => { if (tab === "sync") loadSyncLogs(); }, [tab, loadSyncLogs]);

  // ── Trigger sync ───────────────────────────────────────────────────────────
  const triggerSync = async () => {
    if (!token || syncing) return;
    setSyncing(true); setSyncMsg("");
    try {
      await apiFetch("/api/fiscal/nfse/sync/run", { token, method: "POST" });
      setSyncMsg("Sync NFSe iniciado — aguarde alguns minutos e clique Atualizar.");
      setTimeout(() => loadSyncLogs(), 6000);
    } catch {
      setSyncMsg("Erro ao iniciar sync. Verifique se o token NDD está configurado.");
    } finally {
      setSyncing(false);
    }
  };

  const toggleGroup = (g: string) =>
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      next.has(g) ? next.delete(g) : next.add(g);
      return next;
    });

  // ── Styles ─────────────────────────────────────────────────────────────────
  const base  = isDark ? "bg-gray-900 text-gray-100" : "bg-gray-50 text-gray-900";
  const card  = isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200";
  const side  = isDark ? "bg-gray-850 border-gray-700" : "bg-white border-gray-200";
  const inp   = `border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${isDark ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400" : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"}`;
  const tabCls = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${tab === t
      ? isDark ? "bg-gray-700 text-white" : "bg-white text-gray-900 shadow"
      : isDark ? "text-gray-400 hover:text-gray-200" : "text-gray-500 hover:text-gray-700"}`;

  const MONTHS = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className={`${base} min-h-screen`}>
      <div className="max-w-[1440px] mx-auto flex gap-0">

        {/* ══════════ SIDEBAR ══════════ */}
        <aside className={`w-64 shrink-0 border-r min-h-screen ${side}`}>
          <div className={`px-4 py-5 border-b ${isDark ? "border-gray-700" : "border-gray-200"}`}>
            <h1 className="font-bold text-base">Validação NFe/NFSe</h1>
            <p className={`text-xs mt-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>Selecione uma empresa</p>
          </div>

          <nav className="py-2">
            {GRUPOS.map(({ id: gid, label, color }) => {
              const items = grouped[gid] ?? [];
              if (items.length === 0) return null;
              const expanded = expandedGroups.has(gid);
              return (
                <div key={gid}>
                  {/* Grupo header */}
                  <button
                    onClick={() => toggleGroup(gid)}
                    className={`w-full flex items-center justify-between px-4 py-2.5 text-left hover:${isDark ? "bg-gray-800" : "bg-gray-50"} transition-colors`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${GROUP_COLORS[color]}`} />
                      <span className={`text-xs font-semibold uppercase tracking-wide ${GROUP_TEXT[color]}`}>{gid === "vtclog" ? "VTC" : gid === "voetur" ? "Voetur" : "Payfly"}</span>
                    </div>
                    <svg
                      className={`w-3 h-3 transition-transform ${isDark ? "text-gray-500" : "text-gray-400"} ${expanded ? "rotate-90" : ""}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="m9 6 6 6-6 6" />
                    </svg>
                  </button>

                  {/* Company items */}
                  {expanded && items.map((c) => {
                    const isSelected = c.id === selectedId;
                    const isPayfly = c.grupo === "payfly";
                    return (
                      <button
                        key={c.id}
                        onClick={() => setSelectedId(c.id)}
                        className={`w-full text-left px-4 py-2.5 pl-8 transition-colors border-l-2 ${
                          isSelected
                            ? `border-l-${color}-500 ${isDark ? `bg-${color}-900/20` : `bg-${color}-50`} ${GROUP_TEXT[color]}`
                            : `border-transparent ${isDark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-50 text-gray-600"}`
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-medium leading-tight">
                            {c.cidade ?? c.uf_sede ?? "—"}
                          </span>
                          {c.tipo === "matriz" && (
                            <span className={`text-[10px] px-1 rounded font-medium ${isDark ? "bg-gray-700 text-gray-400" : "bg-gray-100 text-gray-500"}`}>MTZ</span>
                          )}
                          {isPayfly && (
                            <span className="text-[10px] px-1 rounded font-medium bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">sem cert</span>
                          )}
                        </div>
                        <div className={`text-[11px] font-mono mt-0.5 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                          {fmtCnpj(c.cnpj)}
                        </div>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* ══════════ MAIN CONTENT ══════════ */}
        <main className="flex-1 min-w-0 p-6 space-y-5">

          {/* Header da empresa selecionada */}
          {currentCompany && (
            <div className={`rounded-xl border px-5 py-4 flex flex-wrap items-center justify-between gap-3 ${
              currentGrupo ? GROUP_BG[currentGrupo.color] : card
            }`}>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-lg">{currentCompany.cidade ?? currentCompany.uf_sede}</span>
                  {currentCompany.tipo === "matriz" && (
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${isDark ? "bg-gray-700 text-gray-300" : "bg-white/60 text-gray-600"}`}>Matriz</span>
                  )}
                  {currentCompany.tipo === "filial" && (
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${isDark ? "bg-gray-700 text-gray-300" : "bg-white/60 text-gray-600"}`}>Filial</span>
                  )}
                </div>
                <p className={`text-sm mt-0.5 ${isDark ? "text-gray-300" : "text-gray-600"}`}>
                  {currentCompany.nome} · <span className="font-mono">{fmtCnpj(currentCompany.cnpj)}</span>
                </p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                {currentCompany.sync_nfe_ativo && <span className="flex items-center gap-1 text-green-600 dark:text-green-400"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />NFe</span>}
                {currentCompany.sync_cte_ativo && <span className="flex items-center gap-1 text-green-600 dark:text-green-400"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />CTe</span>}
                {currentCompany.sync_nfse_ativo && <span className="flex items-center gap-1 text-green-600 dark:text-green-400"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />NFSe</span>}
                {!currentCompany.sync_nfe_ativo && !currentCompany.sync_cte_ativo && !currentCompany.sync_nfse_ativo && (
                  <span className="text-yellow-600 dark:text-yellow-400 text-xs">Sync não configurado</span>
                )}
              </div>
            </div>
          )}

          {/* Aviso Payfly */}
          {currentCompany?.grupo === "payfly" && (
            <div className="rounded-xl border border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 px-5 py-4">
              <p className="text-sm text-yellow-800 dark:text-yellow-300 font-medium">
                Certificado A1 da Payfly ainda não configurado — sync desativado.
              </p>
              <p className="text-xs text-yellow-700 dark:text-yellow-400 mt-1">
                Após receber o certificado, faça upload em <code className="font-mono">POST /api/fiscal/{currentCompany.id}/certificates</code> para ativar.
              </p>
            </div>
          )}

          {/* Tabs */}
          <div className={`flex gap-1 p-1 rounded-xl w-fit ${isDark ? "bg-gray-800" : "bg-gray-100"}`}>
            <button className={tabCls("dashboard")} onClick={() => setTab("dashboard")}>Dashboard</button>
            <button className={tabCls("nfse")}      onClick={() => setTab("nfse")}>NFSe</button>
            <button className={tabCls("sync")}       onClick={() => setTab("sync")}>Sync</button>
          </div>

          {/* ════ TAB: DASHBOARD ════ */}
          {tab === "dashboard" && (
            <div className="space-y-5">
              <div className="flex flex-wrap gap-3 items-center">
                <select value={ano} onChange={(e) => setAno(+e.target.value)} className={`${inp} w-24`}>
                  {[now.getFullYear()-1, now.getFullYear()].map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
                <select value={mes} onChange={(e) => setMes(+e.target.value)} className={`${inp} w-28`}>
                  {MONTHS.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
                </select>
                <button onClick={loadStats} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Atualizar</button>
              </div>

              {statsLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[...Array(4)].map((_, i) => <div key={i} className={`rounded-xl border p-5 h-24 animate-pulse ${card}`} />)}
                </div>
              ) : stats ? (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <KPICard label="Total NFSe"  value={FMT_NUM.format(stats.total_notas)}  isDark={isDark} />
                    <KPICard label="Valor Total" value={FMT_BRL.format(stats.valor_total)}  isDark={isDark} />
                    <KPICard label="ISS"         value={FMT_BRL.format(stats.valor_iss)}    isDark={isDark} />
                    <KPICard
                      label="Pendentes"
                      value={FMT_NUM.format(stats.por_status?.pendente ?? 0)}
                      sub={`Conferidos: ${FMT_NUM.format(stats.por_status?.conferido ?? 0)}`}
                      isDark={isDark}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div className={`rounded-xl border p-5 ${card}`}>
                      <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>Por Status</h2>
                      {Object.keys(stats.por_status).length === 0
                        ? <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Sem dados.</p>
                        : Object.entries(stats.por_status).map(([s, n]) => (
                          <div key={s} className="flex items-center justify-between gap-3 mb-2">
                            <StatusBadge status={s} />
                            <span className="font-mono text-sm font-medium">{FMT_NUM.format(n)}</span>
                          </div>
                        ))
                      }
                    </div>
                    <div className={`rounded-xl border p-5 ${card}`}>
                      <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>Top Municípios</h2>
                      {Object.entries(stats.por_municipio).sort(([,a],[,b]) => b-a).slice(0,8).map(([m, n]) => (
                        <div key={m} className="flex items-center justify-between gap-2 mb-2">
                          <span className={`text-sm truncate ${isDark ? "text-gray-300" : "text-gray-700"}`}>{m || "—"}</span>
                          <span className="font-mono text-sm font-medium shrink-0">{FMT_NUM.format(n)}</span>
                        </div>
                      ))}
                      {Object.keys(stats.por_municipio).length === 0 && <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Sem dados.</p>}
                    </div>
                  </div>
                </>
              ) : (
                <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Nenhum dado para o período selecionado.</p>
              )}
            </div>
          )}

          {/* ════ TAB: NFSe ════ */}
          {tab === "nfse" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <input type="text" placeholder="Busca full-text (emitente, município...)" value={q}
                  onChange={(e) => { setQ(e.target.value); setDocsOffset(0); }}
                  className={`${inp} flex-1 min-w-[200px]`} />
                <input type="text" placeholder="CNPJ emitente" value={filterCnpj}
                  onChange={(e) => { setFilterCnpj(e.target.value); setDocsOffset(0); }}
                  className={`${inp} w-40 font-mono`} />
                <input type="text" placeholder="Município" value={filterMunicipio}
                  onChange={(e) => { setFilterMunicipio(e.target.value); setDocsOffset(0); }}
                  className={`${inp} w-36`} />
                <select value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setDocsOffset(0); }} className={`${inp} w-36`}>
                  <option value="">Todos status</option>
                  <option value="pendente">Pendente</option>
                  <option value="conferido">Conferido</option>
                  <option value="divergencia">Divergência</option>
                  <option value="cancelado">Cancelado</option>
                </select>
                <button onClick={() => { setDocsOffset(0); loadDocs(); }}
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Buscar</button>
              </div>

              <div className={`rounded-xl border overflow-hidden ${card}`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className={`border-b text-left ${isDark ? "border-gray-700 bg-gray-900/40" : "border-gray-200 bg-gray-50"}`}>
                        <th className="px-4 py-3 font-medium">Data</th>
                        <th className="px-4 py-3 font-medium">Emitente</th>
                        <th className="px-4 py-3 font-medium">Município</th>
                        <th className="px-4 py-3 font-medium text-right">Valor</th>
                        <th className="px-4 py-3 font-medium text-right">ISS</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium text-xs font-mono">Chave</th>
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
                        <tr><td colSpan={7} className={`px-4 py-10 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                          Nenhuma NFSe encontrada.
                        </td></tr>
                      ) : docs.map((doc) => (
                        <tr key={doc.id} className={`border-b transition-colors ${isDark ? "border-gray-700 hover:bg-gray-800/50" : "border-gray-100 hover:bg-gray-50"}`}>
                          <td className="px-4 py-3 whitespace-nowrap">{fmtDay(doc.data_emissao)}</td>
                          <td className="px-4 py-3 max-w-[180px]">
                            <div className="truncate" title={doc.emitente_nome}>{doc.emitente_nome || doc.emitente_cnpj}</div>
                            <div className={`text-xs font-mono ${isDark ? "text-gray-400" : "text-gray-400"}`}>{fmtCnpj(doc.emitente_cnpj)}</div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">{doc.municipio_nome || "—"}</td>
                          <td className="px-4 py-3 text-right font-mono whitespace-nowrap">{FMT_BRL.format(doc.valor_total ?? 0)}</td>
                          <td className="px-4 py-3 text-right font-mono whitespace-nowrap">{doc.valor_iss != null ? FMT_BRL.format(doc.valor_iss) : "—"}</td>
                          <td className="px-4 py-3"><StatusBadge status={doc.status} /></td>
                          <td className="px-4 py-3 font-mono text-xs">
                            <span title={doc.chave_acesso}>{doc.chave_acesso?.slice(0, 10)}…</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={`flex items-center justify-between px-4 py-3 border-t text-sm ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                  <span className={isDark ? "text-gray-400" : "text-gray-500"}>{docs.length} registros</span>
                  <div className="flex gap-2">
                    <button disabled={docsOffset === 0} onClick={() => setDocsOffset(Math.max(0, docsOffset - DOCS_LIMIT))}
                      className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">← Anterior</button>
                    <button disabled={docs.length < DOCS_LIMIT} onClick={() => setDocsOffset(docsOffset + DOCS_LIMIT)}
                      className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Próximo →</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ════ TAB: SYNC ════ */}
          {tab === "sync" && (
            <div className="space-y-5">
              {currentCompany && (
                <div className={`rounded-xl border p-5 ${card}`}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-3">
                      <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>Status do Sync</h2>
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
                          <span className={isDark ? "text-gray-400" : "text-gray-500"}>Próximo agendado</span>
                          <p className="mt-0.5">05:00 diário</p>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={triggerSync}
                      disabled={syncing || !currentCompany.ndd_access_token}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                    >
                      {syncing
                        ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        : <Icon name="zap" size={14} />}
                      Sync NFSe agora
                    </button>
                  </div>
                  {syncMsg && (
                    <p className={`mt-3 text-sm p-3 rounded-lg ${syncMsg.includes("Erro") ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400" : "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"}`}>
                      {syncMsg}
                    </p>
                  )}
                </div>
              )}

              <div className={`rounded-xl border overflow-hidden ${card}`}>
                <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                  <h2 className="text-sm font-semibold">Últimos Syncs</h2>
                  <button onClick={loadSyncLogs} className={`text-xs px-3 py-1.5 rounded border ${isDark ? "border-gray-600 hover:bg-gray-700" : "border-gray-300 hover:bg-gray-50"}`}>
                    Atualizar
                  </button>
                </div>
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
                          {[...Array(6)].map((_, j) => <td key={j} className="px-4 py-3"><div className={`h-4 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} /></td>)}
                        </tr>
                      ))
                    ) : syncLogs.length === 0 ? (
                      <tr><td colSpan={6} className={`px-4 py-10 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Nenhum log de sync ainda.</td></tr>
                    ) : syncLogs.map((log) => (
                      <tr key={log.id} className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{fmtDate(log.executado_em)}</td>
                        <td className="px-4 py-3">{log.tipo}</td>
                        <td className="px-4 py-3 text-xs">{log.janela}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            log.status === "ok"      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" :
                            log.status === "parcial" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300" :
                                                       "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                          }`}>{log.status}</span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{log.documentos_novos}</td>
                        <td className="px-4 py-3 max-w-[200px]">
                          {log.erro_msg ? <span className="text-red-500 text-xs truncate block" title={log.erro_msg}>{log.erro_msg.slice(0, 60)}…</span> : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
