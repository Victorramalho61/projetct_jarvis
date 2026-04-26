type Summary = { up: number; down: number; degraded: number; unknown: number };

type Props = {
  summary: Summary;
  lastRefresh: Date | null;
  autoRefresh: boolean;
  loading: boolean;
  onToggleAutoRefresh: () => void;
  onRefresh: () => void;
};

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
        <span className="text-sm font-medium text-gray-600">{total} sistema{total !== 1 ? "s" : ""}</span>
        {summary.up > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-700">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            {summary.up} UP
          </span>
        )}
        {summary.down > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
            {summary.down} FALHA
          </span>
        )}
        {summary.degraded > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            {summary.degraded} DEGRADADO
          </span>
        )}
        {lastRefresh && (
          <span className="text-xs text-gray-400">
            {lastRefresh.toLocaleTimeString("pt-BR")}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleAutoRefresh}
          className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
            autoRefresh
              ? "border-blue-500 bg-blue-50 text-blue-700"
              : "border-gray-300 text-gray-600 hover:bg-gray-50"
          }`}
        >
          {autoRefresh ? "⏳ Auto-refresh" : "Auto-refresh"}
        </button>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          {loading ? "..." : "Atualizar"}
        </button>
      </div>
    </div>
  );
}
