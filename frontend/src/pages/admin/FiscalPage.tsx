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
  sync_portal_nfse_ativo?: boolean;
  ndd_last_sync_at: string | null;
  ndd_access_token: string | null;
  ndd_refresh_token: string | null;
  ndd_token_expires_at: string | null;
  cert_expiry?: string | null;
}

interface CertStatus {
  has_certificate: boolean;
  cert_expiry: string | null;
  dias_para_vencer: number | null;
  status: "ok" | "expirando" | "expirado" | "sem_certificado";
  sync_portal_nfse_ativo: boolean;
  portal_nfse_hora_sync: number;
  sefaz_nfe_bloqueado_ate: string | null;
  portal_nfse_last_sync_at: string | null;
  ndd_last_sync_at: string | null;
}

interface Municipality {
  municipio_ibge: string;
  municipio_nome: string;
  uf: string;
  sistema_tipo: string;
  ativo: boolean;
  status: string;
  last_sync_at: string | null;
  docs_total: number | null;
  ultimo_erro: string | null;
}

interface PortalLog {
  status: string;
  documentos_novos: number | null;
  documentos_cancelados: number | null;
  erro_msg: string | null;
  executado_em: string;
  nsu_final: number | null;
  janela: string | null;
}

interface SyncInfo {
  status?: string;
  documentos_novos?: number;
  executado_em?: string;
  erro_msg?: string | null;
  ativo?: boolean;
  ultimo_nsu?: number | null;
  ultimo_sync?: string | null;
  bloqueado_ate?: string | null;
  ultima_consulta_hb?: string | null;
  is_stuck?: boolean;
}

interface SyncStatusEntry {
  company_id: string;
  cnpj: string;
  nome: string;
  grupo: string | null;
  cert_expiry: string | null;
  syncs: {
    NFe: SyncInfo;
    CTe: SyncInfo;
    NFSe_NDD: SyncInfo;
    NFSe_Portal: SyncInfo;
  };
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
  fonte?: string | null;
  tipo_schema?: string | null;
  tipo?: string;
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

const GRUPO_PREFIXO: Record<string, string> = {
  vtclog: "VTCLog",
  voetur: "Voetur",
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
      <span className={`text-xs font-medium uppercase tracking-wide ${isDark ? "text-gray-300" : "text-gray-500"}`}>
        {label}
      </span>
      <span className={`text-2xl font-bold ${isDark ? "text-white" : "text-gray-900"}`}>{value}</span>
      {sub && <span className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>{sub}</span>}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const FONTE_LABEL: Record<string, string> = {
  ndd: "NDD Digital",
  portal_nacional: "Portal Nacional ADN",
  sefaz: "SEFAZ",
};

const CERT_STATUS_CLS: Record<string, string> = {
  ok:             "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  expirando:      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  expirado:       "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  sem_certificado:"bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

const SYNC_STATUS_CLS: Record<string, string> = {
  ok:       "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  parcial:  "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  erro:     "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  bloqueado:"bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
};

type Tab = "dashboard" | "nfse" | "nfe" | "sync" | "certificados";
const MONTHS = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
const DOCS_LIMIT = 50;

function NoCompanyPrompt({ isDark, card }: { isDark: boolean; card: string }) {
  return (
    <div className={`rounded-xl border p-12 text-center ${card}`}>
      <svg className="w-8 h-8 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
      <p className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>
        Selecione uma empresa no topo da página
      </p>
    </div>
  );
}

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
  const [mes, setMes] = useState(0); // 0 = todos os meses

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
  const [filterTomadorCnpj, setFilterTomadorCnpj] = useState("");

  // nfse / nfe filters
  const [filterFonte, setFilterFonte]   = useState("");

  // drill-down
  const [detailDoc, setDetailDoc]       = useState<NfseDoc | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailFetchMsg, setDetailFetchMsg] = useState("");

  // sync
  const [syncLogs, setSyncLogs]         = useState<SyncLog[]>([]);
  const [syncLoading, setSyncLoading]   = useState(false);
  const [syncing, setSyncing]           = useState(false);
  const [syncMsg, setSyncMsg]           = useState("");

  // sync status dashboard
  const [syncStatus, setSyncStatus]           = useState<SyncStatusEntry[]>([]);
  const [syncStatusLoading, setSyncStatusLoading] = useState(false);
  const [syncingPortal, setSyncingPortal]     = useState(false);

  // nfe tab (reusa loadDocs com tipo=NFe)
  const [nfeDocs, setNfeDocs]           = useState<NfseDoc[]>([]);
  const [nfeLoading, setNfeLoading]     = useState(false);
  const [nfeOffset, setNfeOffset]       = useState(0);
  const [nfeQ, setNfeQ]                 = useState("");
  const [nfeFonte, setNfeFonte]         = useState("");
  const [nfeStatus, setNfeStatus]       = useState("");

  // export
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingXml, setExportingXml] = useState(false);
  const [exportingNfeCsv, setExportingNfeCsv] = useState(false);
  const [exportingNfeXml, setExportingNfeXml] = useState(false);

  // busca por chave
  const [showFetchKey, setShowFetchKey]   = useState(false);
  const [fetchKey, setFetchKey]           = useState("");
  const [fetchKeyLoading, setFetchKeyLoading] = useState(false);
  const [fetchKeyResult, setFetchKeyResult]   = useState<{found:boolean;source:string;document:NfseDoc}|null>(null);
  const [fetchKeyError, setFetchKeyError]     = useState("");

  // certificados
  const [certStatus, setCertStatus]     = useState<CertStatus | null>(null);
  const [certFile, setCertFile]         = useState<File | null>(null);
  const [certPassword, setCertPassword] = useState("");
  const [certUploading, setCertUploading] = useState(false);
  const [certMsg, setCertMsg]           = useState("");

  // portal nfse settings
  const [portalSyncHora, setPortalSyncHora]           = useState(6);
  const [togglingPortalSync, setTogglingPortalSync]   = useState(false);
  const [runningPortalSync, setRunningPortalSync]     = useState(false);
  const [portalSyncMsg, setPortalSyncMsg]             = useState("");
  const [portalLogs, setPortalLogs]                   = useState<PortalLog[]>([]);

  // ndd manual sync
  const [nddSyncing, setNddSyncing]   = useState(false);
  const [nddSyncMsg, setNddSyncMsg]   = useState("");

  // municipal direto
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [munLoading, setMunLoading]         = useState(false);
  const [testingIbge, setTestingIbge]       = useState<string | null>(null);
  const [testResults, setTestResults]       = useState<Record<string, {ok: boolean; docs: number; msg: string}>>({});
  const [munSyncing, setMunSyncing]         = useState(false);
  const [munSyncMsg, setMunSyncMsg]         = useState("");
  const [seedingMun, setSeedingMun]         = useState(false);

  // sync tudo
  const [syncAllLoading, setSyncAllLoading] = useState(false);
  const [syncAllMsg, setSyncAllMsg]         = useState("");

  // busca por chave — seletor próprio de empresa
  const [fetchKeyCompanyId, setFetchKeyCompanyId] = useState("");

  // filtros de data — NFSe (usados na busca E no export)
  const [exportDateInicio, setExportDateInicio] = useState(() => {
    const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
  });
  const [exportDateFim, setExportDateFim]       = useState(() => new Date().toISOString().slice(0, 10));
  const [exportError, setExportError]           = useState("");

  // filtros de data — NFe/CTe
  const [nfeDataInicio, setNfeDataInicio] = useState(() => {
    const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
  });
  const [nfeDataFim, setNfeDataFim]       = useState(() => new Date().toISOString().slice(0, 10));

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
    const p = new URLSearchParams({ ano: String(ano) });
    if (mes > 0) p.set("mes", String(mes));
    if (selectedId) p.set("company_id", selectedId);
    const key = `stats:${p}`;
    const hit = cached<NfseStats>(key, 300_000);
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
    const p = new URLSearchParams({ limit: String(DOCS_LIMIT), offset: String(docsOffset), tipo: "NFSe" });
    if (selectedId)        p.set("company_id", selectedId);
    if (q)                 p.set("q", q);
    if (filterStatus)      p.set("status", filterStatus);
    if (filterFonte)       p.set("fonte", filterFonte);
    if (filterMunicipio)   p.set("municipio", filterMunicipio);
    if (filterCnpj)        p.set("emitente_cnpj", filterCnpj);
    if (filterTomadorCnpj) p.set("destinatario_cnpj", filterTomadorCnpj);
    if (exportDateInicio)  p.set("data_inicio", exportDateInicio);
    if (exportDateFim)     p.set("data_fim", exportDateFim);
    const key = `docs:${p}`;
    const hit = cached<NfseDoc[]>(key, 60_000);
    if (hit) { setDocs(hit); return; }
    setDocsLoading(true);
    apiFetch<{ data: NfseDoc[] }>(`/api/fiscal/nfse?${p}`, { token })
      .then((r) => { const d = r.data ?? []; setDocs(d); setCache(key, d); })
      .catch(() => setDocs([]))
      .finally(() => setDocsLoading(false));
  }, [token, selectedId, q, filterStatus, filterFonte, filterMunicipio, filterCnpj, filterTomadorCnpj, exportDateInicio, exportDateFim, docsOffset]);

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
    setDetailFetchMsg("");
    if (doc.xml_content) return;
    setDetailLoading(true);
    try {
      const full = await apiFetch<NfseDoc>(`/api/fiscal/nfse/${doc.id}`, { token: token! });
      setDetailDoc(full);
    } catch {/* mostra o que temos */} finally {
      setDetailLoading(false);
    }
  };


  const downloadingDanfse = false;

  const downloadDanfse = async (doc: NfseDoc) => {
    const chave = doc.chave_acesso ?? "";
    // Copia a chave para o clipboard — portal gov.br não suporta pré-preenchimento via URL
    try { await navigator.clipboard.writeText(chave); } catch { /* sem permissão, ignora */ }

    if (chave.length === 44) {
      window.open(
        `https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=completa&nfe=${chave}`,
        "_blank", "noopener,noreferrer"
      );
      setDetailFetchMsg("✅ Chave copiada! Portal SEFAZ aberto — cole no campo de consulta.");
    } else {
      window.open("https://www.nfse.gov.br/consultapublica", "_blank", "noopener,noreferrer");
      setDetailFetchMsg("✅ Chave copiada! Portal NFS-e aberto — selecione 'Por Chave de Acesso' e cole.");
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

  // ── Sync Status ─────────────────────────────────────────────────────────────
  const loadSyncStatus = useCallback(() => {
    if (!token) return;
    const hit = cached<SyncStatusEntry[]>("sync:status", 60_000);
    if (hit) { setSyncStatus(hit); return; }
    setSyncStatusLoading(true);
    apiFetch<SyncStatusEntry[]>("/api/fiscal/sync/status", { token })
      .then((d) => { setSyncStatus(d); setCache("sync:status", d); })
      .catch(() => {})
      .finally(() => setSyncStatusLoading(false));
  }, [token]);

  // Carrega na abertura da tab
  useEffect(() => {
    if (tab === "sync") loadSyncStatus();
  }, [tab, loadSyncStatus]);

  // Polling 30s: reavalia depois que syncStatus é populado
  useEffect(() => {
    if (tab !== "sync") return;
    const hasRunning = syncStatus.some((e) =>
      Object.values(e.syncs).some((s) => s.status === "running")
    );
    if (!hasRunning) return;
    const timer = setInterval(loadSyncStatus, 60_000);
    return () => clearInterval(timer);
  }, [tab, syncStatus, loadSyncStatus]);

  const triggerPortalSync = async (companyId?: string) => {
    if (!token || syncingPortal) return;
    setSyncingPortal(true);
    try {
      const url = companyId
        ? `/api/fiscal/portal-nfse/sync/run?company_id=${companyId}`
        : "/api/fiscal/portal-nfse/sync/run";
      await apiFetch(url, { token, method: "POST" });
      setTimeout(loadSyncStatus, 3000);
    } catch { /* silent */ } finally {
      setSyncingPortal(false);
    }
  };

  // ── NFe tab ─────────────────────────────────────────────────────────────────
  const loadNfeDocs = useCallback(() => {
    if (!token) return;
    const p = new URLSearchParams({ limit: String(DOCS_LIMIT), offset: String(nfeOffset), tipo: "NFe,CTe" });
    if (selectedId)    p.set("company_id", selectedId);
    if (nfeQ)          p.set("q", nfeQ);
    if (nfeStatus)     p.set("status", nfeStatus);
    if (nfeFonte)      p.set("fonte", nfeFonte);
    if (nfeDataInicio) p.set("data_inicio", nfeDataInicio);
    if (nfeDataFim)    p.set("data_fim", nfeDataFim);
    setNfeLoading(true);
    apiFetch<{ data: NfseDoc[] }>(`/api/fiscal/nfse?${p}`, { token })
      .then((r) => setNfeDocs(r.data ?? []))
      .catch(() => setNfeDocs([]))
      .finally(() => setNfeLoading(false));
  }, [token, selectedId, nfeQ, nfeStatus, nfeFonte, nfeDataInicio, nfeDataFim, nfeOffset]);

  useEffect(() => { if (tab === "nfe") loadNfeDocs(); }, [tab, loadNfeDocs]);

  // ── Export ───────────────────────────────────────────────────────────────────
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = async (tipo: string) => {
    if (!token || !selectedId) return;
    setExportError("");
    const setter = tipo === "NFSe" ? setExportingCsv : setExportingNfeCsv;
    setter(true);
    try {
      const p = new URLSearchParams({ company_id: selectedId, tipo });
      if (exportDateInicio) p.set("data_inicio", exportDateInicio);
      if (exportDateFim)    p.set("data_fim",    exportDateFim);
      if (filterFonte)      p.set("fonte",       filterFonte);
      const resp = await fetch(`/api/fiscal/nfse/export/csv?${p}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        setExportError(`Erro ao exportar CSV: ${(err as {detail?: string}).detail ?? `HTTP ${resp.status}`}`);
        return;
      }
      downloadBlob(await resp.blob(), `fiscal_${tipo.toLowerCase()}_${exportDateInicio || "todos"}.csv`);
    } catch (e) {
      setExportError(`Erro ao exportar CSV: ${e instanceof Error ? e.message : String(e)}`);
    } finally { setter(false); }
  };

  const exportXml = async (tipo: string) => {
    if (!token || !selectedId) return;
    setExportError("");
    const setter = tipo === "NFSe" ? setExportingXml : setExportingNfeXml;
    setter(true);
    try {
      const p = new URLSearchParams({ company_id: selectedId, tipo });
      if (exportDateInicio) p.set("data_inicio", exportDateInicio);
      if (exportDateFim)    p.set("data_fim",    exportDateFim);
      if (filterFonte)      p.set("fonte",       filterFonte);
      const resp = await fetch(`/api/fiscal/nfse/export/xml?${p}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        setExportError(`Erro ao exportar XMLs: ${(err as {detail?: string}).detail ?? `HTTP ${resp.status}`}`);
        return;
      }
      downloadBlob(await resp.blob(), `xmls_${tipo.toLowerCase()}_${exportDateInicio || "todos"}.zip`);
    } catch (e) {
      setExportError(`Erro ao exportar XMLs: ${e instanceof Error ? e.message : String(e)}`);
    } finally { setter(false); }
  };

  // ── Busca por chave de acesso ────────────────────────────────────────────────
  const fetchByKey = async () => {
    if (!token || (fetchKey.length !== 44 && fetchKey.length !== 50) || !fetchKeyCompanyId) return;
    setFetchKeyLoading(true);
    setFetchKeyError("");
    setFetchKeyResult(null);
    try {
      const r = await apiFetch<{found:boolean;source:string;document:NfseDoc}>(
        "/api/fiscal/fetch-by-key",
        { token, method: "POST", json: { company_id: fetchKeyCompanyId, chave_acesso: fetchKey } }
      );
      setFetchKeyResult(r);
    } catch (e) {
      setFetchKeyError(e instanceof Error ? e.message : "Documento não encontrado nos portais.");
    } finally {
      setFetchKeyLoading(false);
    }
  };

  // ── Certificados ─────────────────────────────────────────────────────────────
  const loadCertStatus = useCallback(() => {
    if (!token || !selectedId) return;
    apiFetch<CertStatus>(`/api/fiscal/${selectedId}/certificates/status`, { token })
      .then((s) => { setCertStatus(s); setPortalSyncHora(s.portal_nfse_hora_sync ?? 6); })
      .catch(() => setCertStatus(null));
  }, [token, selectedId]);

  const loadPortalLogs = useCallback(() => {
    if (!token || !selectedId) return;
    apiFetch<PortalLog[]>(`/api/fiscal/${selectedId}/portal-nfse/logs`, { token })
      .then(setPortalLogs)
      .catch(() => {});
  }, [token, selectedId]);

  const loadMunicipalities = useCallback(() => {
    if (!token || !selectedId) return;
    setMunLoading(true);
    apiFetch<Municipality[]>(`/api/fiscal/${selectedId}/municipalities`, { token })
      .then(setMunicipalities)
      .catch(() => {})
      .finally(() => setMunLoading(false));
  }, [token, selectedId]);

  useEffect(() => {
    if (tab === "certificados") { loadCertStatus(); loadPortalLogs(); loadMunicipalities(); }
  }, [tab, loadCertStatus, loadPortalLogs, loadMunicipalities]);

  const togglePortalSync = async () => {
    if (!token || !selectedId || !certStatus || togglingPortalSync) return;
    setTogglingPortalSync(true);
    setPortalSyncMsg("");
    try {
      const novo = !certStatus.sync_portal_nfse_ativo;
      await apiFetch(`/api/fiscal/${selectedId}/portal-nfse/settings`, {
        token, method: "PATCH", json: { sync_portal_nfse_ativo: novo },
      });
      setCertStatus((prev) => prev ? { ...prev, sync_portal_nfse_ativo: novo } : prev);
    } catch (e) {
      setPortalSyncMsg(`Erro ao alterar sync: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTogglingPortalSync(false);
    }
  };

  const savePortalHora = async (hora: number) => {
    if (!token || !selectedId) return;
    setPortalSyncHora(hora);
    try {
      await apiFetch(`/api/fiscal/${selectedId}/portal-nfse/settings`, {
        token, method: "PATCH", json: { portal_nfse_hora_sync: hora },
      });
    } catch { /* ignora — valor já exibido na UI */ }
  };

  const runPortalSyncNow = async () => {
    if (!token || !selectedId || runningPortalSync) return;
    // Guard: bloqueia se cStat 656 ainda ativo
    if (certStatus?.sefaz_nfe_bloqueado_ate) {
      const bloqDate = new Date(certStatus.sefaz_nfe_bloqueado_ate);
      if (bloqDate > new Date()) {
        const min = Math.ceil((bloqDate.getTime() - Date.now()) / 60000);
        setPortalSyncMsg(`⛔ Aguarde ${min} min. Tentar agora pode bloquear o CNPJ na ADN (cStat 656).`);
        return;
      }
    }
    setRunningPortalSync(true);
    setPortalSyncMsg("");
    try {
      await apiFetch(`/api/fiscal/portal-nfse/sync/run?company_id=${selectedId}`, { token, method: "POST" });
      setPortalSyncMsg("✅ Sync iniciado — atualize os logs em instantes.");
      setTimeout(loadPortalLogs, 5000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("656") || msg.toLowerCase().includes("bloqueado") || msg.toLowerCase().includes("consumo")) {
        setPortalSyncMsg("⛔ ADN retornou cStat 656 (consumo excessivo). Aguarde 1h antes de tentar.");
        loadCertStatus();
      } else {
        setPortalSyncMsg(`Erro: ${msg}`);
      }
    } finally {
      setRunningPortalSync(false);
    }
  };

  const syncNdd = async () => {
    if (!token || !selectedId || nddSyncing) return;
    setNddSyncing(true);
    setNddSyncMsg("");
    try {
      await apiFetch(`/api/fiscal/${selectedId}/ndd/sync`, { token, method: "POST" });
      setNddSyncMsg("✅ Sync NDD iniciado — aguarde e atualize os logs em instantes.");
      setTimeout(loadCertStatus, 8000);
    } catch (e) {
      setNddSyncMsg(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setNddSyncing(false);
    }
  };

  const seedMunicipalities = async () => {
    if (!token || !selectedId || seedingMun) return;
    setSeedingMun(true);
    try {
      await apiFetch(`/api/fiscal/${selectedId}/municipalities/seed`, { token, method: "POST" });
      loadMunicipalities();
    } catch (e) {
      setMunSyncMsg(`Erro no seed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSeedingMun(false);
    }
  };

  const toggleMunicipality = async (m: Municipality) => {
    if (!token || !selectedId) return;
    const action = m.ativo ? "deactivate" : "activate";
    try {
      await apiFetch(`/api/fiscal/${selectedId}/municipalities/${m.municipio_ibge}/${action}`, { token, method: "PATCH" });
      setMunicipalities(prev => prev.map(x => x.municipio_ibge === m.municipio_ibge ? { ...x, ativo: !x.ativo } : x));
    } catch (e) {
      setMunSyncMsg(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const testMunicipality = async (ibge: string) => {
    if (!token || !selectedId || testingIbge) return;
    setTestingIbge(ibge);
    setTestResults(prev => { const n = { ...prev }; delete n[ibge]; return n; });
    try {
      const r = await apiFetch<{ok: boolean; tipo: string; docs_encontrados: number; sandbox: boolean}>(
        `/api/fiscal/${selectedId}/municipalities/${ibge}/test?sandbox=true`, { token, method: "POST" }
      );
      setTestResults(prev => ({ ...prev, [ibge]: { ok: true, docs: r.docs_encontrados, msg: `✅ ${r.tipo} — ${r.docs_encontrados} docs (sandbox)` } }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setTestResults(prev => ({ ...prev, [ibge]: { ok: false, docs: 0, msg: `❌ ${msg.slice(0, 80)}` } }));
    } finally {
      setTestingIbge(null);
    }
  };

  const syncMunicipalities = async () => {
    if (!token || !selectedId || munSyncing) return;
    setMunSyncing(true);
    setMunSyncMsg("");
    try {
      await apiFetch(`/api/fiscal/${selectedId}/municipalities/sync`, { token, method: "POST" });
      setMunSyncMsg("✅ Sync municipal iniciado — atualize os logs em instantes.");
      setTimeout(loadMunicipalities, 8000);
    } catch (e) {
      setMunSyncMsg(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setMunSyncing(false);
    }
  };

  const syncAllNfse = async () => {
    if (!token || !selectedId || syncAllLoading) return;
    setSyncAllLoading(true);
    setSyncAllMsg("");
    try {
      await apiFetch(`/api/fiscal/${selectedId}/nfse/sync/all`, { token, method: "POST" });
      setSyncAllMsg("✅ Sync unificado iniciado (NDD + Portal + Municipal).");
      setTimeout(() => { loadCertStatus(); loadPortalLogs(); loadMunicipalities(); }, 10000);
    } catch (e) {
      setSyncAllMsg(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSyncAllLoading(false);
    }
  };

  const uploadCert = async () => {
    if (!token || !certFile || !certPassword || !selectedId) return;
    setCertUploading(true);
    setCertMsg("");
    try {
      const fd = new FormData();
      fd.append("arquivo", certFile);
      fd.append("senha", certPassword);
      const resp = await fetch(`/api/fiscal/${selectedId}/certificates`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!resp.ok) throw new Error(await resp.text());
      setCertMsg("✅ Certificado salvo com sucesso.");
      setCertFile(null); setCertPassword("");
      loadCertStatus();
      apiFetch<FiscalCompany[]>("/api/fiscal/companies", { token }).then(setCompanies).catch(() => {});
    } catch (e) {
      setCertMsg(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setCertUploading(false);
    }
  };

  const deleteCert = async () => {
    if (!token || !selectedId || !confirm("Remover certificado digital desta empresa?")) return;
    try {
      await apiFetch(`/api/fiscal/${selectedId}/certificates`, { token, method: "DELETE" });
      setCertMsg("Certificado removido.");
      loadCertStatus();
    } catch (e) {
      setCertMsg(`Erro ao remover: ${e instanceof Error ? e.message : String(e)}`);
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
    `px-3 py-1.5 text-sm font-medium rounded-lg transition-colors whitespace-nowrap ${
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
            <p className={`text-sm mt-0.5 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
              Documentos fiscais sincronizados via NDD Digital
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            {/* Seletor de empresa */}
            <div className="flex flex-col gap-1">
              <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                Empresa
              </label>
              <select
                value={selectedId}
                onChange={(e) => { setSelectedId(e.target.value); setDocsOffset(0); setNfeOffset(0); }}
                className={`${inp} min-w-[240px]`}
              >
                <option value="">Todas as empresas</option>
                {grouped.map(({ key, items }) => (
                  <optgroup key={key} label={GRUPO_LABEL[key] ?? key}>
                    {items.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.grupo && GRUPO_PREFIXO[c.grupo] ? `${GRUPO_PREFIXO[c.grupo]} — ` : ""}
                        {c.nome}
                        {c.cidade ? ` (${c.cidade})` : c.tipo === "matriz" ? " (Matriz)" : ""}
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
      <div className={`flex gap-1 p-1 rounded-xl w-fit flex-wrap ${isDark ? "bg-gray-800" : "bg-gray-100"}`}>
        <button className={tabCls("dashboard")}    onClick={() => setTab("dashboard")}>Dashboard</button>
        <button className={tabCls("nfse")}         onClick={() => setTab("nfse")}>NFSe</button>
        <button className={tabCls("nfe")}          onClick={() => setTab("nfe")}>NFe / CTe</button>
        <button className={tabCls("sync")}         onClick={() => setTab("sync")}>Sync</button>
        <button className={tabCls("certificados")} onClick={() => setTab("certificados")}>Certificados</button>
      </div>

      {/* ════ TAB: DASHBOARD ════ */}
      {tab === "dashboard" && (
        <div className="space-y-5">
          {!selectedId ? (
            <NoCompanyPrompt isDark={isDark} card={card} />
          ) : (<>

          {/* Cards resumo da empresa selecionada (ano corrente) */}
          {currentCompany && stats && (
            <div className={`rounded-xl border p-5 space-y-3 ${card}`}>
              <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                {currentCompany.nome} — {ano}{mes > 0 ? ` · ${MONTHS[mes - 1]}` : ""}
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
              <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>Ano</label>
              <select value={ano} onChange={(e) => setAno(+e.target.value)} className={`${inp} w-24`}>
                {Array.from({ length: now.getFullYear() - 2025 }, (_, i) => 2026 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>Mês</label>
              <select value={mes} onChange={(e) => setMes(+e.target.value)} className={`${inp} w-32`}>
                <option value={0}>Todos os meses</option>
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
                    <p className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>Sem dados.</p>
                  ) : (
                    Object.entries(stats.por_status).map(([s, n]) => (
                      <div key={s} className="flex items-center justify-between gap-3 mb-2">
                        <Badge label={s} cls={STATUS_BADGE[s] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />
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
                    <p className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>Sem dados.</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <p className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
              Nenhum dado para o período selecionado.
            </p>
          )}
          </>)}
        </div>
      )}

      {/* ════ TAB: NFSe ════ */}
      {tab === "nfse" && (
        <div className="space-y-4">
          {!selectedId ? <NoCompanyPrompt isDark={isDark} card={card} /> : (<>
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
                placeholder="CNPJ tomador"
                value={filterTomadorCnpj}
                onChange={(e) => { setFilterTomadorCnpj(e.target.value); setDocsOffset(0); }}
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
              <select
                value={filterFonte}
                onChange={(e) => { setFilterFonte(e.target.value); setDocsOffset(0); }}
                className={`${inp} w-40`}
              >
                <option value="">Todas as fontes</option>
                <option value="ndd">NDD Digital</option>
                <option value="portal_nacional">Portal Nacional</option>
                <option value="sefaz">SEFAZ</option>
              </select>
              <div className="flex flex-col gap-0.5">
                <label className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>De</label>
                <input type="date" value={exportDateInicio} onChange={(e) => { setExportDateInicio(e.target.value); setDocsOffset(0); }}
                  className={`${inp} w-32 text-xs py-1.5`} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>Até</label>
                <input type="date" value={exportDateFim} onChange={(e) => { setExportDateFim(e.target.value); setDocsOffset(0); }}
                  className={`${inp} w-32 text-xs py-1.5`} />
              </div>
              <button
                onClick={() => { setDocsOffset(0); loadDocs(); }}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
              >
                Buscar
              </button>
              <div className="flex flex-wrap items-end gap-2 ml-auto">
                <button
                  onClick={() => exportCsv("NFSe")}
                  disabled={exportingCsv || !selectedId}
                  title={!selectedId ? "Selecione uma empresa" : !exportDateInicio ? "Informe a data inicial" : "Exportar CSV"}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${isDark ? "bg-emerald-900/30 border border-emerald-700/60 text-emerald-400 hover:bg-emerald-900/50" : "bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100"}`}
                >
                  {exportingCsv
                    ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    : (<svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>)}
                  CSV
                </button>
                <button
                  onClick={() => exportXml("NFSe")}
                  disabled={exportingXml || !selectedId}
                  title={!selectedId ? "Selecione uma empresa" : !exportDateInicio ? "Informe a data inicial" : "Baixar XMLs"}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${isDark ? "bg-blue-900/30 border border-blue-700/60 text-blue-400 hover:bg-blue-900/50" : "bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100"}`}
                >
                  {exportingXml
                    ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    : (<svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>)}
                  XML
                </button>
                <button
                  onClick={() => { setShowFetchKey(true); setFetchKeyResult(null); setFetchKeyError(""); setFetchKey(""); setFetchKeyCompanyId(selectedId || ""); }}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors ${isDark ? "bg-violet-900/30 border border-violet-700/60 text-violet-400 hover:bg-violet-900/50" : "bg-violet-50 border border-violet-200 text-violet-700 hover:bg-violet-100"}`}
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  Buscar por chave
                </button>
              </div>
              {exportError && <p className="text-xs text-red-500 mt-1 col-span-full">{exportError}</p>}
            </div>
          </div>

          {/* Lista de cards */}
          <div className={`rounded-xl border overflow-hidden ${card}`}>
            {docsLoading ? (
              <div className={`divide-y ${isDark ? "divide-gray-700" : "divide-gray-100"}`}>
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
              <p className={`px-4 py-12 text-center text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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
                          <span className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                            {fmtDay(doc.data_emissao)}
                          </span>
                          <Badge label={doc.status} cls={STATUS_BADGE[doc.status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />
                          {doc.fonte && doc.fonte !== "ndd" && (
                            <Badge label={FONTE_LABEL[doc.fonte] ?? doc.fonte} cls="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" />
                          )}
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
                        <p className={`text-xs font-mono mt-0.5 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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
                          <p className={`text-xs mt-0.5 tabular-nums ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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
              <span className={isDark ? "text-gray-300" : "text-gray-500"}>{docs.length} registros · clique para detalhar</span>
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
          </>)}
        </div>
      )}

      {/* ════ MODAL BUSCA POR CHAVE ════ */}
      {showFetchKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => setShowFetchKey(false)}>
          <div
            className={`rounded-2xl border shadow-2xl w-full max-w-lg ${isDark ? "bg-gray-900 border-gray-700 text-gray-200" : "bg-white border-gray-200 text-gray-900"}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b" style={{background: isDark ? "#111827" : "#fff"}}>
              <h2 className="font-bold text-base">Buscar NFS-e / NF-e por chave de acesso</h2>
              <button onClick={() => setShowFetchKey(false)} className={`p-2 rounded-lg ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-100"}`}>
                <Icon name="x" size={16} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {/* Seletor de empresa — obrigatório, sem "todas" */}
              <div className="space-y-1">
                <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-600"}`}>Empresa</label>
                <select
                  value={fetchKeyCompanyId}
                  onChange={(e) => setFetchKeyCompanyId(e.target.value)}
                  className={`w-full rounded-lg border px-3 py-2 text-sm ${isDark ? "bg-gray-800 border-gray-600 text-white" : "bg-white border-gray-300 text-gray-900"}`}
                >
                  <option value="">— Selecione a empresa —</option>
                  {grouped.map(({ key, items }) => (
                    <optgroup key={key} label={GRUPO_LABEL[key] ?? key}>
                      {items.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.grupo && GRUPO_PREFIXO[c.grupo] ? `${GRUPO_PREFIXO[c.grupo]} — ` : ""}{c.nome}{c.cidade ? ` (${c.cidade})` : ""} — {fmtCnpj(c.cnpj)}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-600"}`}>Chave de acesso</label>
                <input
                  value={fetchKey}
                  onChange={(e) => setFetchKey(e.target.value.replace(/\D/g, "").slice(0, 50))}
                  placeholder="44 dígitos numéricos"
                  className={`w-full font-mono text-sm rounded-lg border px-3 py-2 ${isDark ? "bg-gray-800 border-gray-600 text-white" : "bg-white border-gray-300"}`}
                  maxLength={44}
                />
                <p className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                  {fetchKey.length}/{fetchKey.length <= 44 ? "44" : "50"} dígitos · NF-e/CT-e = 44 dígitos · NFS-e Portal Nacional = 50 dígitos · Salva automaticamente.
                </p>
              </div>
              <button
                onClick={fetchByKey}
                disabled={(fetchKey.length !== 44 && fetchKey.length !== 50) || fetchKeyLoading || !fetchKeyCompanyId}
                className={`w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold shadow-sm border transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed ${
                  !((fetchKey.length !== 44 && fetchKey.length !== 50) || fetchKeyLoading || !fetchKeyCompanyId)
                    ? "hover:scale-[1.01] active:scale-95" : ""
                } ${
                  isDark
                    ? "bg-gradient-to-br from-blue-600 to-blue-800 hover:from-blue-500 hover:to-blue-700 border-blue-500/40 text-white shadow-blue-900/40"
                    : "bg-gradient-to-br from-blue-500 to-blue-700 hover:from-blue-400 hover:to-blue-600 border-blue-300/50 text-white shadow-blue-200"
                }`}
              >
                {fetchKeyLoading ? (
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
                  </svg>
                )}
                <span>{fetchKeyLoading ? "Buscando…" : "Buscar nos portais"}</span>
              </button>
              {fetchKeyError && <p className="text-sm text-red-500">{fetchKeyError}</p>}
              {fetchKeyResult?.found && (
                <div className={`rounded-xl border p-4 space-y-2 ${isDark ? "border-gray-700 bg-gray-800" : "border-gray-200 bg-gray-50"}`}>
                  <div className="flex items-center gap-2">
                    <Badge label={`Encontrado: ${fetchKeyResult.source}`} cls="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" />
                  </div>
                  <p className="text-sm font-semibold">{fetchKeyResult.document.emitente_nome}</p>
                  <p className={`text-xs font-mono ${isDark ? "text-gray-300" : "text-gray-500"}`}>{fetchKeyResult.document.chave_acesso}</p>
                  <p className="text-sm">{FMT_BRL.format(fetchKeyResult.document.valor_total)} · {fmtDay(fetchKeyResult.document.data_emissao)}</p>
                </div>
              )}
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
                  <p className={`text-xs mt-0.5 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                    Nº {detailDoc.numero}{detailDoc.serie ? ` · Série ${detailDoc.serie}` : ""}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadDanfse(detailDoc)}
                  disabled={downloadingDanfse}
                  title="Baixar DANFS-e em PDF via Portal Nacional ADN"
                  className={`group relative inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold shadow-sm border transition-all duration-150 ${
                    downloadingDanfse
                      ? "cursor-not-allowed opacity-60"
                      : "hover:scale-[1.02] active:scale-95"
                  } ${
                    isDark
                      ? "bg-gradient-to-br from-blue-600 to-blue-800 hover:from-blue-500 hover:to-blue-700 border-blue-500/40 text-white shadow-blue-900/40"
                      : "bg-gradient-to-br from-blue-500 to-blue-700 hover:from-blue-400 hover:to-blue-600 border-blue-300/50 text-white shadow-blue-200"
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  <span>DANFS-e</span>
                </button>
                <button
                  onClick={() => setDetailDoc(null)}
                  className={`p-2 rounded-lg transition-colors ${isDark ? "hover:bg-gray-800 text-gray-400 hover:text-gray-200" : "hover:bg-gray-100 text-gray-500 hover:text-gray-700"}`}
                >
                  <Icon name="x" size={16} />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-5">
              {/* Status + Data */}
              <div className="flex items-center gap-3">
                <Badge label={detailDoc.status} cls={STATUS_BADGE[detailDoc.status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />
                <span className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                  Emitida em {fmtDay(detailDoc.data_emissao)}
                </span>
                {detailDoc.municipio_nome && (
                  <span className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                    · {detailDoc.municipio_nome}
                  </span>
                )}
              </div>

              {/* Emitente / Destinatário */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className={`rounded-xl p-4 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDark ? "text-gray-500" : "text-gray-400"}`}>Emitente (Prestador)</p>
                  <p className="font-semibold leading-snug">{detailDoc.emitente_nome || "—"}</p>
                  <p className={`text-xs font-mono mt-1 ${isDark ? "text-gray-300" : "text-gray-500"}`}>{fmtCnpj(detailDoc.emitente_cnpj)}</p>
                </div>
                <div className={`rounded-xl p-4 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDark ? "text-gray-500" : "text-gray-400"}`}>Destinatário (Tomador)</p>
                  <p className="font-semibold leading-snug">{detailDoc.destinatario_nome || "—"}</p>
                  <p className={`text-xs font-mono mt-1 ${isDark ? "text-gray-300" : "text-gray-500"}`}>{fmtCnpj(detailDoc.destinatario_cnpj)}</p>
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

              <div className={`grid grid-cols-2 gap-3 text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                <div>
                  <span className="font-semibold">Chave de Acesso</span>
                  <p className="font-mono break-all mt-0.5">{detailDoc.chave_acesso}</p>
                  {detailFetchMsg && (
                    <p className={`mt-1 text-xs ${detailFetchMsg.startsWith("✅") ? "text-emerald-500" : "text-red-400"}`}>
                      {detailFetchMsg}
                    </p>
                  )}
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
                    <p className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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
                    <div className={`text-xs space-y-1 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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
                    <span className={isDark ? "text-gray-300" : "text-gray-500"}>Cobertura</span>
                    <p className="mt-0.5 font-medium">
                      {selectedId
                        ? (currentCompany?.nome ?? "Empresa selecionada")
                        : "Todas as empresas"}
                    </p>
                  </div>
                  <div>
                    <span className={isDark ? "text-gray-300" : "text-gray-500"}>Agendado às</span>
                    <p className="mt-0.5">05:00 diário</p>
                  </div>
                  {currentCompany && (
                    <div>
                      <span className={isDark ? "text-gray-300" : "text-gray-500"}>Último sync NFSe</span>
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

          {/* Status por empresa */}
          <div className={`rounded-xl border p-5 space-y-4 ${card}`}>
            <div className="flex items-center justify-between">
              <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                Status por Empresa e Tipo
              </h2>
              <button onClick={loadSyncStatus} className={`text-xs px-3 py-1.5 rounded border transition-colors ${isDark ? "border-gray-600 hover:bg-gray-700" : "border-gray-300 hover:bg-gray-50"}`}>
                Atualizar
              </button>
            </div>
            {syncStatusLoading && <div className={`h-20 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />}
            {syncStatus.filter(e => !selectedId || e.company_id === selectedId).map((entry) => (
              <div key={entry.company_id} className={`rounded-lg border p-4 space-y-3 ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold">{entry.nome}</p>
                    <p className={`text-xs font-mono ${isDark ? "text-gray-300" : "text-gray-500"}`}>{fmtCnpj(entry.cnpj)}</p>
                  </div>
                  {entry.cert_expiry && (() => {
                    const dias = Math.round((new Date(entry.cert_expiry).getTime() - Date.now()) / 86400000);
                    return dias < 30 ? <Badge label={`Cert. expira em ${dias}d`} cls={dias < 7 ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800"} /> : null;
                  })()}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {(["NFe","CTe","NFSe_NDD","NFSe_Portal"] as const).map((tipo) => {
                    const s = entry.syncs[tipo as keyof typeof entry.syncs];
                    const label = { NFe: "NF-e", CTe: "CT-e", NFSe_NDD: "NFS-e NDD", NFSe_Portal: "NFS-e ADN" }[tipo];
                    return (
                      <div key={tipo} className={`rounded-lg p-3 space-y-1.5 ${isDark ? "bg-gray-700/60" : "bg-gray-50"}`}>
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-medium">{label}</span>
                          {s.ativo ? <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> : <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />}
                        </div>
                        {s.status && <Badge label={s.is_stuck ? "preso" : s.status} cls={s.is_stuck ? "bg-orange-100 text-orange-800" : SYNC_STATUS_CLS[s.status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />}
                        {s.documentos_novos != null && s.documentos_novos > 0 && (
                          <p className="text-xs text-green-500">+{s.documentos_novos} docs</p>
                        )}
                        {s.executado_em && <p className={`text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>{fmtDate(s.executado_em)}</p>}
                        {s.ultimo_nsu != null && <p className={`text-xs font-mono ${isDark ? "text-gray-500" : "text-gray-400"}`}>NSU {s.ultimo_nsu}</p>}
                        {s.bloqueado_ate && <p className="text-xs text-orange-500">⛔ Bloq. até {fmtDate(s.bloqueado_ate)}</p>}
                        {s.erro_msg && <p className="text-xs text-red-400 truncate" title={s.erro_msg}>{s.erro_msg.slice(0, 40)}</p>}
                        {tipo === "NFSe_Portal" && s.ativo && (
                          <button
                            onClick={() => triggerPortalSync(entry.company_id)}
                            disabled={syncingPortal}
                            className="text-xs px-2 py-0.5 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-40 transition-colors"
                          >
                            Sync agora
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
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
                      <td colSpan={6} className={`px-4 py-10 text-center text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
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

      {/* ════ TAB: NFe / CTe ════ */}
      {tab === "nfe" && (
        <div className="space-y-4">
          {!selectedId ? <NoCompanyPrompt isDark={isDark} card={card} /> : (<>
          <div className={`rounded-xl border p-4 ${card}`}>
            <div className="flex flex-wrap gap-3">
              <input type="text" placeholder="Busca (emitente, chave...)" value={nfeQ}
                onChange={(e) => { setNfeQ(e.target.value); setNfeOffset(0); }}
                className={`${inp} flex-1 min-w-[200px]`} />
              <select value={nfeStatus} onChange={(e) => { setNfeStatus(e.target.value); setNfeOffset(0); }} className={`${inp} w-36`}>
                <option value="">Todos status</option>
                <option value="pendente">Pendente</option>
                <option value="conferido">Conferido</option>
                <option value="cancelado">Cancelado</option>
              </select>
              <select value={nfeFonte} onChange={(e) => { setNfeFonte(e.target.value); setNfeOffset(0); }} className={`${inp} w-36`}>
                <option value="">Todas as fontes</option>
                <option value="sefaz">SEFAZ</option>
                <option value="portal_nacional">Portal Nacional</option>
              </select>
              <div className="flex flex-col gap-0.5">
                <label className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>De</label>
                <input type="date" value={nfeDataInicio} onChange={(e) => { setNfeDataInicio(e.target.value); setNfeOffset(0); }}
                  className={`${inp} w-32 text-xs py-1.5`} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>Até</label>
                <input type="date" value={nfeDataFim} onChange={(e) => { setNfeDataFim(e.target.value); setNfeOffset(0); }}
                  className={`${inp} w-32 text-xs py-1.5`} />
              </div>
              <button onClick={loadNfeDocs} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
                Buscar
              </button>
              <div className="flex gap-2 ml-auto">
                <button onClick={() => exportCsv("NFe,CTe")} disabled={exportingNfeCsv || !selectedId}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${isDark ? "bg-emerald-900/30 border border-emerald-700/60 text-emerald-400 hover:bg-emerald-900/50" : "bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100"}`}>
                  {exportingNfeCsv
                    ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    : (<svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>)}
                  CSV
                </button>
                <button onClick={() => exportXml("NFe,CTe")} disabled={exportingNfeXml || !selectedId}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${isDark ? "bg-blue-900/30 border border-blue-700/60 text-blue-400 hover:bg-blue-900/50" : "bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100"}`}>
                  {exportingNfeXml
                    ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    : (<svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>)}
                  XML
                </button>
                <button onClick={() => { setShowFetchKey(true); setFetchKeyResult(null); setFetchKeyError(""); setFetchKey(""); setFetchKeyCompanyId(selectedId || ""); }}
                  className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 font-medium transition-colors ${isDark ? "bg-violet-900/30 border border-violet-700/60 text-violet-400 hover:bg-violet-900/50" : "bg-violet-50 border border-violet-200 text-violet-700 hover:bg-violet-100"}`}>
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  Buscar por chave
                </button>
              </div>
            </div>
          </div>
          <div className={`rounded-xl border overflow-hidden ${card}`}>
            {nfeLoading ? (
              [...Array(5)].map((_, i) => (
                <div key={i} className="p-4 space-y-2">
                  <div className={`h-3 w-24 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                  <div className={`h-4 w-2/3 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-200"}`} />
                </div>
              ))
            ) : nfeDocs.length === 0 ? (
              <p className={`px-4 py-12 text-center text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                Nenhuma NF-e/CT-e encontrada.{!selectedId && " Selecione uma empresa."}
              </p>
            ) : (
              <div className={`divide-y ${isDark ? "divide-gray-700" : "divide-gray-100"}`}>
                {nfeDocs.map((doc) => (
                  <div key={doc.id} onClick={() => openDetail(doc)}
                    className={`p-4 cursor-pointer transition-colors ${isDark ? "hover:bg-gray-700/50" : "hover:bg-blue-50/60"}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center flex-wrap gap-2 mb-1">
                          <span className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-500"}`}>{fmtDay(doc.data_emissao)}</span>
                          <Badge label={doc.tipo ?? "NFe"} cls="bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300" />
                          <Badge label={doc.status} cls={STATUS_BADGE[doc.status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />
                        </div>
                        <p className={`font-semibold text-base leading-tight truncate ${isDark ? "text-white" : "text-gray-900"}`}>
                          {doc.emitente_nome || doc.emitente_cnpj}
                        </p>
                        {doc.destinatario_nome && (
                          <p className={`text-xs mt-0.5 truncate ${isDark ? "text-gray-500" : "text-gray-400"}`}>→ {doc.destinatario_nome}</p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className={`font-bold text-base tabular-nums ${isDark ? "text-white" : "text-gray-900"}`}>
                          {FMT_BRL.format(doc.valor_total ?? 0)}
                        </p>
                        <p className={`text-xs mt-1 font-mono ${isDark ? "text-gray-600" : "text-gray-400"}`}>
                          {doc.chave_acesso?.slice(0, 12)}…
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className={`flex items-center justify-between px-4 py-3 border-t text-sm ${isDark ? "border-gray-700" : "border-gray-200"}`}>
              <span className={isDark ? "text-gray-300" : "text-gray-500"}>{nfeDocs.length} registros</span>
              <div className="flex gap-2">
                <button disabled={nfeOffset === 0} onClick={() => setNfeOffset(Math.max(0, nfeOffset - DOCS_LIMIT))}
                  className={`px-3 py-1 rounded border text-sm disabled:opacity-40 ${isDark ? "border-gray-600 hover:bg-gray-700 text-gray-300" : "border-gray-300 hover:bg-gray-50 text-gray-700"}`}>
                  ← Anterior
                </button>
                <button disabled={nfeDocs.length < DOCS_LIMIT} onClick={() => setNfeOffset(nfeOffset + DOCS_LIMIT)}
                  className={`px-3 py-1 rounded border text-sm disabled:opacity-40 ${isDark ? "border-gray-600 hover:bg-gray-700 text-gray-300" : "border-gray-300 hover:bg-gray-50 text-gray-700"}`}>
                  Próximo →
                </button>
              </div>
            </div>
          </div>
          </>)}
        </div>
      )}

      {/* ════ TAB: CERTIFICADOS ════ */}
      {tab === "certificados" && (
        <div className="space-y-4">
          {!selectedId ? (
            <div className={`rounded-xl border p-8 text-center ${card}`}>
              <p className={`text-sm ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                Selecione uma empresa no topo da página para gerenciar o certificado digital.
              </p>
            </div>
          ) : (
            <>
            <div className={`rounded-xl border p-5 space-y-5 ${card}`}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                    Certificado Digital e-CNPJ A1
                  </h2>
                  <p className={`text-xs mt-0.5 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                    Necessário para sync Portal Nacional NFS-e (ADN) e busca por chave na SEFAZ.
                  </p>
                </div>
                {certStatus && (
                  <Badge
                    label={{ ok: "Válido", expirando: "Expirando em breve", expirado: "Expirado", sem_certificado: "Sem certificado" }[certStatus.status] ?? certStatus.status}
                    cls={CERT_STATUS_CLS[certStatus.status] ?? "bg-gray-100 text-gray-600"}
                  />
                )}
              </div>

              {certStatus?.cert_expiry && (
                <div className={`rounded-lg p-3 text-sm ${isDark ? "bg-gray-700/60" : "bg-gray-50"}`}>
                  <span className={isDark ? "text-gray-300" : "text-gray-500"}>Validade: </span>
                  <span className="font-mono font-medium">{fmtDay(certStatus.cert_expiry)}</span>
                  {certStatus.dias_para_vencer != null && (
                    <span className={`ml-2 text-xs ${certStatus.dias_para_vencer < 7 ? "text-red-500" : certStatus.dias_para_vencer < 30 ? "text-yellow-500" : isDark ? "text-gray-300" : "text-gray-500"}`}>
                      ({certStatus.dias_para_vencer} dias restantes)
                    </span>
                  )}
                </div>
              )}

              <div className={`rounded-lg border p-4 space-y-4 ${isDark ? "border-gray-700 bg-gray-900/30" : "border-gray-200 bg-gray-50"}`}>
                <h3 className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                  {certStatus?.has_certificate ? "Substituir certificado" : "Fazer upload do certificado"}
                </h3>
                <div className="space-y-3">
                  <div>
                    <label className={`block text-xs font-medium mb-1 ${isDark ? "text-gray-400" : "text-gray-600"}`}>Arquivo PFX / P12</label>
                    <input type="file" accept=".pfx,.p12"
                      onChange={(e) => setCertFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-blue-600 file:text-white file:text-xs cursor-pointer" />
                  </div>
                  <div>
                    <label className={`block text-xs font-medium mb-1 ${isDark ? "text-gray-400" : "text-gray-600"}`}>Senha do certificado</label>
                    <input type="password" value={certPassword} onChange={(e) => setCertPassword(e.target.value)}
                      placeholder="••••••••" className={`${inp} w-full font-mono`} />
                    <p className={`text-xs mt-1 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                      Criptografada (AES-256 Fernet). Após salvar, impossível recuperar — apenas substituir.
                    </p>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <button onClick={uploadCert} disabled={!certFile || !certPassword || certUploading}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40 flex items-center gap-2 transition-colors">
                      {certUploading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                      {certStatus?.has_certificate ? "Substituir" : "Fazer upload"}
                    </button>
                    {certStatus?.has_certificate && (
                      <button onClick={deleteCert}
                        className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors">
                        Remover certificado
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {certMsg && (
                <p className={`text-sm p-3 rounded-lg ${certMsg.startsWith("✅") ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400" : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400"}`}>
                  {certMsg}
                </p>
              )}
            </div>

            {/* ── Seção Portal Nacional NFS-e ── */}
            {certStatus?.has_certificate && (
              <div className={`rounded-xl border p-5 space-y-4 ${isDark ? "border-gray-700 bg-gray-800/50" : "border-gray-200 bg-gray-50"}`}>
                <h3 className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-800"}`}>
                  Portal Nacional NFS-e (ADN — gov.br/nfse)
                </h3>

                {/* Toggle ativo */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className={`text-sm font-medium ${isDark ? "text-gray-200" : "text-gray-800"}`}>
                      Sincronização automática
                    </p>
                    <p className={`text-xs mt-0.5 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                      Limite: 256 req/hora · mTLS ICP-Brasil A1
                    </p>
                  </div>
                  <button
                    onClick={togglePortalSync}
                    disabled={togglingPortalSync}
                    className={`relative w-12 h-6 rounded-full transition-colors disabled:opacity-50 ${certStatus.sync_portal_nfse_ativo ? "bg-emerald-500" : isDark ? "bg-gray-600" : "bg-gray-300"}`}
                  >
                    <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${certStatus.sync_portal_nfse_ativo ? "translate-x-6" : "translate-x-0.5"}`} />
                  </button>
                </div>

                {/* Seletor de hora */}
                {certStatus.sync_portal_nfse_ativo && (
                  <div className="flex items-center gap-3">
                    <label className={`text-xs font-medium ${isDark ? "text-gray-300" : "text-gray-600"}`}>
                      Horário do sync automático
                    </label>
                    <select
                      value={portalSyncHora}
                      onChange={(e) => savePortalHora(+e.target.value)}
                      className={`${inp} w-24 text-sm`}
                    >
                      {Array.from({ length: 24 }, (_, h) => (
                        <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
                      ))}
                    </select>
                    <span className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                      horário de Brasília
                    </span>
                  </div>
                )}

                {/* Alerta bloqueio cStat 656 */}
                {certStatus.sefaz_nfe_bloqueado_ate && new Date(certStatus.sefaz_nfe_bloqueado_ate) > new Date() && (() => {
                  const min = Math.ceil((new Date(certStatus.sefaz_nfe_bloqueado_ate!).getTime() - Date.now()) / 60000);
                  return (
                    <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 p-3 space-y-1">
                      <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                        ⛔ Sync bloqueado — aguarde {min} min
                      </p>
                      <p className="text-xs text-red-600 dark:text-red-300">
                        O Portal Nacional ADN retornou <strong>cStat 656 (consumo excessivo)</strong> para este CNPJ.
                        Tentar novamente antes de{" "}
                        <span className="font-mono font-medium">{fmtDate(certStatus.sefaz_nfe_bloqueado_ate)}</span>{" "}
                        pode resultar em <strong>bloqueio prolongado do CNPJ</strong> pela Receita Federal.
                      </p>
                    </div>
                  );
                })()}

                {/* Botão Sync agora */}
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={runPortalSyncNow}
                    disabled={runningPortalSync || (!!certStatus.sefaz_nfe_bloqueado_ate && new Date(certStatus.sefaz_nfe_bloqueado_ate) > new Date())}
                    className="px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                  >
                    {runningPortalSync
                      ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      : "▶ Sync agora"}
                  </button>
                  {certStatus.portal_nfse_last_sync_at && (
                    <span className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                      Último sync: {fmtDate(certStatus.portal_nfse_last_sync_at)}
                    </span>
                  )}
                </div>
                {portalSyncMsg && (
                  <p className={`text-sm p-2 rounded ${portalSyncMsg.startsWith("✅") ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                    {portalSyncMsg}
                  </p>
                )}

                {/* Pré-requisitos simplificados (sem SQL) */}
                {!certStatus.sync_portal_nfse_ativo && (
                  <div className={`rounded-lg p-3 text-xs ${isDark ? "bg-gray-700/50 text-gray-300" : "bg-white text-gray-600 border border-gray-200"}`}>
                    <p className={`font-medium mb-1 ${isDark ? "text-gray-200" : "text-gray-700"}`}>Antes de ativar, verifique:</p>
                    <ol className="list-decimal list-inside space-y-0.5">
                      <li>Empresa registrada em <a href="https://www.gov.br/nfse" target="_blank" rel="noreferrer" className="text-blue-500 underline">gov.br/nfse</a></li>
                      <li>Município aderiu: <a href="https://www.gov.br/nfse/pt-br/municipios/monitoramento-adesoes" target="_blank" rel="noreferrer" className="text-blue-500 underline">verificar adesão</a></li>
                      <li>Ao ativar, o sync roda automaticamente no horário configurado</li>
                    </ol>
                  </div>
                )}
              </div>
            )}

            {/* ── Seção NDD Digital ── */}
            {certStatus?.has_certificate && (
              <div className={`rounded-xl border p-5 space-y-4 ${isDark ? "border-gray-700 bg-gray-800/50" : "border-gray-200 bg-gray-50"}`}>
                <h3 className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-800"}`}>
                  ND Digital — Notas Fiscais de Serviço Recebidas
                </h3>
                <p className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                  Portal centralizador privado — cobre 32 municípios com uma única conta. Sync automático diário às 05:00.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={syncNdd}
                    disabled={nddSyncing}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
                  >
                    {nddSyncing
                      ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      : "▶ Sync NDD agora"}
                  </button>
                  {certStatus.ndd_last_sync_at && (
                    <span className={`text-xs ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                      Último: {fmtDate(certStatus.ndd_last_sync_at)}
                    </span>
                  )}
                </div>
                {nddSyncMsg && (
                  <p className={`text-xs ${nddSyncMsg.startsWith("✅") ? "text-emerald-500" : "text-red-500"}`}>{nddSyncMsg}</p>
                )}
              </div>
            )}

            {/* ── Seção Municípios — API Direta ── */}
            {certStatus?.has_certificate && (
              <div className={`rounded-xl border overflow-hidden ${card}`}>
                <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                  <h3 className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                    Municípios — API Direta (não-NDD)
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={seedMunicipalities}
                      disabled={seedingMun}
                      className={`text-xs hover:underline disabled:opacity-50 ${isDark ? "text-blue-400" : "text-blue-500"}`}
                    >
                      {seedingMun ? "Populando..." : "Seed (32 municípios)"}
                    </button>
                    <span className={`text-xs ${isDark ? "text-gray-600" : "text-gray-400"}`}>·</span>
                    <button
                      onClick={syncMunicipalities}
                      disabled={munSyncing}
                      className="text-xs px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
                    >
                      {munSyncing ? "Sincronizando..." : "▶ Sync Municipal"}
                    </button>
                  </div>
                </div>
                {munLoading ? (
                  <div className="p-4 space-y-2">
                    {[1,2,3].map(i => <div key={i} className={`h-8 rounded animate-pulse ${isDark ? "bg-gray-700" : "bg-gray-100"}`} />)}
                  </div>
                ) : municipalities.length === 0 ? (
                  <p className={`px-4 py-8 text-center text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                    Nenhum município configurado. Clique em "Seed" para popular os 32 municípios do registry.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className={`border-b ${isDark ? "border-gray-700 text-gray-400" : "border-gray-100 text-gray-500"}`}>
                          <th className="px-4 py-2 text-left font-medium">Município</th>
                          <th className="px-4 py-2 text-left font-medium">UF</th>
                          <th className="px-4 py-2 text-left font-medium">Tipo API</th>
                          <th className="px-4 py-2 text-right font-medium">Docs</th>
                          <th className="px-4 py-2 text-left font-medium">Último sync</th>
                          <th className="px-4 py-2 text-center font-medium">Ativo</th>
                          <th className="px-4 py-2 text-center font-medium">Teste</th>
                        </tr>
                      </thead>
                      <tbody>
                        {municipalities.map(m => (
                          <tr key={m.municipio_ibge} className={`border-b last:border-0 ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                            <td className={`px-4 py-2 font-medium ${isDark ? "text-gray-200" : "text-gray-800"}`}>{m.municipio_nome}</td>
                            <td className={`px-4 py-2 ${isDark ? "text-gray-300" : "text-gray-500"}`}>{m.uf}</td>
                            <td className="px-4 py-2">
                              <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                                m.sistema_tipo === "nddigital"
                                  ? isDark ? "bg-gray-700 text-gray-400" : "bg-gray-100 text-gray-500"
                                  : isDark ? "bg-blue-900/40 text-blue-300" : "bg-blue-50 text-blue-700"
                              }`}>{m.sistema_tipo}</span>
                            </td>
                            <td className={`px-4 py-2 text-right tabular-nums ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                              {m.docs_total ?? 0}
                            </td>
                            <td className={`px-4 py-2 ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                              {m.last_sync_at ? fmtDate(m.last_sync_at) : "—"}
                              {m.ultimo_erro && (
                                <span className="block text-red-400 truncate max-w-[120px]" title={m.ultimo_erro}>
                                  {m.ultimo_erro.slice(0, 30)}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-center">
                              <button
                                onClick={() => toggleMunicipality(m)}
                                className={`relative w-9 h-5 rounded-full transition-colors ${m.ativo ? "bg-emerald-500" : isDark ? "bg-gray-600" : "bg-gray-300"}`}
                              >
                                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${m.ativo ? "translate-x-4" : "translate-x-0.5"}`} />
                              </button>
                            </td>
                            <td className="px-4 py-2 text-center">
                              {m.sistema_tipo !== "nddigital" ? (
                                <div className="flex flex-col items-center gap-0.5">
                                  <button
                                    onClick={() => testMunicipality(m.municipio_ibge)}
                                    disabled={testingIbge === m.municipio_ibge}
                                    className={`text-xs hover:underline disabled:opacity-50 ${isDark ? "text-blue-400" : "text-blue-500"}`}
                                  >
                                    {testingIbge === m.municipio_ibge ? "..." : "Testar"}
                                  </button>
                                  {testResults[m.municipio_ibge] && (
                                    <span className={`text-xs ${testResults[m.municipio_ibge].ok ? "text-emerald-500" : "text-red-400"}`}
                                      title={testResults[m.municipio_ibge].msg}>
                                      {testResults[m.municipio_ibge].ok ? `✅ ${testResults[m.municipio_ibge].docs}` : "❌"}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className={`text-xs ${isDark ? "text-gray-600" : "text-gray-400"}`}>NDD</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {munSyncMsg && (
                  <p className={`px-4 py-2 text-xs border-t ${isDark ? "border-gray-700" : "border-gray-100"} ${munSyncMsg.startsWith("✅") ? "text-emerald-500" : "text-red-500"}`}>
                    {munSyncMsg}
                  </p>
                )}
              </div>
            )}

            {/* ── Botão Sync Tudo ── */}
            {certStatus?.has_certificate && (
              <div className="flex flex-col items-end gap-2">
                <button
                  onClick={syncAllNfse}
                  disabled={syncAllLoading}
                  className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-emerald-600 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-opacity"
                >
                  {syncAllLoading
                    ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    : "⚡"}
                  Sync NFS-e Completo (NDD + Portal + Municipal)
                </button>
                {syncAllMsg && (
                  <p className={`text-xs ${syncAllMsg.startsWith("✅") ? "text-emerald-500" : "text-red-500"}`}>{syncAllMsg}</p>
                )}
              </div>
            )}

            {/* ── Histórico das últimas 5 tentativas ── */}
            {certStatus?.has_certificate && (
              <div className={`rounded-xl border overflow-hidden mt-0 ${card}`}>
                <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? "border-gray-700" : "border-gray-200"}`}>
                  <h3 className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-gray-300" : "text-gray-500"}`}>
                    Últimas tentativas — Portal Nacional NFS-e
                  </h3>
                  <button onClick={loadPortalLogs} className="text-xs text-blue-500 hover:underline">Atualizar</button>
                </div>
                {portalLogs.length === 0 ? (
                  <p className={`px-4 py-6 text-center text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                    Nenhum sync realizado ainda.
                  </p>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className={`border-b ${isDark ? "border-gray-700 text-gray-400" : "border-gray-100 text-gray-500"}`}>
                        <th className="px-4 py-2 text-left font-medium">Executado em</th>
                        <th className="px-4 py-2 text-left font-medium">Status</th>
                        <th className="px-4 py-2 text-right font-medium">Notas</th>
                        <th className="px-4 py-2 text-left font-medium">Erro</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portalLogs.map((log, i) => (
                        <tr key={i} className={`border-b last:border-0 ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                          <td className={`px-4 py-2 font-mono whitespace-nowrap ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                            {fmtDate(log.executado_em)}
                          </td>
                          <td className="px-4 py-2">
                            <Badge label={log.status} cls={SYNC_STATUS_CLS[log.status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"} />
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums">
                            {(log.documentos_novos ?? 0) > 0
                              ? (<span className="text-emerald-500">+{log.documentos_novos}</span>)
                              : (<span className={isDark ? "text-gray-600" : "text-gray-400"}>—</span>)}
                          </td>
                          <td className="px-4 py-2 max-w-[200px]">
                            {log.erro_msg
                              ? (<span className="text-red-400 truncate block" title={log.erro_msg}>{log.erro_msg.slice(0, 50)}</span>)
                              : (<span className={isDark ? "text-gray-600" : "text-gray-400"}>—</span>)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
