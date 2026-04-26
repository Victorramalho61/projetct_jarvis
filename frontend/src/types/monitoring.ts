export type SystemStatus = "up" | "down" | "degraded" | "unknown";
export type SystemType = "http" | "evolution" | "metrics" | "tcp" | "custom";

export interface SystemCheck {
  id: string;
  checked_at: string;
  system_id: string;
  status: SystemStatus;
  latency_ms?: number;
  http_status?: number;
  detail?: string;
  metrics?: Record<string, number>;
  checked_by: string;
}

export interface MonitoredSystem {
  id: string;
  name: string;
  description: string;
  url: string;
  system_type: SystemType;
  config: Record<string, unknown>;
  check_interval_minutes: number;
  enabled: boolean;
  created_at: string;
  last_check?: SystemCheck;
  uptime_24h?: number;
}

export interface DashboardData {
  systems: MonitoredSystem[];
  summary: { up: number; down: number; degraded: number; unknown: number };
}

export interface ChecksPage {
  data: SystemCheck[];
  total: number;
  limit: number;
  offset: number;
}
