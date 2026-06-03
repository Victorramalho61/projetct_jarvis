export interface Period {
  from: string;
  to: string;
}

export interface TicketFilters {
  from?: string;
  to?: string;
  group_id?: number;
  responder_id?: number;
  company_id?: number;
  priority?: number;
  sla_breached?: boolean;
  csat_rating?: number;
}

interface PriorityBreakdown {
  priority: number | null;
  count: number;
  breach_pct: number | null;
}

export interface FreshserviceSummary {
  total_closed: number;
  csat_avg: number | null;
  sla_breach_pct: number | null;
  avg_resolution_min: number | null;
  avg_fr_min: number | null;
  by_priority: PriorityBreakdown[];
}

export interface GroupSLA {
  group_id: number | null;
  group_name: string;
  count: number;
  avg_resolution_min: number | null;
  breach_pct: number | null;
}

export interface AgentStats {
  agent_id: number | null;
  agent_name: string;
  closed_count: number;
  avg_resolution_min: number | null;
}

export interface CompanyRequester {
  company_id: number | null;
  company_name: string;
  count: number;
}

interface CSATByGroup {
  group_id: number | null;
  group_name: string;
  count: number;
  avg_rating: number | null;
  happy_pct: number | null;
  unhappy_pct: number | null;
}

interface CSATComment {
  id: number;
  subject: string;
  csat_rating: number;
  csat_comment: string;
  resolved_at: string;
}

export interface CSATSummary {
  total_rated: number;
  avg_rating: number | null;
  happy_pct: number | null;
  neutral_pct: number | null;
  unhappy_pct: number | null;
  by_group: CSATByGroup[];
  recent_comments: CSATComment[];
}

interface LiveTicket {
  id: number;
  subject: string;
  created_at: string;
  time_open_hours?: number;
  group_id?: number | null;
  responder_id?: number | null;
  priority?: number | null;
  status?: number;
}

export interface LiveMetrics {
  oldest_open: LiveTicket[];
  waiting_vendor_count: number;
  by_vendor: { group_id: string; count: number }[];
}

export interface FreshserviceTicket {
  id: number;
  subject: string;
  status: number;
  priority: number | null;
  type: string | null;
  group_id: number | null;
  responder_id: number | null;
  requester_id: number | null;
  company_id: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  sla_breached: boolean | null;
  resolution_time_min: number | null;
  fr_time_min: number | null;
  csat_rating: number | null;
  csat_comment: string | null;
  agent_name?: string | null;
  group_name?: string | null;
  company_name?: string | null;
}

export interface TicketsPage {
  data: FreshserviceTicket[];
  total: number;
  page: number;
  page_size: number;
}

export interface DailySummary {
  summary: string;
  anomaly: boolean;
  anomaly_detail: string;
}

export interface SyncStatus {
  id: number;
  sync_type: string;
  started_at: string;
  completed_at: string | null;
  tickets_upserted: number;
  status: string;
  error: string | null;
  summary_json: DailySummary | null;
}

export const PRIORITY_LABELS: Record<number, string> = {
  1: "Baixa",
  2: "Média",
  3: "Alta",
  4: "Urgente",
};

export const PRIORITY_COLORS: Record<number, string> = {
  1: "text-gray-500",
  2: "text-blue-600",
  3: "text-amber-600",
  4: "text-red-600",
};

const CSAT_LABELS: Record<number, string> = {
  1: "Insatisfeito",
  2: "Neutro",
  3: "Satisfeito",
};

export const CSAT_EMOJIS: Record<number, string> = {
  1: "😞",
  2: "😐",
  3: "😊",
};
