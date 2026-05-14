import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";

export type Notification = {
  id: string;
  type: "down" | "degraded" | "pending_user" | "agent_proposal" | "cto_message" | "critical_event" | "performance_pending";
  title: string;
  body: string;
  link?: string;
};

type NotificationSummary = {
  systems_down: { id: string; name: string; detail: string }[];
  systems_degraded: { id: string; name: string; detail: string }[];
  pending_users: number;
  pending_proposals: number;
  unread_inbox: number;
  critical_findings: number;
};

const PERFORMANCE_ROLES: string[] = ["rh", "gestor", "coordenador", "supervisor", "colaborador"];

export function useNotifications() {
  const { token, user } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    if (!token) return;

    try {
      const summary = await apiFetch<NotificationSummary>("/api/notifications/summary", { token });
      const next: Notification[] = [];

      for (const sys of summary.systems_down) {
        next.push({
          id: `sys-${sys.id}`,
          type: "down",
          title: `${sys.name} — FALHA`,
          body: sys.detail,
          link: `/admin/monitoramento/${sys.id}`,
        });
      }

      for (const sys of summary.systems_degraded) {
        next.push({
          id: `sys-degraded-${sys.id}`,
          type: "degraded",
          title: `${sys.name} — Degradado`,
          body: sys.detail,
          link: `/admin/monitoramento/${sys.id}`,
        });
      }

      if (summary.pending_users > 0) {
        const n = summary.pending_users;
        next.push({
          id: "pending-users",
          type: "pending_user",
          title: `${n} solicitaç${n > 1 ? "ões" : "ão"} pendente${n > 1 ? "s" : ""}`,
          body: "Novos usuários aguardando ativação",
          link: "/admin/acesso",
        });
      }

      if (summary.pending_proposals > 0) {
        const n = summary.pending_proposals;
        next.push({
          id: "agent-proposals",
          type: "agent_proposal",
          title: `${n} proposal${n > 1 ? "s" : ""} aguardando aprovação`,
          body: "Agentes identificaram melhorias que precisam da sua decisão",
          link: "/admin/proposals",
        });
      }

      if (summary.unread_inbox > 0) {
        const n = summary.unread_inbox;
        next.push({
          id: "cto-inbox",
          type: "cto_message",
          title: `${n} mensage${n > 1 ? "ns" : "m"} nova${n > 1 ? "s" : ""} do CTO`,
          body: "Abra o Inbox para ver as sugestões e atualizações",
          link: "/admin/cto-inbox",
        });
      }

      if (summary.critical_findings > 0) {
        const n = summary.critical_findings;
        next.push({
          id: "critical-events",
          type: "critical_event",
          title: `${n} evento${n > 1 ? "s" : ""} crítico${n > 1 ? "s" : ""}`,
          body: "Eventos críticos não processados no orquestrador",
          link: "/admin/orquestrador",
        });
      }

      if (user && PERFORMANCE_ROLES.includes(user.role)) {
        try {
          const perfSummary = await apiFetch<{ total_pending: number }>(
            "/api/performance/notifications/summary", { token }
          );
          if (perfSummary.total_pending > 0) {
            const n = perfSummary.total_pending;
            next.push({
              id: "performance-pending",
              type: "performance_pending",
              title: `${n} pendência${n > 1 ? "s" : ""} em Desempenho`,
              body: "Metas ou avaliações aguardando sua ação",
              link: "/desempenho",
            });
          }
        } catch {
          /* silencioso */
        }
      }

      setNotifications(next);
    } catch {
      /* silencioso — não quebrar UI por falha de notificação */
    }
  }, [token, user?.role]);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, 90_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  const dismiss = useCallback((id: string) => {
    setDismissedIds((prev) => new Set([...prev, id]));
  }, []);

  const clearAll = useCallback(() => {
    setDismissedIds((prev) => new Set([...prev, ...notifications.map((n) => n.id)]));
  }, [notifications]);

  const visible = notifications.filter((n) => !dismissedIds.has(n.id));

  return { notifications: visible, dismiss, clearAll };
}
