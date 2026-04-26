import type { SystemStatus } from "../../types/monitoring";
import { STATUS_DOT, STATUS_STYLES, STATUS_LABEL } from "./StatusBadge";

type Summary = { up: number; down: number; degraded: number; unknown: number };

type Props = {
  summary: Summary;
  lastRefresh: Date | null;
  autoRefresh: boolean;
  loading: boolean;
  onToggleAutoRefresh: () => void;
  onRefresh: () => void;
};

const PILL_ORDER: SystemStatus[] = ["down", "degraded", "up"];

export default function SummaryBar({
  summary,
  lastRefresh,
  autoRefresh,
  loading,
  onToggleAutoRefresh,
  onRefresh,
}: Props) {
  const total = summary.up + summary.down + summary.degraded + summary.unknown;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{total} sistema{total !== 1 ? "s" : ""}</span>

        {PILL_ORDER.filter((s) => summary[s] > 0).map((s) => (
          <span
            key={s}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold border ${STATUS_STYLES[s]}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[s]} ${s === "down" ? "animate-pulse" : ""}`} />
            {summary[s]} {STATUS_LABEL[s]}
          </span>
        ))}

        {lastRefresh && (
          <span className="text-xs text-gray-400 dark:text-gray-500">{lastRefresh.toLocaleTimeString("pt-BR")}</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleAutoRefresh}
          className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
            autoRefresh ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300" : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          {autoRefresh ? "⏳ Auto-refresh" : "Auto-refresh"}
        </button>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          {loading ? "..." : "Atualizar"}
        </button>
      </div>
    </div>
  );
}
