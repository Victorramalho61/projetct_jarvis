import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";

type LogEntry = {
  id: number;
  created_at: string;
  level: "info" | "warning" | "error";
  module: string;
  message: string;
  detail: string | null;
  user_id: string | null;
};

const LEVEL_STYLES: Record<string, string> = {
  info: "bg-voetur-50 text-voetur-700 border-voetur-200 dark:bg-voetur-900/20 dark:text-voetur-300 dark:border-voetur-800",
  warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800",
  error: "bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800",
};

const LEVEL_DOT: Record<string, string> = {
  info: "bg-voetur-500",
  warning: "bg-amber-500",
  error: "bg-red-500",
};

export default function LogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "info" | "warning" | "error">("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ data: LogEntry[]; total: number }>("/api/admin/logs?limit=300&offset=0", { token });
      setLogs(res.data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar logs.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLogs, 5000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, fetchLogs]);

  const visible = filter === "all" ? logs : logs.filter((l) => l.level === filter);

  const counts = {
    error: logs.filter((l) => l.level === "error").length,
    warning: logs.filter((l) => l.level === "warning").length,
    info: logs.filter((l) => l.level === "info").length,
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Logs do sistema</h2>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">Últimas 300 entradas</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
              autoRefresh
                ? "border-voetur-500 bg-voetur-50 text-voetur-700 dark:bg-voetur-900/20 dark:text-voetur-300"
                : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            {autoRefresh ? "⏳ Atualizando..." : "Auto-refresh"}
          </button>
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {loading ? "..." : "Atualizar"}
          </button>
        </div>
      </div>

      {/* Counters */}
      <div className="mt-4 flex gap-3">
        {(["all", "error", "warning", "info"] as const).map((lvl) => (
          <button
            key={lvl}
            onClick={() => setFilter(lvl)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
              filter === lvl
                ? "border-gray-900 bg-gray-900 text-white dark:border-gray-100 dark:bg-gray-100 dark:text-gray-900"
                : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            {lvl === "all" ? `Todos (${logs.length})` : lvl === "error" ? `Erros (${counts.error})` : lvl === "warning" ? `Avisos (${counts.warning})` : `Info (${counts.info})`}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>
      )}

      <div className="mt-4 space-y-2">
        {visible.length === 0 && !loading && (
          <p className="py-10 text-center text-sm text-gray-400 dark:text-gray-500">Nenhum log encontrado.</p>
        )}
        {visible.map((log) => (
          <div
            key={log.id}
            className={`rounded-xl border px-4 py-3 ${LEVEL_STYLES[log.level] ?? "bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700"}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 min-w-0">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${LEVEL_DOT[log.level] ?? "bg-gray-400"}`} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold uppercase tracking-wide opacity-70">{log.module}</span>
                    <span className="text-sm font-medium">{log.message}</span>
                  </div>
                  {log.detail && expanded === log.id && (
                    <pre className="mt-2 whitespace-pre-wrap break-all rounded-lg bg-white/60 dark:bg-black/20 px-3 py-2 text-xs opacity-90">
                      {log.detail}
                    </pre>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-xs opacity-60 whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString("pt-BR")}
                </span>
                {log.detail && (
                  <button
                    onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                    className="rounded px-1.5 py-0.5 text-xs font-medium opacity-70 hover:opacity-100 transition-opacity"
                  >
                    {expanded === log.id ? "Fechar" : "Detalhe"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
