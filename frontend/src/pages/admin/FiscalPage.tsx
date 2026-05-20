import { useCallback, useEffect, useMemo, useState } from "react";
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
    setStatsLoading(true);
    const p = new URLSearchParams({ ano: String(ano), mes: String(mes) });
    if (selectedId) p.set("company_id", selectedId);
    apiFetch<NfseStats>(`/api/fiscal/nfse/stats?${p}`, { token })
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [token, ano, mes, selectedId]);

  useEffect(() => { if (tab === "dashboard") loadStats(); }, [tab, loadStats]);

  // ── Load docs ───────────────────────────────────────────────────────────────
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

  // ── Load sync logs ──────────────────────────────────────────────────────────
  const loadSyncLogs = useCallback(() => {
    if (!token) return;
    setSyncLoading(true);
    // Sem empresa selecionada: pega logs globais (sem filtro de company_id)
    const url = selectedId
      ? `/api/fiscal/${selectedId}/sync/logs?limit=30`
      : `/api/fiscal/sync/logs?limit=30`;
    apiFetch<SyncLog[]>(url, { token })
      .then(setSyncLogs)
      .catch(() => setSyncLogs([]))
      .finally(() => setSyncLoading(false));
  }, [token, selectedId]);

  useEffect(() => { if (tab === "sync") loadSyncLogs(); }, [tab, loadSyncLogs]);

  // ── Conectar NDD via PKCE (offline_access → refresh_token permanente) ───────
  const [nddConnecting, setNddConnecting] = useState(false);
  const [nddMsg, setNddMsg] = useState("");

  const connectNdd = async () => {
    if (!token) return;
    // Usa a empresa Voetur (portadora do token NDD — sync_nfse_ativo)
    const nddCompany = companies.find((c) => c.sync_nfse_ativo);
    if (!nddCompany) {
      setNddMsg("Nenhuma empresa com sync_nfse_ativo configurado.");
      return;
    }
    setNddConnecting(true);
    setNddMsg("");
    try {
      const redirectBase = window.location.origin;
      const res = await apiFetch<{ authorize_url: string }>(
        `/api/fiscal/${nddCompany.id}/ndd/authorize-url?redirect_base=${encodeURIComponent(redirectBase)}`,
        { token }
      );
      const popup = window.open(res.authorize_url, "ndd_auth", "width=600,height=700");
      // Escuta mensagem de sucesso do popup (callback HTML envia postMessage)
      const onMsg = (e: MessageEvent) => {
        if (e.data?.type === "ndd_connected") {
          window.removeEventListener("message", onMsg);
          setNddMsg(
            e.data.has_refresh
              ? "✅ Conectado! Renovação automática ativada — não precisa fazer isso de novo."
              : "⚠️ Conectado sem refresh_token. Token expira em 30 min."
          );
          setNddConnecting(false);
          // Recarrega companies para atualizar status do token
          apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token }).then(setCompanies).catch(() => {});
          if (popup) popup.close();
        }
      };
      window.addEventListener("message", onMsg);
      // Timeout de segurança: se fechar o popup sem completar o auth
      const interval = setInterval(() => {
        if (popup?.closed) {
          clearInterval(interval);
          window.removeEventListener("message", onMsg);
          setNddConnecting(false);
        }
      }, 1000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setNddMsg(`Erro: ${msg}`);
      setNddConnecting(false);
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

          {/* Tabela */}
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
                    <th className="px-4 py-3 font-medium">Chave</th>
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
                      <td colSpan={7} className={`px-4 py-10 text-center text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                        Nenhuma NFSe encontrada.
                      </td>
                    </tr>
                  ) : (
                    docs.map((doc) => (
                      <tr
                        key={doc.id}
                        className={`border-b transition-colors ${isDark ? "border-gray-700 hover:bg-gray-800/50" : "border-gray-100 hover:bg-gray-50"}`}
                      >
                        <td className="px-4 py-3 whitespace-nowrap">{fmtDay(doc.data_emissao)}</td>
                        <td className="px-4 py-3 max-w-[180px]">
                          <div className="truncate" title={doc.emitente_nome}>
                            {doc.emitente_nome || doc.emitente_cnpj}
                          </div>
                          <div className={`text-xs font-mono ${isDark ? "text-gray-400" : "text-gray-400"}`}>
                            {fmtCnpj(doc.emitente_cnpj)}
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">{doc.municipio_nome || "—"}</td>
                        <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                          {FMT_BRL.format(doc.valor_total ?? 0)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                          {doc.valor_iss != null ? FMT_BRL.format(doc.valor_iss) : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge label={doc.status} cls={STATUS_BADGE[doc.status] ?? "bg-gray-100 text-gray-600"} />
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          <span title={doc.chave_acesso}>{doc.chave_acesso?.slice(0, 10)}…</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className={`flex items-center justify-between px-4 py-3 border-t text-sm ${isDark ? "border-gray-700" : "border-gray-200"}`}>
              <span className={isDark ? "text-gray-400" : "text-gray-500"}>{docs.length} registros</span>
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

      {/* ════ TAB: SYNC ════ */}
      {tab === "sync" && (
        <div className="space-y-5">

          {/* Painel de conexão NDD Digital */}
          <div className={`rounded-xl border p-5 ${card}`}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                  Conexão NDD Digital
                </h2>
                <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                  {companies.find((c) => c.sync_nfse_ativo)?.ndd_access_token
                    ? companies.find((c) => c.sync_nfse_ativo)?.ndd_refresh_token
                      ? "✅ Conectado com renovação automática (refresh_token ativo)"
                      : "⚠️ Token ativo mas sem refresh — expira em 30 min. Reconecte para ativar renovação automática."
                    : "Sem token NDD configurado. Clique em Conectar para autenticar."}
                </p>
              </div>
              <button
                onClick={connectNdd}
                disabled={nddConnecting}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2 transition-colors whitespace-nowrap"
              >
                {nddConnecting ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Icon name="link" size={14} />
                )}
                Conectar NDD Digital
              </button>
            </div>
            {nddMsg && (
              <p className={`mt-3 text-sm p-3 rounded-lg ${
                nddMsg.startsWith("✅")
                  ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                  : nddMsg.startsWith("⚠")
                  ? "bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400"
                  : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400"
              }`}>
                {nddMsg}
              </p>
            )}
          </div>

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
