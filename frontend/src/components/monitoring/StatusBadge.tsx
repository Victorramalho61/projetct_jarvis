import type { SystemStatus } from "../../types/monitoring";

export const STATUS_STYLES: Record<SystemStatus, string> = {
  up:       "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800",
  down:     "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800",
  degraded: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  unknown:  "bg-gray-100 text-gray-500 border-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600",
};

export const STATUS_DOT: Record<SystemStatus, string> = {
  up:       "bg-green-500",
  down:     "bg-red-500",
  degraded: "bg-amber-500",
  unknown:  "bg-gray-400",
};

export const STATUS_LABEL: Record<SystemStatus, string> = {
  up:       "UP",
  down:     "FALHA",
  degraded: "DEGRADADO",
  unknown:  "DESCONHECIDO",
};

type Props = { status: SystemStatus; size?: "sm" | "md" };

export default function StatusBadge({ status, size = "md" }: Props) {
  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${padding} ${STATUS_STYLES[status]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]} ${status === "down" ? "animate-pulse" : ""}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}
