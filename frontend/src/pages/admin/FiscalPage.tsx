import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import { apiFetch } from "../../lib/api";
import Icon from "../../components/Icon";

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface FiscalCompany {
  id: string;
  cnpj: string;
  nome: string;
  grupo: string | null;
  tipo: string | null;
  cidade: string | null;
  uf_sede: string | null;
  sync_nfe_ativo: boolean;
  sync_cte_ativo: boolean;
  sync_nfse_ativo: boolean;
  ndd_last_sync_at: string | null;
  ndd_access_token: string | null;
  ndd_refresh_token: string | null;
  ndd_token_expires_at: string | null;
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
  numero: string | null;
  serie: string | null;
  emitente_cnpj: string;
  emitente_nome: string;
  destinatario_cnpj: string;
  destinatario_nome: string;
  natureza_operacao: string | null;
  data_emissao: string;
  valor_total: number;
  valor_iss: number | null;
  valor_iss_retido: number | null;
  municipio_nome: string;
  status: string;
  ndd_id: number | null;
  ndd_sync_at: string | null;
  xml_content?: string | null;
}

interface SyncLog {
  id: string;
  tipo: string;
  status: string;
  documentos_novos: number;
  erro_msg: string | null;
  janela: string;
  executado_em: string;
}

// ─── Constantes ───────────────────────────────────────────────────────────────

const GRUPO_LABEL: Record<string, string> = {
  vtclog: "VTC Operadora Logística",
  voetur: "Voetur Turismo",
  payfly: "Payfly",
};

const FMT_BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const FMT_NUM = new Intl.NumberFormat("pt-BR");
const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const fmtDay = (s: string | null) =>
  s ? new Date(s + "T12:00:00").toLocaleDateString("pt-BR") : "—";
const fmtCnpj = (s: string) =>
  s.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");

const STATUS_BADGE: Record<string, string> = {
  pendente:    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  conferido:   "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  divergencia: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  cancelado:   "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

function Badge({ label, cls }: { label: string; cls: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

function KPICard({
  label, value, sub, isDark,
}: {
  label: string; value: string; sub?: string; isDark: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 flex flex-col gap-1 ${
        isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
      }`}
    >
      <span className={`text-xs font-medium uppercase tracking-wide ${isDark ? "text-gray-400" : "text-gray-500"}`}>
        {label}
      </span>
      <span className={`text-2xl font-bold ${isDark ? "text-white" : "text-gray-900"}`}>{value}</span>
      {sub && <span className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>{sub}</span>}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = "dashboard" | "nfse" | "sync";
const MONTHS = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
const DOCS_LIMIT = 50;

export default function FiscalPage() {
  const { token } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const cache = useRef<Map<string, { data: unknown; ts: number }>>(new Map());
  const cached = <T,>(key: string, ttl = 120_000): T | null => {
    const e = cache.current.get(key);
    return e && Date.now() - e.ts < ttl ? (e.data as T) : null;
  };
  const setCache = (key: string, data: unknown) =>
    cache.current.set(key, { data, ts: Date.now() });

  const [tab, setTab]           = useState<Tab>("dashboard");
  const [companies, setCompanies] = useState<FiscalCompany[]>([]);
  // "" = todas as empresas
  const [selectedId, setSelectedId] = useState<string>("");

  const now = new Date();
  const [ano, setAno] = useState(now.getFullYear());
  const [mes, setMes] = useState(now.getMonth() + 1);

  // dashboard
  const [stats, setStats]             = useState<NfseStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // nfse
  const [docs, setDocs]             = useState<NfseDoc[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsOffset, setDocsOffset] = useState(0);
  const [q, setQ]                   = useState("");
  const [filterStatus, setFilterStatus]     = useState("");
  const [filterMunicipio, setFilterMunicipio] = useState("");
  const [filterCnpj, setFilterCnpj]         = useState("");

  // drill-down
  const [detailDoc, setDetailDoc]       = useState<NfseDoc | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // sync
  const [syncLogs, setSyncLogs]         = useState<SyncLog[]>([]);
  const [syncLoading, setSyncLoading]   = useState(false);
  const [syncing, setSyncing]           = useState(false);
  const [syncMsg, setSyncMsg]           = useState("");

  // ── Load companies ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token })
      .then(setCompanies)
      .catch(() => {});
  }, [token]);

  const currentCompany = useMemo(
    () => companies.find((c) => c.id === selectedId),
    [companies, selectedId]
  );

  // Agrupa para o <select> — mantém ordem: vtclog, voetur, payfly, outros
  const grouped = useMemo(() => {
    const order = ["vtclog", "voetur", "payfly"];
    const map: Record<string, FiscalCompany[]> = {};
    for (const c of companies) {
      const g = c.grupo ?? "outros";
      (map[g] ??= []).push(c);
    }
    for (const arr of Object.values(map)) {
      arr.sort((a, b) => (a.tipo === "matriz" ? -1 : b.tipo === "matriz" ? 1 : 0));
    }
    return [...order, ...Object.keys(map).filter((k) => !order.includes(k))]
      .filter((k) => map[k])
      .map((k) => ({ key: k, items: map[k] }));
  }, [companies]);

  // ── Load stats ──────────────────────────────────────────────────────────────
  const loadStats = useCallback(() => {
    if (!token) return;
    const p = new URLSearchParams({ ano: String(ano), mes: String(mes) });
    if (selectedId) p.set("company_id", selectedId);
    const key = `stats:${p}`;
    const hit = cached<NfseStats>(key);
    if (hit) { setStats(hit); return; }
    setStatsLoading(true);
    apiFetch<NfseStats>(`/api/fiscal/nfse/stats?${p}`, { token })
      .then((d) => { setStats(d); setCache(key, d); })
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [token, ano, mes, selectedId]);

  useEffect(() => { if (tab === "dashboard") loadStats(); }, [tab, loadStats]);

  // ── Load docs ───────────────────────────────────────────────────────────────
  const loadDocs = useCallback(() => {
    if (!token) return;
    const p = new URLSearchParams({ limit: String(DOCS_LIMIT), offset: String(docsOffset) });
    if (selectedId)      p.set("company_id", selectedId);
    if (q)               p.set("q", q);
    if (filterStatus)    p.set("status", filterStatus);
    if (filterMunicipio) p.set("municipio", filterMunicipio);
    if (filterCnpj)      p.set("emitente_cnpj", filterCnpj);
    const key = `docs:${p}`;
    const hit = cached<NfseDoc[]>(key, 60_000);
    if (hit) { setDocs(hit); return; }
    setDocsLoading(true);
    apiFetch<{ data: NfseDoc[] }>(`/api/fiscal/nfse?${p}`, { token })
      .then((r) => { const d = r.data ?? []; setDocs(d); setCache(key, d); })
      .catch(() => setDocs([]))
      .finally(() => setDocsLoading(false));
  }, [token, selectedId, q, filterStatus, filterMunicipio, filterCnpj, docsOffset]);

  useEffect(() => { if (tab === "nfse") loadDocs(); }, [tab, loadDocs]);

  // ── Load sync logs ──────────────────────────────────────────────────────────
  const loadSyncLogs = useCallback(() => {
    if (!token) return;
    const url = selectedId
      ? `/api/fiscal/${selectedId}/sync/logs?limit=30`
      : `/api/fiscal/sync/logs?limit=30`;
    const key = `logs:${selectedId}`;
    const hit = cached<SyncLog[]>(key, 30_000);
    if (hit) { setSyncLogs(hit); return; }
    setSyncLoading(true);
    apiFetch<SyncLog[]>(url, { token })
      .then((d) => { setSyncLogs(d); setCache(key, d); })
      .catch(() => setSyncLogs([]))
      .finally(() => setSyncLoading(false));
  }, [token, selectedId]);

  useEffect(() => { if (tab === "sync") loadSyncLogs(); }, [tab, loadSyncLogs]);

  // ── Drill-down ──────────────────────────────────────────────────────────────
  const openDetail = async (doc: NfseDoc) => {
    setDetailDoc(doc);
    if (doc.xml_content) return;
    setDetailLoading(true);
    try {
      const full = await apiFetch<NfseDoc>(`/api/fiscal/nfse/${doc.id}`, { token: token! });
      setDetailDoc(full);
    } catch {/* mostra o que temos */} finally {
      setDetailLoading(false);
    }
  };

  // ── Configurar token NDD manualmente (via DevTools do portal NDD) ───────────
  const [showTokenForm, setShowTokenForm] = useState(false);
  const [nddAccessToken, setNddAccessToken]   = useState("");
  const [nddRefreshToken, setNddRefreshToken] = useState("");
  const [savingToken, setSavingToken]         = useState(false);
  const [nddMsg, setNddMsg]                   = useState("");

  const saveNddToken = async () => {
    if (!token) return;
    const nddCompany = companies.find((c) => c.sync_nfse_ativo);
    if (!nddCompany) { setNddMsg("Nenhuma empresa com sync NFSe ativo."); return; }
    if (!nddAccessToken.trim()) { setNddMsg("Cole o access_token."); return; }
    setSavingToken(true);
    setNddMsg("");
    try {
      await apiFetch(`/api/fiscal/${nddCompany.id}/ndd/token`, {
        token,
        method: "POST",
        json: {
          access_token:  nddAccessToken.trim(),
          refresh_token: nddRefreshToken.trim(),
          expires_in:    1800,
        },
      });
      setNddMsg(
        nddRefreshToken.trim()
          ? "✅ Tokens salvos! Renovação automática ativada — não precisa fazer isso de novo."
          : "⚠️ access_token salvo. Sem refresh_token: expira em 30 min. Cole também o refresh_token para renovação automática."
      );
      setNddAccessToken("");
      setNddRefreshToken("");
      setShowTokenForm(false);
      apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token }).then(setCompanies).catch(() => {});
    } catch (err) {
      setNddMsg(`Erro: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSavingToken(false);
    }
  };

  // ── Trigger sync ────────────────────────────────────────────────────────────
  const triggerSync = async () => {
    if (!token || syncing) return;
    setSyncing(true);
    setSyncMsg("");
    try {
      await apiFetch("/api/fiscal/nfse/sync/run", { token, method: "POST" });
      setSyncMsg("Sync NFSe iniciado — aguarde alguns minutos e clique Atualizar.");
      setTimeout(() => loadSyncLogs(), 6000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSyncMsg(`Erro: ${msg}`);
    } finally {
      setSyncing(false);
    }
  };

  // ── Estilos compartilhados ──────────────────────────────────────────────────
  const card = isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200";
  const inp  = `border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    isDark
      ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400"
      : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`;
  const tabCls = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      tab === t
        ? isDark ? "bg-gray-700 text-white" : "bg-white text-gray-900 shadow"
        : isDark ? "text-gray-400 hover:text-gray-200" : "text-gray-500 hover:text-gray-700"
    }`;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 p-6 max-w-7xl mx-auto">

      {/* ── Cabeçalho + Filtro de empresa ── */}
      <div className={`rounded-xl border p-5 ${card}`}>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[220px]">
            <h1 className={`text-lg font-bold ${isDark ? "text-white" : "text-gray-900"}`}>
              Validação NFe / NFSe
            </h1>
            <p className={`text-sm mt-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>
              Documentos fiscais sincronizados via NDD Digital
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            {/* Seletor de empresa */}
            <div className="flex flex-col gap-1">
              <label className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                Empresa
              </label>
              <select
                value={selectedId}
                onChange={(e) => { setSelectedId(e.target.value); setDocsOffset(0); }}
                className={`${inp} min-w-[240px]`}
              >
                <option value="">Todas as empresas</option>
                {grouped.map(({ key, items }) => (
                  <optgroup key={key} label={GRUPO_LABEL[key] ?? key}>
                    {items.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.cidade ?? c.uf_sede ?? c.cnpj}
                        {c.tipo === "matriz" ? " (Matriz)" : ""}
                        {" — "}
                        {fmtCnpj(c.cnpj)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {/* Indicadores de sync da empresa selecionada */}
            {currentCompany && (
              <div className="flex items-center gap-2 pb-0.5">
                {currentCompany.sync_nfe_ativo && (
                  <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />NFe
                  </span>
                )}
                {currentCompany.sync_cte_ativo && (
                  <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />CTe
                  </span>
                )}
                {currentCompany.sync_nfse_ativo && (
                  <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />NFSe
                  </span>
                )}
                {currentCompany.grupo === "payfly" && (
                  <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">
                    ⚠ Sem certificado A1
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className={`flex gap-1 p-1 rounded-xl w-fit ${isDark ? "bg-gray-800" : "bg-gray-100"}`}>
        <button className={tabCls("dashboard")} onClick={() => setTab("dashboard")}>Dashboard</button>
        <button className={tabCls("nfse")}      onClick={() => setTab("nfse")}>NFSe</button>
        <button className={tabCls("sync")}      onClick={() => setTab("sync")}>Sync</button>
      </div>

      {/* ════ TAB: DASHBOARD ════ */}
      {tab === "dashboard" && (
        <div className="space-y-5">

          {/* Cards resumo da empresa selecionada (ano corrente) */}
          {currentCompany && stats && (
            <div className={`rounded-xl border p-5 space-y-3 ${card}`}>
              <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                {currentCompany.nome} — {ano}
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
            </div>
          )}

          {/* Filtro de período */}
          <div className={`rounded-xl border p-4 flex flex-wrap gap-3 items-end ${card}`}>
            <div className="flex flex-col gap-1">
              <label className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>Ano</label>
              <select value={ano} onChange={(e) => setAno(+e.target.value)} className={`${inp} w-24`}>
                {[now.getFullYear() - 1, now.getFullYear()].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>Mês</label>
              <select value={mes} onChange={(e) => setMes(+e.target.value)} className={`${inp} w-28`}>
                {MONTHS.map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </select>
            </div>
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
                  <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                    Por Status
                  </h2>
                  {Object.keys(stats.por_status).length === 0 ? (
                    <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Sem dados.</p>
                  ) : (
                    Object.entries(stats.por_status).map(([s, n]) => (
                      <div key={s} className="flex items-center justify-between gap-3 mb-2">
                        <Badge label={s} cls={STATUS_BADGE[s] ?? "bg-gray-100 text-gray-600"} />
                        <span className="font-mono text-sm font-medium">{FMT_NUM.format(n)}</span>
                      </div>
                    ))
                  )}
                </div>
                <div className={`rounded-xl border p-5 ${card}`}>
                  <h2 className={`text-sm font-semibold mb-4 ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                    Top Municípios
                  </h2>
                  {Object.entries(stats.por_municipio)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 8)
                    .map(([m, n]) => (
                      <div key={m} className="flex items-center justify-between gap-2 mb-2">
                        <span className={`text-sm truncate ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                          {m || "—"}
                        </span>
                        <span className="font-mono text-sm font-medium shrink-0">{FMT_NUM.format(n)}</span>
                      </div>
                    ))}
                  {Object.keys(stats.por_municipio).length === 0 && (
                    <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>Sem dados.</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
              Nenhum dado para o período selecionado.
            </p>
          )}
        </div>
      )}

      {/* ════ TAB: NFSe ════ */}
      {tab === "nfse" && (
        <div className="space-y-4">
          {/* Filtros */}
          <div className={`rounded-xl border p-4 ${card}`}>
            <div className="flex flex-wrap gap-3">
              <input
                type="text"
                placeholder="Busca full-text (emitente, município...)"
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
          </div>

          {/* Lista de cards */}
          <div className={`rounded-xl border overflow-hidden ${card}`}>
            {docsLoading ? (
              <div className="divide-y divide-gray-700">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="p-4 flex justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      <div className={`h-3 w-24 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                      <div className={`h-4 w-2/3 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                      <div className={`h-3 w-1/2 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                    </div>
                    <div className="space-y-2 text-right">
                      <div className={`h-5 w-28 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                      <div className={`h-3 w-20 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                    </div>
                  </div>
                ))}
              </div>
            ) : docs.length === 0 ? (
              <p className={`px-4 py-12 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                Nenhuma NFSe encontrada.
              </p>
            ) : (
              <div className={`divide-y ${isDark ? "divide-gray-700" : "divide-gray-100"}`}>
                {docs.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => openDetail(doc)}
                    className={`p-4 cursor-pointer transition-colors ${
                      isDark ? "hover:bg-gray-700/50" : "hover:bg-blue-50/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center flex-wrap gap-2 mb-1">
                          <span className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                            {fmtDay(doc.data_emissao)}
                          </span>
                          <Badge label={doc.status} cls={STATUS_BADGE[doc.status] ?? "bg-gray-100 text-gray-600"} />
                          {doc.municipio_nome && (
                            <span className={`text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                              · {doc.municipio_nome}
                            </span>
                          )}
                        </div>
                        <p className={`font-semibold text-base leading-tight truncate ${isDark ? "text-white" : "text-gray-900"}`}
                          title={doc.emitente_nome}>
                          {doc.emitente_nome || doc.emitente_cnpj}
                        </p>
                        <p className={`text-xs font-mono mt-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                          {fmtCnpj(doc.emitente_cnpj)}
                        </p>
                        {doc.destinatario_nome && (
                          <p className={`text-xs mt-0.5 truncate ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                            → {doc.destinatario_nome}
                          </p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className={`font-bold text-base tabular-nums ${isDark ? "text-white" : "text-gray-900"}`}>
                          {FMT_BRL.format(doc.valor_total ?? 0)}
                        </p>
                        {doc.valor_iss != null && (
                          <p className={`text-xs mt-0.5 tabular-nums ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                            ISS {FMT_BRL.format(doc.valor_iss)}
                          </p>
                        )}
                        <p className={`text-xs mt-1.5 font-mono ${isDark ? "text-gray-600" : "text-gray-400"}`}>
                          {doc.chave_acesso?.slice(0, 12)}…
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className={`flex items-center justify-between px-4 py-3 border-t text-sm ${isDark ? "border-gray-700" : "border-gray-200"}`}>
              <span className={isDark ? "text-gray-400" : "text-gray-500"}>{docs.length} registros · clique para detalhar</span>
              <div className="flex gap-2">
                <button
                  disabled={docsOffset === 0}
                  onClick={() => setDocsOffset(Math.max(0, docsOffset - DOCS_LIMIT))}
                  className={`px-3 py-1 rounded border text-sm disabled:opacity-40 transition-colors ${
                    isDark ? "border-gray-600 hover:bg-gray-700 text-gray-300" : "border-gray-300 hover:bg-gray-50 text-gray-700"
                  }`}
                >← Anterior</button>
                <button
                  disabled={docs.length < DOCS_LIMIT}
                  onClick={() => setDocsOffset(docsOffset + DOCS_LIMIT)}
                  className={`px-3 py-1 rounded border text-sm disabled:opacity-40 transition-colors ${
                    isDark ? "border-gray-600 hover:bg-gray-700 text-gray-300" : "border-gray-300 hover:bg-gray-50 text-gray-700"
                  }`}
                >Próximo →</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ════ MODAL DETALHE NFSe ════ */}
      {detailDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setDetailDoc(null)}
        >
          <div
            className={`rounded-2xl border shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto ${
              isDark ? "bg-gray-900 border-gray-700 text-gray-200" : "bg-white border-gray-200 text-gray-900"
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b"
              style={{ background: isDark ? "#111827" : "#fff" }}>
              <div>
                <h2 className="font-bold text-base">NFSe — Detalhes</h2>
                {detailDoc.numero && (
                  <p className={`text-xs mt-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                    Nº {detailDoc.numero}{detailDoc.serie ? ` · Série ${detailDoc.serie}` : ""}
                  </p>
                )}
              </div>
              <button
                onClick={() => setDetailDoc(null)}
                className={`p-2 rounded-lg transition-colors ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-100"}`}
              >
                <Icon name="x" size={16} />
              </button>
            </div>

            <div className="p-5 space-y-5">
              {/* Status + Data */}
              <div className="flex items-center gap-3">
                <Badge label={detailDoc.status} cls={STATUS_BADGE[detailDoc.status] ?? "bg-gray-100 text-gray-600"} />
                <span className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                  Emitida em {fmtDay(detailDoc.data_emissao)}
                </span>
                {detailDoc.municipio_nome && (
                  <span className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                    · {detailDoc.municipio_nome}
                  </span>
                )}
              </div>

              {/* Emitente / Destinatário */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className={`rounded-xl p-4 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDark ? "text-gray-500" : "text-gray-400"}`}>Emitente (Prestador)</p>
                  <p className="font-semibold leading-snug">{detailDoc.emitente_nome || "—"}</p>
                  <p className={`text-xs font-mono mt-1 ${isDark ? "text-gray-400" : "text-gray-500"}`}>{fmtCnpj(detailDoc.emitente_cnpj)}</p>
                </div>
                <div className={`rounded-xl p-4 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDark ? "text-gray-500" : "text-gray-400"}`}>Destinatário (Tomador)</p>
                  <p className="font-semibold leading-snug">{detailDoc.destinatario_nome || "—"}</p>
                  <p className={`text-xs font-mono mt-1 ${isDark ? "text-gray-400" : "text-gray-500"}`}>{fmtCnpj(detailDoc.destinatario_cnpj)}</p>
                </div>
              </div>

              {/* Valores */}
              <div className="grid grid-cols-3 gap-3">
                <div className={`rounded-xl p-4 text-center ${isDark ? "bg-blue-900/30 border border-blue-800/40" : "bg-blue-50 border border-blue-100"}`}>
                  <p className={`text-xs mb-1 ${isDark ? "text-blue-400" : "text-blue-600"}`}>Valor Total</p>
                  <p className={`font-bold text-lg tabular-nums ${isDark ? "text-white" : "text-gray-900"}`}>
                    {FMT_BRL.format(detailDoc.valor_total ?? 0)}
                  </p>
                </div>
                <div className={`rounded-xl p-4 text-center ${isDark ? "bg-yellow-900/20 border border-yellow-800/30" : "bg-yellow-50 border border-yellow-100"}`}>
                  <p className={`text-xs mb-1 ${isDark ? "text-yellow-400" : "text-yellow-600"}`}>ISS</p>
                  <p className={`font-bold text-lg tabular-nums ${isDark ? "text-white" : "text-gray-900"}`}>
                    {detailDoc.valor_iss != null ? FMT_BRL.format(detailDoc.valor_iss) : "—"}
                  </p>
                </div>
                <div className={`rounded-xl p-4 text-center ${isDark ? "bg-orange-900/20 border border-orange-800/30" : "bg-orange-50 border border-orange-100"}`}>
                  <p className={`text-xs mb-1 ${isDark ? "text-orange-400" : "text-orange-600"}`}>ISS Retido</p>
                  <p className={`font-bold text-lg tabular-nums ${isDark ? "text-white" : "text-gray-900"}`}>
                    {detailDoc.valor_iss_retido != null ? FMT_BRL.format(detailDoc.valor_iss_retido) : "—"}
                  </p>
                </div>
              </div>

              {/* Natureza + IDs */}
              {detailDoc.natureza_operacao && (
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wide mb-1 ${isDark ? "text-gray-500" : "text-gray-400"}`}>Natureza da Operação</p>
                  <p className="text-sm">{detailDoc.natureza_operacao}</p>
                </div>
              )}

              <div className={`grid grid-cols-2 gap-3 text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                <div>
                  <span className="font-semibold">Chave de Acesso</span>
                  <p className="font-mono mt-0.5 break-all">{detailDoc.chave_acesso}</p>
                </div>
                <div>
                  <span className="font-semibold">NDD ID</span>
                  <p className="font-mono mt-0.5">{detailDoc.ndd_id ?? "—"}</p>
                  <span className="font-semibold mt-2 block">Sync em</span>
                  <p className="mt-0.5">{fmtDate(detailDoc.ndd_sync_at)}</p>
                </div>
              </div>

              {/* XML */}
              {detailLoading ? (
                <div className={`h-8 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
              ) : detailDoc.xml_content ? (
                <details className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                  <summary className={`px-4 py-3 cursor-pointer text-sm font-medium select-none ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                    Ver XML completo
                  </summary>
                  <pre className={`text-xs p-4 overflow-auto max-h-64 border-t font-mono leading-relaxed ${
                    isDark ? "bg-gray-950 text-green-400 border-gray-700" : "bg-gray-50 text-gray-700 border-gray-200"
                  }`}>
                    {detailDoc.xml_content}
                  </pre>
                </details>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* ════ TAB: SYNC ════ */}
      {tab === "sync" && (
        <div className="space-y-5">

          {/* Painel de configuração do token NDD */}
          {(() => {
            const nddCo = companies.find((c) => c.sync_nfse_ativo);
            const hasToken   = !!nddCo?.ndd_access_token;
            const hasRefresh = !!nddCo?.ndd_refresh_token;
            return (
              <div className={`rounded-xl border p-5 space-y-4 ${card}`}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1">
                    <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                      Token NDD Digital
                    </h2>
                    <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                      {!hasToken && "Sem token configurado."}
                      {hasToken && hasRefresh && "✅ Renovação automática ativa (refresh_token configurado)."}
                      {hasToken && !hasRefresh && "⚠️ access_token ativo, mas sem refresh_token — expira em 30 min."}
                    </p>
                  </div>
                  <button
                    onClick={() => { setShowTokenForm((v) => !v); setNddMsg(""); }}
                    className={`px-3 py-2 text-sm rounded-lg border transition-colors flex items-center gap-2 ${
                      isDark ? "border-gray-600 hover:bg-gray-700 text-gray-300" : "border-gray-300 hover:bg-gray-50 text-gray-700"
                    }`}
                  >
                    <Icon name="key" size={13} />
                    {hasRefresh ? "Atualizar tokens" : "Configurar tokens"}
                  </button>
                </div>

                {showTokenForm && (
                  <div className={`rounded-lg border p-4 space-y-4 ${isDark ? "border-gray-700 bg-gray-900/40" : "border-gray-200 bg-gray-50"}`}>
                    {/* Instruções */}
                    <div className={`text-xs space-y-1 ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                      <p className="font-semibold text-blue-500">Como obter os tokens do portal NDD:</p>
                      <ol className="list-decimal list-inside space-y-0.5 pl-1">
                        <li>Abra <span className="font-mono">spaceportalprod.e-datacenter.nddigital.com.br</span> e faça login</li>
                        <li>Pressione <kbd className={`px-1 py-0.5 rounded text-xs font-mono ${isDark ? "bg-gray-700" : "bg-white border border-gray-300"}`}>F12</kbd> → aba <strong>Network</strong> → filtre por <span className="font-mono">token</span></li>
                        <li>Recarregue a página ou navegue — aparecerá um POST para <span className="font-mono">/connect/token</span></li>
                        <li>Clique nessa request → aba <strong>Response</strong> → copie <code>access_token</code> e <code>refresh_token</code></li>
                      </ol>
                      <p className="text-yellow-500 font-medium pt-1">O refresh_token é mais longo que o access_token e não expira em 30 min — é ele que mantém a conexão permanente.</p>
                    </div>

                    {/* Campos */}
                    <div className="space-y-3">
                      <div>
                        <label className={`block text-xs font-medium mb-1 ${isDark ? "text-gray-400" : "text-gray-600"}`}>
                          access_token <span className="text-gray-400">(obrigatório)</span>
                        </label>
                        <textarea
                          rows={3}
                          value={nddAccessToken}
                          onChange={(e) => setNddAccessToken(e.target.value)}
                          placeholder="eyJhbGciOiJSUzI1NiIs..."
                          className={`w-full font-mono text-xs rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                            isDark ? "bg-gray-700 border border-gray-600 text-white placeholder-gray-500" : "bg-white border border-gray-300 text-gray-900 placeholder-gray-400"
                          }`}
                        />
                      </div>
                      <div>
                        <label className={`block text-xs font-medium mb-1 ${isDark ? "text-gray-400" : "text-gray-600"}`}>
                          refresh_token <span className="text-green-500">(recomendado — renovação automática)</span>
                        </label>
                        <textarea
                          rows={2}
                          value={nddRefreshToken}
                          onChange={(e) => setNddRefreshToken(e.target.value)}
                          placeholder="Cole o refresh_token aqui..."
                          className={`w-full font-mono text-xs rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                            isDark ? "bg-gray-700 border border-gray-600 text-white placeholder-gray-500" : "bg-white border border-gray-300 text-gray-900 placeholder-gray-400"
                          }`}
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={saveNddToken}
                          disabled={savingToken || !nddAccessToken.trim()}
                          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
                        >
                          {savingToken && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                          Salvar tokens
                        </button>
                        <button
                          onClick={() => { setShowTokenForm(false); setNddMsg(""); }}
                          className={`px-4 py-2 text-sm rounded-lg border transition-colors ${isDark ? "border-gray-600 hover:bg-gray-700" : "border-gray-300 hover:bg-gray-50"}`}
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {nddMsg && (
                  <p className={`text-sm p-3 rounded-lg ${
                    nddMsg.startsWith("✅") ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                    : nddMsg.startsWith("⚠") ? "bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400"
                  }`}>
                    {nddMsg}
                  </p>
                )}
              </div>
            );
          })()}

          {/* Painel de controle */}
          <div className={`rounded-xl border p-5 ${card}`}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-3">
                <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                  Status do Sync NFSe (NDD Digital)
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-5 text-sm">
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>Cobertura</span>
                    <p className="mt-0.5 font-medium">
                      {selectedId
                        ? (currentCompany?.nome ?? "Empresa selecionada")
                        : "Todas as empresas"}
                    </p>
                  </div>
                  <div>
                    <span className={isDark ? "text-gray-400" : "text-gray-500"}>Agendado às</span>
                    <p className="mt-0.5">05:00 diário</p>
                  </div>
                  {currentCompany && (
                    <div>
                      <span className={isDark ? "text-gray-400" : "text-gray-500"}>Último sync NFSe</span>
                      <p className="mt-0.5">{fmtDate(currentCompany.ndd_last_sync_at)}</p>
                    </div>
                  )}
                </div>
              </div>

              <button
                onClick={triggerSync}
                disabled={syncing}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
              >
                {syncing ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Icon name="zap" size={14} />
                )}
                Sync NFSe agora
              </button>
            </div>

            {syncMsg && (
              <p className={`mt-4 text-sm p-3 rounded-lg ${
                syncMsg.includes("Erro")
                  ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400"
                  : "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
              }`}>
                {syncMsg}
              </p>
            )}
          </div>

          {/* Logs */}
          <div className={`rounded-xl border overflow-hidden ${card}`}>
            <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-200"}`}>
              <h2 className="text-sm font-semibold">Últimos Syncs</h2>
              <button
                onClick={loadSyncLogs}
                className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                  isDark ? "border-gray-600 hover:bg-gray-700" : "border-gray-300 hover:bg-gray-50"
                }`}
              >
                Atualizar
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className={`w-full text-sm ${isDark ? "text-gray-200" : "text-gray-900"}`}>
                <thead>
                  <tr className={`border-b text-left ${isDark ? "border-gray-700 text-gray-400" : "border-gray-200 text-gray-600"}`}>
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
                      <td colSpan={6} className={`px-4 py-10 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                        Nenhum log de sync ainda.
                      </td>
                    </tr>
                  ) : (
                    syncLogs.map((log) => (
                      <tr key={log.id} className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">
                          {fmtDate(log.executado_em)}
                        </td>
                        <td className="px-4 py-3">{log.tipo}</td>
                        <td className="px-4 py-3 text-xs">{log.janela}</td>
                        <td className="px-4 py-3">
                          <Badge
                            label={log.status}
                            cls={
                              log.status === "ok"
                                ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                                : log.status === "parcial"
                                ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
                                : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                            }
                          />
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{log.documentos_novos}</td>
                        <td className="px-4 py-3 max-w-[220px]">
                          {log.erro_msg ? (
                            <span className="text-red-500 text-xs truncate block" title={log.erro_msg}>
                              {log.erro_msg.slice(0, 60)}…
                            </span>
                          ) : (
                            "—"
                          )}
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
  );
}
