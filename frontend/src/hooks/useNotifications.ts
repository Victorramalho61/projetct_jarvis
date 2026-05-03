import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types/monitoring";

export type Notification = {
  id: string;
  type: "down" | "degraded" | "pending_user" | "agent_proposal" | "cto_message" | "critical_event";
  title: string;
  body: string;
  link?: string;
};

export function useNotifications() {
  const { token, user } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    if (!token) return;
    const next: Notification[] = [];

    try {
      const dash = await apiFetch<DashboardData>("/api/monitoring/dashboard", { token });
      for (const sys of dash.systems) {
        const status = sys.last_check?.status;
        if (status === "down" && (sys.consecutive_down_count ?? 0) >= 2) {
          next.push({
            id: `sys-${sys.id}`,
            type: "down",
            title: `${sys.name} — FALHA`,
            body: sys.last_check?.detail ?? "Sistema inacessível",
          });
        } else if (status === "degraded") {
          next.push({
            id: `sys-${sys.id}`,
            type: "degraded",
            title: `${sys.name} — Degradado`,
            body: sys.last_check?.detail ?? "Resposta lenta ou parcial",
          });
        }
      }
    } catch {
      /* silencioso */
    }

    if (user?.role === "admin") {
      try {
        const users = await apiFetch<{ active: boolean; display_name: string; email: string }[]>("/api/users", { token });
        const pending = users.filter((u) => !u.active);
        if (pending.length > 0) {
          next.push({
            id: "pending-users",
            type: "pending_user",
            title: `${pending.length} solicitaç${pending.length > 1 ? "ões" : "ão"} pendente${pending.length > 1 ? "s" : ""}`,
            body: pending.map((u) => u.display_name || u.email).join(", "),
          });
        }
      } catch {
        /* silencioso */
      }
    }

    if (user?.role === "admin") {
      // Proposals pendentes dos agentes
      try {
        const p = await apiFetch<{ proposals: { id: string }[] }>("/api/agents/proposals?status=pending&limit=100", { token });
        const count = p.proposals?.length ?? 0;
        if (count > 0) {
          next.push({
            id: "agent-proposals",
            type: "agent_proposal",
            title: `${count} proposal${count > 1 ? "s" : ""} aguardando aprovação`,
            body: "Agentes identificaram melhorias que precisam da sua decisão",
            link: "/admin/proposals",
          });
        }
      } catch { /* silencioso */ }

      // Mensagens não lidas do inbox (evolution_agent, cto, etc.)
      try {
        const inbox = await apiFetch<{ messages: { id: string; from_agent: string; message: string }[]; unread_count: number }>("/api/agents/inbox?unread_only=true&limit=5", { token });
        const unread = inbox.unread_count ?? 0;
        if (unread > 0) {
          const preview = inbox.messages?.[0]?.message?.slice(0, 80) ?? "";
          next.push({
            id: "cto-inbox",
            type: "cto_message",
            title: `${unread} mensage${unread > 1 ? "ns" : "m"} nova${unread > 1 ? "s" : ""} do CTO`,
            body: preview || "Abra o Inbox para ver as sugestões e atualizações",
            link: "/admin/cto-inbox",
          });
        }
      } catch { /* silencioso */ }

      // Eventos críticos não processados
      try {
        const evts = await apiFetch<{ findings: { id: string; event_type: string; source: string }[] }>("/api/agents/orchestrator/findings?limit=5", { token });
        const critical = (evts.findings ?? []).filter((e: any) => e.priority === "critical" && !e.processed);
        if (critical.length > 0) {
          next.push({
            id: "critical-events",
            type: "critical_event",
            title: `${critical.length} evento${critical.length > 1 ? "s" : ""} crítico${critical.length > 1 ? "s" : ""}`,
            body: `Fonte: ${critical[0].source} — ${critical[0].event_type}`,
            link: "/admin/orquestrador",
          });
        }
      } catch { /* silencioso */ }
    }

    setNotifications(next);
  }, [token, user?.role]);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, 60_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  return notifications;
}
