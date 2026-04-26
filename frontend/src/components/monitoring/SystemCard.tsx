import type { MonitoredSystem, SystemStatus } from "../../types/monitoring";
import StatusBadge from "./StatusBadge";
import Sparkline from "./Sparkline";

const TYPE_LABEL: Record<string, string> = {
  http:      "HTTP",
  evolution: "WhatsApp",
  metrics:   "Servidor",
  custom:    "Custom",
};

const BORDER_DOWN: Record<SystemStatus, string> = {
  up:       "",
  down:     "border-red-300",
  degraded: "border-amber-300",
  unknown:  "",
};

type Props = { system: MonitoredSystem; onClick: () => void };

export default function SystemCard({ system, onClick }: Props) {
  const lc = system.last_check;
  const status: SystemStatus = lc ? lc.status : "unknown";
  const borderClass = BORDER_DOWN[status];

  const checksForSparkline = lc ? [lc] : [];

  return (
    <div
      onClick={onClick}
      className={`cursor-pointer rounded-xl border bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-gray-300 ${borderClass} ${!system.enabled ? "opacity-60" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-gray-900">{system.name}</h3>
          {system.url && (
            <p className="mt-0.5 truncate text-xs text-gray-400">{system.url}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <StatusBadge status={status} />
          {!system.enabled && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">Desativado</span>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
        <span>
          <span className="font-medium text-gray-700">
            {system.uptime_24h != null ? `${system.uptime_24h}%` : "—"}
          </span>{" "}
          uptime 24h
        </span>
        <span>
          <span className="font-medium text-gray-700">
            {lc?.latency_ms != null ? `${lc.latency_ms}ms` : "—"}
          </span>{" "}
          latência
        </span>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 font-medium">
          {TYPE_LABEL[system.system_type] ?? system.system_type}
        </span>
      </div>

      {lc?.detail && status !== "up" && (
        <p className={`mt-2 truncate text-xs ${status === "down" ? "text-red-600" : "text-amber-600"}`}>
          {lc.detail}
        </p>
      )}

      {lc?.metrics && (
        <div className="mt-2 flex gap-3 text-xs text-gray-500">
          {lc.metrics.cpu_pct != null && <span>CPU {lc.metrics.cpu_pct}%</span>}
          {lc.metrics.ram_pct != null && <span>RAM {lc.metrics.ram_pct}%</span>}
          {lc.metrics.disk_pct != null && <span>Disco {lc.metrics.disk_pct}%</span>}
        </div>
      )}

      <Sparkline checks={checksForSparkline} maxBars={48} className="mt-3 h-8 w-full" />

      {lc && (
        <p className="mt-1 text-right text-xs text-gray-400">
          {new Date(lc.checked_at).toLocaleString("pt-BR")}
        </p>
      )}
    </div>
  );
}
