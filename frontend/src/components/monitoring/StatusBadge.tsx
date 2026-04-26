import type { SystemStatus } from "../../types/monitoring";

const STYLES: Record<SystemStatus, string> = {
  up:       "bg-green-100 text-green-700 border-green-200",
  down:     "bg-red-100 text-red-700 border-red-200",
  degraded: "bg-amber-100 text-amber-700 border-amber-200",
  unknown:  "bg-gray-100 text-gray-500 border-gray-200",
};

const DOT: Record<SystemStatus, string> = {
  up:       "bg-green-500",
  down:     "bg-red-500",
  degraded: "bg-amber-500",
  unknown:  "bg-gray-400",
};

const LABEL: Record<SystemStatus, string> = {
  up:       "UP",
  down:     "FALHA",
  degraded: "DEGRADADO",
  unknown:  "DESCONHECIDO",
};

type Props = { status: SystemStatus; size?: "sm" | "md" };

export default function StatusBadge({ status, size = "md" }: Props) {
  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${padding} ${STYLES[status]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[status]} ${status === "down" ? "animate-pulse" : ""}`} />
      {LABEL[status]}
    </span>
  );
}
