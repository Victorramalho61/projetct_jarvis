export type AgentType = "freshservice_sync" | "script" | "langgraph";
export type ScheduleType = "manual" | "interval" | "daily" | "weekly" | "monthly";
export type AgentRunStatus = "running" | "success" | "error";
export type ProposalStatus = "pending" | "approved" | "rejected" | "applied" | "implementation_failed";
export type ChangeStatus = "pending" | "approved" | "rejected" | "implemented" | "cancelled";
export type Priority = "critical" | "high" | "medium" | "low";

export interface Agent {
  id: string;
  name: string;
  description: string;
  agent_type: AgentType;
  config: Record<string, unknown>;
  schedule_type: ScheduleType;
  schedule_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}

export interface AgentRun {
  id: number;
  agent_id: string;
  status: AgentRunStatus;
  started_at: string;
  finished_at?: string;
  output?: string;
  error?: string;
}

export interface Proposal {
  id: string;
  source_agent: string;
  proposal_type: string;
  title: string;
  description?: string;
  evidence?: string;
  proposed_fix?: string;
  proposed_action?: string;
  sql_proposal?: string;
  expected_gain?: string;
  business_value?: string;
  motivational_note?: string;
  priority: Priority;
  risk: "low" | "medium" | "high";
  estimated_effort?: string;
  auto_implementable: boolean;
  validation_status: ProposalStatus;
  applied: boolean;
  applied_at?: string;
  approved_at?: string;
  rejection_reason?: string;
  implementation_error?: string;
  assessor_status?: "pending_review" | "approved" | "rejected" | "needs_revision" | "validated";
  assessor_score?: number;
  assessor_feedback?: string;
  assessor_tags?: string[];
  revision_count?: number;
  reviewed_at?: string;
  created_at: string;
}

export interface ChangeRequest {
  id: string;
  title: string;
  description?: string;
  change_type: "emergency" | "normal" | "standard";
  priority: Priority;
  requested_by: string;
  status: ChangeStatus;
  sla_deadline?: string;
  approved_by?: string;
  rejection_reason?: string;
  context?: Record<string, unknown> | null;
  rollback_plan?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeploymentWindow {
  id: string;
  active: boolean;
  reason?: string;
  started_by?: string;
  started_at: string;
  expected_end?: string;
  ended_at?: string;
}

export interface GovernanceReport {
  id: string;
  period: "daily" | "weekly";
  report_date: string;
  metrics: Record<string, unknown>;
  findings_summary?: string;
  recommendations?: string;
  agents_health: Record<string, unknown>;
  generated_by: string;
  created_at: string;
}

export interface AgentEvent {
  id: string;
  event_type: string;
  source: string;
  payload: Record<string, unknown>;
  priority: Priority;
  processed: boolean;
  created_at: string;
}

export interface AgentMessage {
  id: string;
  from_agent: string;
  to_agent: string;
  message: string;
  context: Record<string, unknown>;
  thread_id?: string;
  status: "pending" | "read" | "processed";
  read_at?: string;
  created_at: string;
}
