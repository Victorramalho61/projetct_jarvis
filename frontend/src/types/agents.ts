export type AgentType = "freshservice_sync" | "script";
export type ScheduleType = "manual" | "interval" | "daily" | "weekly" | "monthly";
export type AgentRunStatus = "running" | "success" | "error";

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
