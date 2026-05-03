import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { AgentMessage } from "../../types/agents";

const AGENT_COLORS: Record<string, string> = {
  evolution_agent:      "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
  cto:                  "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  log_strategic_advisor:"bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  security:             "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  cicd_monitor:         "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  db_dba_agent:         "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
};

const AGENT_ICON: Record<string, string> = {
  evolution_agent:      "🚀",
  cto:                  "🧠",
  log_strategic_advisor:"📊",
  security:             "🔒",
  cicd_monitor:         "⚙️",
  db_dba_agent:         "🗄️",
};

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "medium", timeStyle: "short" });
}

function AgentBadge({ agent }: { agent: string }) {
  const style = AGENT_COLORS[agent] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
  const icon = AGENT_ICON[agent] ?? "🤖";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${style}`}>
      {icon} {agent.replace(/_/g, " ")}
    </span>
  );
}

function MessageCard({ msg, onRead }: { msg: AgentMessage; onRead: (id: string) => void }) {
  const [expanded, setExpanded] = useState(msg.status === "pending");
  const isUnread = msg.status === "pending";

  const innovations = (msg.context?.innovations as any[]) ?? [];
  const innovCount = msg.context?.innovations_count as number | undefined;
  const oppCount = msg.context?.opportunities_count as number | undefined;

  return (
    <div
      className={`border rounded-xl p-4 transition-all ${
        isUnread
          ? "border-indigo-300 dark:border-indigo-600 bg-indigo-50/50 dark:bg-indigo-900/10"
          : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <AgentBadge agent={msg.from_agent} />
          {isUnread && (
            <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 animate-pulse">NOVO</span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-gray-400">{fmt(msg.created_at)}</span>
          {isUnread && (
            <button
              onClick={() => onRead(msg.id)}
              className="text-xs px-2 py-0.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
            >
              Marcar lido
            </button>
          )}
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            {expanded ? "▲ Recolher" : "▼ Expandir"}
          </button>
        </div>
      </div>

      {/* Stats rápidos do evolution_agent */}
      {(innovCount !== undefined || oppCount !== undefined) && (
        <div className="flex items-center gap-4 mb-3">
          {innovCount !== undefined && (
            <div className="text-center">
              <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400">{innovCount}</p>
              <p className="text-xs text-gray-500">Inovações</p>
            </div>
          )}
          {oppCount !== undefined && (
            <div className="text-center">
              <p className="text-lg font-bold text-purple-600 dark:text-purple-400">{oppCount}</p>
              <p className="text-xs text-gray-500">Oportunidades</p>
            </div>
          )}
        </div>
      )}

      {/* Mensagem principal */}
      {expanded && (
        <div className="space-y-3">
          <div className="bg-white dark:bg-gray-900 rounded-lg p-3 border border-gray-100 dark:border-gray-700">
            <pre className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
              {msg.message}
            </pre>
          </div>

          {/* Inovações destacadas */}
          {innovations.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Inovações destacadas:</p>
              <div className="space-y-1.5">
                {innovations.map((inn: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${
                      inn.priority === "critical" ? "bg-red-100 text-red-700" :
                      inn.priority === "high" ? "bg-orange-100 text-orange-700" :
                      "bg-yellow-100 text-yellow-700"
                    }`}>
                      {inn.priority}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-800 dark:text-gray-200">{inn.title}</p>
                      {inn.business_value && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{inn.business_value}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!expanded && (
        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mt-1">
          {msg.message?.split("\n").find(l => l.trim() && !l.startsWith("#") && !l.startsWith("🚀") && !l.startsWith("📊")) ?? msg.message?.slice(0, 120)}
        </p>
      )}
    </div>
  );
}

export default function CTOInboxPage() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (filter === "unread") params.set("unread_only", "true");
      const data = await apiFetch<{ messages: AgentMessage[]; unread_count: number }>(
        `/api/agents/inbox?${params}`, { token }
      );
      setMessages(data.messages || []);
      setUnreadCount(data.unread_count ?? 0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, filter]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const markRead = async (id: string) => {
    if (!token) return;
    try {
      await apiFetch(`/api/agents/inbox/${id}/read`, { token, method: "PATCH", json: {} });
      setMessages(prev => prev.map(m => m.id === id ? { ...m, status: "read" } : m));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (e: any) { setError(e.message); }
  };

  const markAllRead = async () => {
    if (!token) return;
    try {
      await apiFetch("/api/agents/inbox/read-all", { token, method: "POST", json: {} });
      setMessages(prev => prev.map(m => ({ ...m, status: "read" as const })));
      setUnreadCount(0);
    } catch (e: any) { setError(e.message); }
  };

  const filteredMessages = filter === "unread"
    ? messages.filter(m => m.status === "pending")
    : messages;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Inbox do CTO</h1>
            {unreadCount > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-sm font-bold bg-indigo-600 text-white animate-pulse">
                {unreadCount} novo{unreadCount > 1 ? "s" : ""}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Sugestões, briefings e notificações dos agentes de IA para sua aprovação
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden text-sm">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1.5 transition-colors ${filter === "all" ? "bg-indigo-600 text-white" : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"}`}
            >
              Todas
            </button>
            <button
              onClick={() => setFilter("unread")}
              className={`px-3 py-1.5 transition-colors ${filter === "unread" ? "bg-indigo-600 text-white" : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"}`}
            >
              Não lidas {unreadCount > 0 ? `(${unreadCount})` : ""}
            </button>
          </div>
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Marcar todas lidas
            </button>
          )}
          <button
            onClick={load}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Atualizar
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Dica quando vazio */}
      {!loading && filteredMessages.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
          <p className="text-4xl mb-3">🤖</p>
          <p className="text-gray-600 dark:text-gray-400 font-medium">
            {filter === "unread" ? "Nenhuma mensagem não lida" : "Nenhuma mensagem ainda"}
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            O Evolution Agent envia o briefing diário às 07:00 BRT com sugestões e inovações
          </p>
        </div>
      )}

      <div className="space-y-3">
        {filteredMessages.map(msg => (
          <MessageCard key={msg.id} msg={msg} onRead={markRead} />
        ))}
      </div>
    </div>
  );
}
