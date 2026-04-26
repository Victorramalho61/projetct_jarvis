import type { SystemCheck } from "../../types/monitoring";

const COLOR: Record<string, string> = {
  up:       "bg-green-400",
  down:     "bg-red-500",
  degraded: "bg-amber-400",
  unknown:  "bg-gray-200",
};

type Props = {
  checks: SystemCheck[];
  maxBars?: number;
  className?: string;
};

export default function Sparkline({ checks, maxBars = 48, className = "" }: Props) {
  const bars = checks.slice(-maxBars);
  const placeholder = maxBars - bars.length;
  const latencies = bars.map((c) => c.latency_ms ?? 0).filter(Boolean);
  const maxLatency = Math.max(...latencies, 1);

  return (
    <div className={`flex items-end gap-px ${className}`} title="Histórico de disponibilidade">
      {Array.from({ length: placeholder }).map((_, i) => (
        <div key={`ph-${i}`} className="flex-1 rounded-sm bg-gray-100" style={{ height: "20%" }} />
      ))}
      {bars.map((check, i) => {
        const pct = check.latency_ms
          ? Math.max(15, (check.latency_ms / maxLatency) * 100)
          : 20;
        return (
          <div
            key={i}
            title={`${new Date(check.checked_at).toLocaleString("pt-BR")} — ${check.latency_ms ?? "—"}ms`}
            style={{ height: `${pct}%` }}
            className={`flex-1 rounded-sm transition-opacity hover:opacity-70 ${COLOR[check.status] ?? COLOR.unknown}`}
          />
        );
      })}
    </div>
  );
}
