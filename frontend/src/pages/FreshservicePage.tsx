import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import type {
  AgentStats,
  CompanyRequester,
  CSATSummary,
  DailySummary,
  FreshserviceSummary,
  GroupSLA,
  LiveMetrics,
  Period,
  SyncStatus,
  TicketFilters,
} from "../types/freshservice";
import AgentBoard from "../components/freshservice/AgentBoard";
import CSATSection from "../components/freshservice/CSATSection";
import KPICard from "../components/freshservice/KPICard";
import PeriodSelector from "../components/freshservice/PeriodSelector";
import SLAGroupTable from "../components/freshservice/SLAGroupTable";
import TicketsTable from "../components/freshservice/TicketsTable";

function defaultPeriod(): Period {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const from = new Date(today);
  from.setDate(from.getDate() - 30);
  const to = new Date(today);
  to.setDate(to.getDate() + 1);
  return { from: from.toISOString(), to: to.toISOString() };
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function fmtMin(min: number | null) {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function fmtHours(h: number | undefined) {
  if (h == null) return "";
  const days = Math.floor(h / 24);
  const rem = h % 24;
  return days > 0 ? `${days}d ${rem}h` : `${h}h`;
}

type DrillType = "total" | "sla" | "csat" | "resolution" | "group" | "agent" | "priority" | "csat_rating" | null;

export default function FreshservicePage() {
  const { token, user } = useAuth();

  const [period, setPeriod] = useState<Period>(defaultPeriod);
  const [month, setMonth] = useState<string>(currentMonth);
  const [drill, setDrill] = useState<DrillType>(null);
  const [drillFilter, setDrillFilter] = useState<TicketFilters>({});

  const [summary, setSummary] = useState<FreshserviceSummary | null>(null);
  const [slaGroups, setSlaGroups] = useState<GroupSLA[]>([]);
  const [agents, setAgents] = useState<AgentStats[]>([]);
  const [requesters, setRequesters] = useState<CompanyRequester[]>([]);
  const [csat, setCsat] = useState<CSATSummary | null>(null);
  const [live, setLive] = useState<LiveMetrics | null>(null);
  const [aiSummary, setAiSummary] = useState<DailySummary | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

  const [loadingMain, setLoadingMain] = useState(true);
  const [loadingLive, setLoadingLive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMain = useCallback(async () => {
    setLoadingMain(true);
    setError(null);
    const qs = `from=${encodeURIComponent(period.from)}&to=${encodeURIComponent(period.to)}`;
    const mqs = `month=${month}`;

    const [sum, sla, ag, req, cs, status] = await Promise.allSettled([
      apiFetch<FreshserviceSummary>(`/api/freshservice/dashboard/summary?${qs}`, { token }),
      apiFetch<GroupSLA[]>(`/api/freshservice/dashboard/sla-by-group?${qs}`, { token }),
      apiFetch<AgentStats[]>(`/api/freshservice/dashboard/agents?${mqs}`, { token }),
      apiFetch<CompanyRequester[]>(`/api/freshservice/dashboard/top-requesters?${qs}&limit=5`, { token }),
      apiFetch<CSATSummary>(`/api/freshservice/dashboard/csat?${qs}`, { token }),
      apiFetch<SyncStatus>(`/api/freshservice/sync/status`, { token }),
    ]);

    if (sum.status === "fulfilled") setSummary(sum.value);
    if (sla.status === "fulfilled") setSlaGroups(Array.isArray(sla.value) ? sla.value : []);
    if (ag.status === "fulfilled") setAgents(Array.isArray(ag.value) ? ag.value : []);
    if (req.status === "fulfilled") setRequesters(Array.isArray(req.value) ? req.value : []);
    if (cs.status === "fulfilled") setCsat(cs.value);
    if (status.status === "fulfilled") setSyncStatus(status.value);

    const failed = [sum, sla, ag, req, cs, status].filter(
      (r): r is PromiseRejectedResult => r.status === "rejected"
    );
    if (failed.length > 0) {
      const reason = failed[0].reason;
      const msg = reason instanceof ApiError ? reason.message : "Erro ao carregar dados.";
      setError(
        failed.length === 6
          ? msg
          : `${msg} (${failed.length} de 6 seções não carregaram — as demais foram exibidas normalmente)`
      );
    }
    setLoadingMain(false);
  }, [token, period, month]);

  const fetchLive = useCallback(async () => {
    setLoadingLive(true);
    try {
      const [lv, ai] = await Promise.all([
        apiFetch<LiveMetrics>(`/api/freshservice/dashboard/live`, { token }),
        apiFetch<{ summary_json?: DailySummary }>(`/api/freshservice/agent/daily-summary`, { token }),
      ]);
      setLive(lv);
      if (ai?.summary_json) setAiSummary(ai.summary_json);
    } catch {
      // live metrics are optional — don't block page
    } finally {
      setLoadingLive(false);
    }
  }, [token]);

  useEffect(() => { fetchMain(); }, [fetchMain]);
  useEffect(() => { fetchLive(); }, [fetchLive]);

  function openDrill(type: DrillType, extraFilter: TicketFilters = {}) {
    if (drill === type && JSON.stringify(drillFilter) === JSON.stringify(extraFilter)) {
      setDrill(null);
      setDrillFilter({});
      return;
    }
    setDrill(type);
    setDrillFilter({ from: period.from, to: period.to, ...extraFilter });
  }

  const isAdmin = user?.role === "admin";

  async function triggerBackfill() {
    if (!confirm("Iniciar backfill completo? Pode demorar horas para 150k tickets.")) return;
    try {
      await apiFetch("/api/freshservice/sync/backfill", { method: "POST", token });
      alert("Backfill iniciado em background. Acompanhe o status abaixo.");
      fetchMain();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erro ao iniciar backfill.");
    }
  }

  async function triggerDailySync() {
    try {
      await apiFetch("/api/freshservice/sync/daily", { method: "POST", token });
      alert("Sync diário iniciado.");
      setTimeout(fetchMain, 3000);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erro ao iniciar sync.");
    }
  }

  return (
    <div className="p-4 sm:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Freshservice Analytics
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Dashboard de chamados — resolved + closed
          </p>
        </div>

        {isAdmin && (
          <div className="flex gap-2">
            {syncStatus && (
              <span className={`self-center text-[11px] px-2 py-1 rounded-full font-medium ${
                syncStatus.status === "running"
                  ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
                  : syncStatus.status === "completed"
                  ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                  : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
              }`}>
                {syncStatus.sync_type} · {syncStatus.status}
                {syncStatus.tickets_upserted ? ` · ${syncStatus.tickets_upserted.toLocaleString("pt-BR")} tickets` : ""}
              </span>
            )}
            <button
              type="button"
              onClick={triggerDailySync}
              className="px-3 py-1.5 rounded-lg text-[13px] border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-brand-green/60 transition-colors"
            >
              Sync diário
            </button>
            <button
              type="button"
              onClick={triggerBackfill}
              className="px-3 py-1.5 rounded-lg text-[13px] bg-brand-deep text-white hover:bg-brand-green transition-colors"
            >
              Backfill completo
            </button>
          </div>
        )}
      </div>

      {/* Seletor de período */}
      <PeriodSelector value={period} onChange={(p) => { setPeriod(p); setDrill(null); }} />

      {/* Resumo IA */}
      {aiSummary && (
        <div className={`rounded-xl border px-4 py-3 ${
          aiSummary.anomaly
            ? "border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10"
            : "border-brand-green/30 bg-green-50 dark:bg-green-900/10"
        }`}>
          <div className="flex items-start gap-2">
            <span className="text-lg shrink-0">{aiSummary.anomaly ? "⚠️" : "✅"}</span>
            <div>
              <p className="text-[13px] text-gray-800 dark:text-gray-200 font-medium">
                {aiSummary.summary}
              </p>
              {aiSummary.anomaly && aiSummary.anomaly_detail && (
                <p className="text-[12px] text-amber-700 dark:text-amber-400 mt-0.5">
                  {aiSummary.anomaly_detail}
                </p>
              )}
            </div>
            <span className="ml-auto text-[10px] text-gray-400 dark:text-gray-500 shrink-0">by Jarvis IA</span>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      {loadingMain ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KPICard
            label="Fechados total"
            value={summary?.total_closed?.toLocaleString("pt-BR") ?? "—"}
            active={drill === "total"}
            onClick={() => openDrill("total")}
            colorClass="text-brand-deep dark:text-brand-mid"
          />
          <KPICard
            label="CSAT médio"
            value={
              summary?.csat_avg != null
                ? `${summary.csat_avg.toFixed(1)} / 3`
                : "—"
            }
            sub={
              csat?.total_rated
                ? `${csat.total_rated.toLocaleString("pt-BR")} avaliações`
                : undefined
            }
            active={drill === "csat"}
            onClick={() => openDrill("csat")}
            colorClass={
              (summary?.csat_avg ?? 0) >= 2.5
                ? "text-green-600 dark:text-green-400"
                : "text-amber-600 dark:text-amber-400"
            }
          />
          <KPICard
            label="SLA Breach"
            value={summary?.sla_breach_pct != null ? `${summary.sla_breach_pct}%` : "—"}
            active={drill === "sla"}
            onClick={() => openDrill("sla", { sla_breached: true })}
            colorClass={
              (summary?.sla_breach_pct ?? 0) > 20
                ? "text-red-600 dark:text-red-400"
                : "text-green-600 dark:text-green-400"
            }
          />
          <KPICard
            label="Tempo médio resolução"
            value={fmtMin(summary?.avg_resolution_min ?? null)}
            sub={
              summary?.avg_fr_min != null
                ? `1ª resp: ${fmtMin(summary.avg_fr_min)}`
                : undefined
            }
            active={drill === "resolution"}
            onClick={() => openDrill("resolution")}
            colorClass="text-brand-deep dark:text-brand-mid"
          />
        </div>
      )}

      {/* Drill-down tabela */}
      {drill && (
        <div className="rounded-xl border border-brand-green/40 bg-white dark:bg-gray-900 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {drill === "total" && "Todos os chamados fechados"}
              {drill === "sla" && "Chamados com breach de SLA"}
              {drill === "csat" && "Chamados avaliados"}
              {drill === "resolution" && "Chamados por tempo de resolução"}
              {drill === "group" && "Chamados do grupo"}
              {drill === "agent" && "Chamados do técnico"}
              {drill === "csat_rating" && "Chamados por avaliação"}
            </h3>
            <button
              type="button"
              onClick={() => { setDrill(null); setDrillFilter({}); }}
              className="text-[12px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              Fechar ✕
            </button>
          </div>
          <TicketsTable filters={drillFilter} />
        </div>
      )}

      {/* SLA por Grupo */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
          SLA por Grupo / Tenant
        </h2>
        {loadingMain ? (
          <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
        ) : (
          <SLAGroupTable
            data={slaGroups}
            onGroupClick={(gid) => openDrill("group", { group_id: gid ?? undefined })}
          />
        )}
      </div>

      {/* Técnicos + Top Solicitantes */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Técnicos — {month}
            </h2>
            <div className="flex gap-1">
              {[-1, 0, 1].map((offset) => {
                const d = new Date();
                d.setMonth(d.getMonth() + offset);
                const m = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMonth(m)}
                    className={`px-2 py-0.5 rounded text-[11px] border transition-colors ${
                      month === m
                        ? "bg-brand-green text-white border-brand-green"
                        : "border-gray-200 dark:border-gray-700 text-gray-500 hover:border-brand-green/60"
                    }`}
                  >
                    {offset === -1 ? "Ant." : offset === 0 ? "Atual" : "Próx."}
                  </button>
                );
              })}
            </div>
          </div>
          {loadingMain ? (
            <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ) : (
            <AgentBoard
              data={agents}
              onAgentClick={(aid) => openDrill("agent", { responder_id: aid ?? undefined })}
            />
          )}
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Top 5 Empresas Solicitantes
          </h2>
          {loadingMain ? (
            <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ) : requesters.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">Sem dados no período.</p>
          ) : (
            <div className="space-y-2">
              {requesters.map((r, i) => (
                <button
                  key={r.company_id ?? `anon-${i}`}
                  type="button"
                  onClick={() => openDrill("group", { company_id: r.company_id ?? undefined })}
                  className="flex items-center gap-3 w-full text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg px-1 -mx-1 py-1 transition-colors"
                >
                  <span className="text-[11px] font-bold text-gray-400 dark:text-gray-500 w-4">
                    {i + 1}
                  </span>
                  <span className="flex-1 text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate">
                    {r.company_name}
                  </span>
                  <span className="text-[13px] font-bold text-brand-deep dark:text-brand-mid shrink-0">
                    {r.count.toLocaleString("pt-BR")}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Live — Mais Antigos + Aguardando Fornecedor */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Top 10 Chamados Mais Antigos
            <span className="ml-2 text-[10px] font-normal text-gray-400">(live)</span>
          </h2>
          {loadingLive ? (
            <div className="h-24 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ) : !live?.oldest_open?.length ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">Nenhum chamado aberto.</p>
          ) : (
            <div className="space-y-2">
              {live.oldest_open.map((t) => (
                <div key={t.id} className="flex items-center gap-2">
                  <span className="text-[12px] font-mono text-gray-400 dark:text-gray-500 shrink-0">
                    #{t.id}
                  </span>
                  <span className="flex-1 text-[13px] text-gray-800 dark:text-gray-200 truncate">
                    {t.subject}
                  </span>
                  <span className="text-[11px] text-amber-600 dark:text-amber-400 shrink-0 font-medium">
                    {t.time_open_hours != null ? fmtHours(t.time_open_hours) : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Aguardando Fornecedor
            <span className="ml-2 text-[10px] font-normal text-gray-400">(live)</span>
          </h2>
          {loadingLive ? (
            <div className="h-24 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ) : (
            <div className="space-y-3">
              <div className="text-3xl font-bold text-brand-deep dark:text-brand-mid">
                {live?.waiting_vendor_count ?? 0}
              </div>
              {live?.by_vendor && live.by_vendor.length > 0 && (
                <div className="space-y-1.5 mt-2">
                  {live.by_vendor.slice(0, 6).map((v) => (
                    <div key={v.group_id} className="flex items-center justify-between text-[12px]">
                      <span className="text-gray-600 dark:text-gray-400 truncate">{v.group_id}</span>
                      <span className="font-semibold text-gray-900 dark:text-gray-100 ml-2 shrink-0">
                        {v.count}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* CSAT */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Pesquisa de Satisfação — CSAT
        </h2>
        {loadingMain ? (
          <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
        ) : (
          <CSATSection
            data={csat}
            onRatingClick={(rating) =>
              openDrill("csat_rating", { csat_rating: rating })
            }
          />
        )}
      </div>
    </div>
  );
}
