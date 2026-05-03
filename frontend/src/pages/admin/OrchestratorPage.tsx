import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { AgentEvent, DeploymentWindow } from "../../types/agents";

// ── estilos ──────────────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  high:     "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  medium:   "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  low:      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
};

const STATUS_DOT: Record<string, string> = {
  ok:        "bg-green-500",
  success:   "bg-green-500",
  error:     "bg-red-500",
  failing:   "bg-red-600 animate-pulse",
  stale:     "bg-amber-400",
  never_run: "bg-gray-300 dark:bg-gray-600",
  running:   "bg-blue-500 animate-pulse",
  unknown:   "bg-gray-400",
  idle:      "bg-gray-300 dark:bg-gray-600",
};

const STATUS_TEXT: Record<string, string> = {
  ok:        "text-green-600 dark:text-green-400",
  success:   "text-green-600 dark:text-green-400",
  error:     "text-red-600 dark:text-red-400",
  failing:   "text-red-600 dark:text-red-400",
  stale:     "text-amber-600 dark:text-amber-400",
  never_run: "text-gray-400",
  running:   "text-blue-600 dark:text-blue-400",
  unknown:   "text-gray-400",
  idle:      "text-gray-400",
};

const STATUS_LABEL: Record<string, string> = {
  ok:        "OK",
  success:   "OK",
  error:     "Erro",
  failing:   "Falhando",
  stale:     "Atrasado",
  never_run: "Nunca rodou",
  running:   "Rodando",
  unknown:   "Desconhecido",
  idle:      "Aguardando",
};

const PIPELINE_LABEL: Record<string, string> = {
  monitoring: "Monitoramento",
  security:   "Segurança",
  cicd:       "CI/CD",
  dba:        "DBA",
  governance: "Governança",
  evolution:  "Evolução",
};

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function statusOrder(s: string) {
  return { running: 0, failing: 1, error: 2, stale: 3, never_run: 4, idle: 5, ok: 6, success: 6, unknown: 7 }[s] ?? 8;
}

// ── componentes menores ───────────────────────────────────────────────────────

function StatusRow({ name, status, sub }: { name: string; status: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-50 dark:border-gray-700/50 last:border-0">
      <div className="min-w-0">
        <span className="text-xs text-gray-700 dark:text-gray-300 font-medium block truncate">{name}</span>
        {sub && <span className="text-[10px] text-gray-400 truncate block">{sub}</span>}
      </div>
      <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
        <span className={`w-2 h-2 rounded-full ${STATUS_DOT[status] ?? STATUS_DOT.unknown}`} />
        <span className={`text-[10px] font-medium ${STATUS_TEXT[status] ?? "text-gray-400"}`}>
          {STATUS_LABEL[status] ?? status}
        </span>
      </div>
    </div>
  );
}

// ── página principal ──────────────────────────────────────────────────────────

export default function OrchestratorPage() {
  const { token } = useAuth();

  const [findings, setFindings]       = useState<AgentEvent[]>([]);
  const [activeWindow, setActiveWindow] = useState<DeploymentWindow | null>(null);
  const [pendingProposals, setPendingProposals] = useState(0);
  const [pendingChanges, setPendingChanges]     = useState(0);
  const [running, setRunning]         = useState(false);
  const [windowLoading, setWindowLoading] = useState(false);
  const [error, setError]             = useState("");

  // unified
  const [dbAgents, setDbAgents]               = useState<any[]>([]);
  const [langgraphHealth, setLanggraphHealth] = useState<Record<string, any>>({});
  const [reportTime, setReportTime]           = useState<string | null>(null);
  const [runningNow, setRunningNow]           = useState<any[]>([]);
  const [pipelines, setPipelines]             = useState<Record<string, any>>({});

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [f, w, p, c, all] = await Promise.all([
        apiFetch<{ findings: AgentEvent[] }>("/api/agents/orchestrator/findings?limit=30", { token }),
        apiFetch<{ active_window: DeploymentWindow | null }>("/api/agents/windows/active", { token }),
        apiFetch<{ proposals: any[] }>("/api/agents/proposals?status=pending&limit=1", { token }),
        apiFetch<{ changes: any[] }>("/api/agents/changes?status=pending&limit=1", { token }),
        apiFetch<any>("/api/agents/orchestrator/all-agents", { token }),
      ]);
      setFindings(f.findings || []);
      setActiveWindow(w.active_window);
      setPendingProposals(p.proposals?.length ?? 0);
      setPendingChanges(c.changes?.length ?? 0);
      setDbAgents(all.db_agents || []);
      setLanggraphHealth(all.langgraph_health || {});
      setReportTime(all.report_time || null);
      setRunningNow(all.running_now || []);
      setPipelines(all.pipelines || {});
    } catch (e: any) {
      setError(e.message);
    }
  }, [token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const runPipeline = async (pipeline: string) => {
    if (!token) return;
    setRunning(true);
    setError("");
    try {
      await apiFetch("/api/agents/orchestrator/run", {
        token, method: "POST", json: { pipeline, agent_name: "cto" },
      });
      setTimeout(load, 1500);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const toggleWindow = async () => {
    if (!token) return;
    setWindowLoading(true);
    try {
      if (activeWindow) {
        await apiFetch("/api/agents/windows/close", { token, method: "POST", json: {} });
      } else {
        const reason = prompt("Motivo da janela de deploy:");
        if (!reason) { setWindowLoading(false); return; }
        await apiFetch("/api/agents/windows/open", {
          token, method: "POST",
          json: { reason, duration_minutes: 60, started_by: "admin" },
        });
      }
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setWindowLoading(false);
    }
  };

  // ── dados derivados ───────────────────────────────────────────────────────

  const allPipelineNames = ["monitoring", "security", "cicd", "dba", "governance", "evolution"];

  // Agentes LangGraph ordenados por criticidade
  const lgEntries = Object.entries(langgraphHealth)
    .map(([name, info]: [string, any]) => ({
      name,
      status: typeof info === "object" ? info.status : info,
      lastRun: typeof info === "object" ? info.last_run : null,
      consecutive_errors: typeof info === "object" ? info.consecutive_errors : 0,
    }))
    .sort((a, b) => statusOrder(a.status) - statusOrder(b.status));

  // DB agents com status derivado do último run
  const dbAgentRows = dbAgents.map(a => {
    const lastStatus = a.last_run?.status ?? "never_run";
    const isRunning = runningNow.some(r => r.agent_id === a.id);
    return { ...a, derivedStatus: isRunning ? "running" : lastStatus };
  });

  // Contadores de saúde LangGraph
  const lgCounts = lgEntries.reduce((acc, { status }) => {
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Rodando agora — nomes amigáveis
  const runningLabels = runningNow.map(r => {
    if (r.pipeline_name) return `Pipeline: ${r.pipeline_name}`;
    const agent = dbAgents.find(a => a.id === r.agent_id);
    if (agent) return agent.name;
    return r.agent_id?.slice(0, 8) ?? "?";
  });

  return (
    <div className="p-6 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Orquestrador</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Supervisão unificada de todos os agentes
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {allPipelineNames.slice(0, 3).map(p => (
            <button
              key={p}
              onClick={() => runPipeline(p)}
              disabled={running}
              className="px-3 py-1.5 rounded-lg border border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 text-xs font-medium hover:bg-indigo-50 dark:hover:bg-indigo-900/20 disabled:opacity-50 transition-colors capitalize"
            >
              ▶ {PIPELINE_LABEL[p] ?? p}
            </button>
          ))}
          <button
            onClick={() => runPipeline("manual")}
            disabled={running}
            className="px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {running ? "Executando..." : "Executar CTO"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* ── Rodando Agora ── */}
      {runningLabels.length > 0 && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-3 flex items-center gap-3 flex-wrap">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />
          <span className="text-sm font-semibold text-blue-800 dark:text-blue-300">Rodando agora:</span>
          {runningLabels.map((l, i) => (
            <span key={i} className="text-xs bg-blue-100 dark:bg-blue-800/40 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full font-medium">{l}</span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* ── Coluna Esquerda ── */}
        <div className="space-y-4">

          {/* Deploy Window */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Janela de Deploy</h2>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${activeWindow
                ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
                : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"}`}>
                {activeWindow ? "ATIVA" : "Inativa"}
              </span>
            </div>
            {activeWindow && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                {activeWindow.reason} — desde {fmt(activeWindow.started_at)}
              </p>
            )}
            <button
              onClick={toggleWindow}
              disabled={windowLoading}
              className={`w-full text-xs py-1.5 rounded-lg font-medium transition-colors disabled:opacity-50 ${
                activeWindow ? "bg-green-600 text-white hover:bg-green-700" : "bg-yellow-500 text-white hover:bg-yellow-600"
              }`}
            >
              {windowLoading ? "..." : activeWindow ? "Fechar Janela" : "Abrir Janela de Deploy"}
            </button>
          </div>

          {/* Pipelines */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Pipelines</h2>
            <div className="space-y-0.5">
              {allPipelineNames.map(name => {
                const run = pipelines[name];
                const st  = run?.status ?? "idle";
                return (
                  <div key={name} className="flex items-center justify-between py-1.5 border-b border-gray-50 dark:border-gray-700/50 last:border-0">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[st] ?? STATUS_DOT.unknown}`} />
                      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{PIPELINE_LABEL[name]}</span>
                    </div>
                    <span className="text-[10px] text-gray-400">{fmt(run?.started_at)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Automações (DB agents) */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              Automações
              <span className="ml-1.5 text-[10px] text-gray-400 font-normal">({dbAgentRows.length})</span>
            </h2>
            {dbAgentRows.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-4">Nenhuma automação cadastrada</p>
            ) : (
              <div className="space-y-0.5">
                {dbAgentRows.map(a => (
                  <StatusRow
                    key={a.id}
                    name={a.name}
                    status={a.enabled ? a.derivedStatus : "unknown"}
                    sub={a.enabled
                      ? (a.last_run ? fmt(a.last_run.started_at) : "Nunca executado")
                      : "Desabilitado"}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Pendências */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Pendências</h2>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                <span className="text-xs text-gray-600 dark:text-gray-400">Proposals</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  pendingProposals > 0 ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                }`}>{pendingProposals}</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                <span className="text-xs text-gray-600 dark:text-gray-400">Changes</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  pendingChanges > 0 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                }`}>{pendingChanges}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Coluna Central — Feed de Eventos ── */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex flex-col">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Feed de Eventos</h2>
          <div className="flex-1 overflow-y-auto space-y-2 max-h-[600px]">
            {findings.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-8">Sem eventos recentes</p>
            )}
            {findings.map(evt => (
              <div key={evt.id} className="border border-gray-100 dark:border-gray-700 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${PRIORITY_STYLE[evt.priority] ?? PRIORITY_STYLE.low}`}>
                    {evt.priority}
                  </span>
                  <span className="text-xs text-gray-400">{fmt(evt.created_at)}</span>
                </div>
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300">{evt.event_type}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">fonte: {evt.source}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Coluna Direita — Agentes LangGraph ── */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Agentes IA
              <span className="ml-1.5 text-[10px] text-gray-400 font-normal">({lgEntries.length})</span>
            </h2>
            {reportTime && (
              <span className="text-[10px] text-gray-400">relatório {fmt(reportTime)}</span>
            )}
          </div>

          {/* Contadores resumo */}
          {lgEntries.length > 0 && (
            <div className="flex gap-1.5 mb-3 flex-wrap">
              {(lgCounts.ok || lgCounts.success) ? (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 font-medium">
                  ✓ {(lgCounts.ok ?? 0) + (lgCounts.success ?? 0)} OK
                </span>
              ) : null}
              {lgCounts.running ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium animate-pulse">● {lgCounts.running} rodando</span> : null}
              {lgCounts.failing ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">✗ {lgCounts.failing} falhando</span> : null}
              {lgCounts.error ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">! {lgCounts.error} erro</span> : null}
              {lgCounts.stale ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">⚠ {lgCounts.stale} atrasado</span> : null}
              {lgCounts.never_run ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">○ {lgCounts.never_run} nunca rodou</span> : null}
            </div>
          )}

          <div className="flex-1 overflow-y-auto space-y-0.5">
            {lgEntries.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-8">
                Supervisor ainda não rodou<br />
                <span className="text-[10px]">(aguarde até 15 min)</span>
              </p>
            )}
            {lgEntries.map(({ name, status, lastRun }) => (
              <StatusRow
                key={name}
                name={name}
                status={status}
                sub={lastRun ? fmt(lastRun) : undefined}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
