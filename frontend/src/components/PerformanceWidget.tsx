import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";

type PerfSummary = {
  pending_goal_acks: number;
  pending_self_review: number;
  pending_manager_review: number;
  pending_ack_result: number;
  total_pending: number;
};

type Dashboard = {
  completude_pct: number;
};

const RH_ADMIN = ["admin", "rh"];

export default function PerformanceWidget() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<PerfSummary | null>(null);
  const [completude, setCompletude] = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<PerfSummary>("/api/performance/notifications/summary", { token })
      .then(setSummary)
      .catch(() => {});
    if (user && RH_ADMIN.includes(user.role)) {
      apiFetch<Dashboard>("/api/performance/admin/dashboard", { token })
        .then((d) => setCompletude(d.completude_pct))
        .catch(() => {});
    }
  }, [token, user]);

  if (!summary) return null;
  if (summary.total_pending === 0 && completude === null) return null;

  const pendingItems = [
    { label: "Metas pendentes de aceite", count: summary.pending_goal_acks },
    { label: "Autoavaliações pendentes", count: summary.pending_self_review },
    { label: "Avaliações de gestor pendentes", count: summary.pending_manager_review },
    { label: "Resultados aguardando reconhecimento", count: summary.pending_ack_result },
  ].filter((i) => i.count > 0);

  return (
    <div className="rounded-xl border border-violet-100 dark:border-violet-900/40 bg-white dark:bg-gray-900 p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
            Gestão de Desempenho
          </p>
          {summary.total_pending > 0 && (
            <p className="mt-1 text-2xl font-bold text-violet-600 dark:text-violet-400">
              {summary.total_pending}
              <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">
                pendência{summary.total_pending > 1 ? "s" : ""}
              </span>
            </p>
          )}
        </div>
        {completude !== null && (
          <div className="text-right">
            <p className="text-xs text-gray-400 dark:text-gray-500">Completude do ciclo</p>
            <p className="text-lg font-bold text-gray-900 dark:text-gray-100">{completude}%</p>
          </div>
        )}
      </div>

      {completude !== null && (
        <div className="mt-3">
          <div className="h-1.5 w-full rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-violet-500 transition-all duration-500"
              style={{ width: `${completude}%` }}
            />
          </div>
        </div>
      )}

      {pendingItems.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {pendingItems.map((item) => (
            <li key={item.label} className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">{item.label}</span>
              <span className="rounded-full bg-violet-100 dark:bg-violet-900/30 px-2 py-0.5 text-xs font-semibold text-violet-700 dark:text-violet-300">
                {item.count}
              </span>
            </li>
          ))}
        </ul>
      )}

      <button
        onClick={() => navigate("/desempenho")}
        className="mt-4 w-full rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 transition-colors"
      >
        Ir para Desempenho
      </button>
    </div>
  );
}
