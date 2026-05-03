/**
 * AgentFlowView — visualização ao vivo do grafo de agentes.
 *
 * Conecta ao SSE /api/agents/orchestrator/stream para receber:
 *  - snapshot inicial com últimos runs + mensagens
 *  - updates incrementais a cada 2s
 *  - heartbeat a cada ~15s
 *
 * Renderiza:
 *  - CTO Supervisor no topo
 *  - Pipelines como colunas
 *  - Agentes pulsando quando em execução
 *  - Feed de mensagens inter-agentes ao vivo
 */

import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";

declare const __API_URL__: string;
const BASE = typeof __API_URL__ !== "undefined" ? __API_URL__ : "";

// ── Tipos ─────────────────────────────────────────────────────────────────────

interface AgentRun {
  id: string;
  pipeline_name: string | null;
  run_type: string | null;
  status: "running" | "success" | "error" | string;
  started_at: string;
  finished_at: string | null;
  output: string | null;
  error: string | null;
}

interface AgentMessage {
  id: string;
  from_agent: string;
  to_agent: string;
  content: string | Record<string, unknown>;
  status: string;
  created_at: string;
}

interface StreamEvent {
  type: "snapshot" | "update" | "heartbeat" | "error";
  runs?: AgentRun[];
  messages?: AgentMessage[];
  ts?: string;
  message?: string;
}

interface TopoNode {
  id: string;
  type: "supervisor" | "agent";
  label: string;
  pipelines: string[];
}

interface Topology {
  nodes: TopoNode[];
  pipelines: Record<string, string[]>;
}

// ── Paleta ────────────────────────────────────────────────────────────────────

const PIPELINE_COLORS: Record<string, { bg: string; border: string; label: string; text: string }> = {
  monitoring: { bg: "bg-blue-50 dark:bg-blue-950/30",   border: "border-blue-200 dark:border-blue-800",   label: "Monitoramento", text: "text-blue-700 dark:text-blue-300" },
  security:   { bg: "bg-red-50 dark:bg-red-950/30",     border: "border-red-200 dark:border-red-800",     label: "Segurança",     text: "text-red-700 dark:text-red-300" },
  cicd:       { bg: "bg-purple-50 dark:bg-purple-950/30",border: "border-purple-200 dark:border-purple-800",label: "CI/CD",        text: "text-purple-700 dark:text-purple-300" },
  dba:        { bg: "bg-orange-50 dark:bg-orange-950/30",border: "border-orange-200 dark:border-orange-800",label: "DBA",          text: "text-orange-700 dark:text-orange-300" },
  governance: { bg: "bg-teal-50 dark:bg-teal-950/30",   border: "border-teal-200 dark:border-teal-800",   label: "Governança",    text: "text-teal-700 dark:text-teal-300" },
  evolution:  { bg: "bg-pink-50 dark:bg-pink-950/30",   border: "border-pink-200 dark:border-pink-800",   label: "Evolução",      text: "text-pink-700 dark:text-pink-300" },
  manual:     { bg: "bg-gray-50 dark:bg-gray-800/30",   border: "border-gray-200 dark:border-gray-700",   label: "Manual",        text: "text-gray-700 dark:text-gray-300" },
};

function statusDot(status: string) {
  if (status === "running")  return "w-2 h-2 rounded-full bg-blue-500 animate-pulse";
  if (status === "success")  return "w-2 h-2 rounded-full bg-green-500";
  if (status === "error")    return "w-2 h-2 rounded-full bg-red-500";
  return "w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600";
}

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function msgText(content: string | Record<string, unknown>): string {
  if (typeof content === "string") return content.slice(0, 120);
  try { return JSON.stringify(content).slice(0, 120); } catch { return ""; }
}

// ── Hook SSE ──────────────────────────────────────────────────────────────────

function useAgentStream(token: string | null) {
  const [runs, setRuns]         = useState<AgentRun[]>([]);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastTs, setLastTs]     = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!token) return;

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    async function connect() {
      try {
        const res = await fetch(`${BASE}/api/agents/orchestrator/stream`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: ctrl.signal,
        });

        if (!res.ok || !res.body) { setConnected(false); return; }
        setConnected(true);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            try {
              const ev: StreamEvent = JSON.parse(line.slice(5).trim());
              if (ev.type === "snapshot") {
                setRuns(ev.runs ?? []);
                setMessages(ev.messages ?? []);
                setLastTs(ev.ts ?? null);
              } else if (ev.type === "update") {
                if (ev.runs?.length) {
                  setRuns(prev => {
                    const map = new Map(prev.map(r => [r.id, r]));
                    (ev.runs ?? []).forEach(r => map.set(r.id, r));
                    return Array.from(map.values()).slice(-60);
                  });
                }
                if (ev.messages?.length) {
                  setMessages(prev => [...prev, ...(ev.messages ?? [])].slice(-50));
                }
                setLastTs(ev.ts ?? null);
              }
            } catch { /* ignore parse errors */ }
          }
        }
        // Stream fechou normalmente — reconecta automaticamente
        setConnected(false);
        if (!ctrl.signal.aborted) setTimeout(connect, 3000);
      } catch (e: unknown) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setConnected(false);
        if (!ctrl.signal.aborted) setTimeout(connect, 5000);
      }
    }

    connect();
    return () => { ctrl.abort(); setConnected(false); };
  }, [token]);

  return { runs, messages, connected, lastTs };
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function AgentFlowView() {
  const { token } = useAuth();
  const { runs, messages, connected, lastTs } = useAgentStream(token);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [topoError, setTopoError] = useState(false);
  const msgRef = useRef<HTMLDivElement>(null);

  // Carrega topologia uma vez
  useEffect(() => {
    if (!token) return;
    fetch(`${BASE}/api/agents/orchestrator/topology`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(setTopology)
      .catch(() => setTopoError(true));
  }, [token]);

  // Auto-scroll no feed de mensagens
  useEffect(() => {
    if (msgRef.current) {
      msgRef.current.scrollTop = msgRef.current.scrollHeight;
    }
  }, [messages]);

  // Mapa de status atual por agente (do último run)
  const agentStatus = new Map<string, string>();
  const agentLastRun = new Map<string, string>();
  [...runs].reverse().forEach(r => {
    const name = r.pipeline_name;
    if (name && !agentStatus.has(name)) {
      agentStatus.set(name, r.status);
      agentLastRun.set(name, r.started_at);
    }
  });

  const pipelines = topology?.pipelines ?? {};
  const pipelineNames = Object.keys(pipelines).filter(p => p !== "manual");

  const activeCount = runs.filter(r => r.status === "running").length;
  const successCount = runs.filter(r => r.status === "success").length;
  const errorCount = runs.filter(r => r.status === "error").length;

  return (
    <div className="space-y-4">

      {/* ── Barra de status da conexão ── */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${connected ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {connected ? "Conectado ao stream ao vivo" : "Reconectando..."}
          </span>
          {lastTs && (
            <span className="text-[10px] text-gray-400">· atualizado {fmt(lastTs)}</span>
          )}
        </div>
        <div className="flex gap-3 text-xs">
          {activeCount > 0  && <span className="text-blue-600 dark:text-blue-400 font-medium animate-pulse">● {activeCount} rodando</span>}
          {successCount > 0 && <span className="text-green-600 dark:text-green-400">✓ {successCount} ok</span>}
          {errorCount > 0   && <span className="text-red-600 dark:text-red-400">✗ {errorCount} erro</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">

        {/* ── Coluna esquerda + centro: Grafo ── */}
        <div className="xl:col-span-3 space-y-3">

          {/* CTO Supervisor */}
          <div className="flex justify-center">
            <div className={`relative px-6 py-3 rounded-xl border-2 text-center min-w-[180px] shadow-sm
              ${agentStatus.get("cto") === "running"
                ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/40 shadow-indigo-100 dark:shadow-indigo-900"
                : "border-indigo-300 dark:border-indigo-700 bg-white dark:bg-gray-800"}`}>
              <div className="flex items-center justify-center gap-2 mb-0.5">
                <span className={statusDot(agentStatus.get("cto") ?? "idle")} />
                <span className="text-sm font-bold text-indigo-700 dark:text-indigo-300">CTO Agent</span>
              </div>
              <span className="text-[10px] text-gray-400">Supervisor</span>
              {agentStatus.get("cto") === "running" && (
                <span className="absolute -top-1.5 -right-1.5 text-[9px] bg-blue-500 text-white px-1.5 py-0.5 rounded-full animate-pulse">
                  rodando
                </span>
              )}
            </div>
          </div>

          {/* Linha conectora */}
          <div className="flex justify-center">
            <div className="w-px h-4 bg-gray-300 dark:bg-gray-600" />
          </div>

          {/* Pipelines + Agentes */}
          {topoError && (
            <p className="text-xs text-gray-400 text-center py-4">
              Topologia indisponível — execute um pipeline para gerar dados.
            </p>
          )}

          {!topoError && pipelineNames.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4 animate-pulse">
              Carregando topologia...
            </p>
          )}

          {pipelineNames.length > 0 && (
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              {pipelineNames.map(pipeline => {
                const col = PIPELINE_COLORS[pipeline] ?? PIPELINE_COLORS.manual;
                const agents = pipelines[pipeline] ?? [];
                const pipelineRunning = agents.some(a => agentStatus.get(a) === "running");

                return (
                  <div
                    key={pipeline}
                    className={`rounded-xl border p-3 ${col.bg} ${col.border} ${pipelineRunning ? "ring-1 ring-blue-400 dark:ring-blue-600" : ""}`}
                  >
                    {/* Header do pipeline */}
                    <div className="flex items-center gap-1.5 mb-2">
                      {pipelineRunning && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />}
                      <span className={`text-xs font-semibold ${col.text}`}>
                        {col.label}
                      </span>
                    </div>

                    {/* Agentes do pipeline */}
                    <div className="space-y-1">
                      {agents.map(agent => {
                        const st = agentStatus.get(agent) ?? "idle";
                        const isRunning = st === "running";
                        return (
                          <div
                            key={agent}
                            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium transition-all
                              ${isRunning
                                ? "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 ring-1 ring-blue-300"
                                : st === "error"
                                  ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                                  : st === "success"
                                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                                    : "bg-white/60 dark:bg-gray-700/30 text-gray-600 dark:text-gray-400"
                              }`}
                          >
                            <span className={statusDot(st)} />
                            <span className="truncate">{agent}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Log de execuções recentes */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-3">
            <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
              Execuções recentes
            </h3>
            <div className="space-y-1 max-h-36 overflow-y-auto">
              {runs.length === 0 && (
                <p className="text-[10px] text-gray-400 text-center py-2">Sem execuções ainda</p>
              )}
              {[...runs].reverse().slice(0, 20).map(r => (
                <div key={r.id} className="flex items-center gap-2 text-[10px]">
                  <span className={statusDot(r.status)} />
                  <span className="font-medium text-gray-700 dark:text-gray-300 w-28 truncate flex-shrink-0">
                    {r.pipeline_name ?? "—"}
                  </span>
                  <span className={`flex-shrink-0 ${
                    r.status === "running" ? "text-blue-500" :
                    r.status === "success" ? "text-green-500" :
                    r.status === "error"   ? "text-red-500"   : "text-gray-400"
                  }`}>{r.status}</span>
                  <span className="text-gray-400 flex-shrink-0">{fmt(r.started_at)}</span>
                  {r.error && (
                    <span className="text-red-400 truncate" title={r.error}>{r.error.slice(0, 40)}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Coluna direita: Feed de mensagens inter-agentes ── */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-3 flex flex-col">
          <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2 flex-shrink-0">
            Agentes conversando
          </h3>

          <div
            ref={msgRef}
            className="flex-1 overflow-y-auto space-y-2 min-h-0"
            style={{ maxHeight: "calc(100vh - 260px)", minHeight: 200 }}
          >
            {messages.length === 0 && (
              <p className="text-[10px] text-gray-400 text-center py-4">
                Sem mensagens recentes.<br />
                <span className="text-[9px]">As mensagens aparecerão aqui quando os agentes estiverem rodando.</span>
              </p>
            )}
            {messages.map((msg, i) => (
              <div
                key={msg.id ?? i}
                className="border border-gray-100 dark:border-gray-700 rounded-lg p-2 text-[10px] animate-fadeIn"
              >
                {/* De → Para */}
                <div className="flex items-center gap-1 mb-1 flex-wrap">
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1.5 py-0.5 rounded">
                    {msg.from_agent}
                  </span>
                  <span className="text-gray-400">→</span>
                  <span className={`font-semibold px-1.5 py-0.5 rounded ${
                    msg.to_agent === "human"
                      ? "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30"
                      : "text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/30"
                  }`}>
                    {msg.to_agent}
                  </span>
                  <span className="text-gray-300 dark:text-gray-600 ml-auto">{fmt(msg.created_at)}</span>
                </div>
                {/* Conteúdo */}
                <p className="text-gray-600 dark:text-gray-400 leading-relaxed break-words">
                  {msgText(msg.content)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
