import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";

export type Notification = {
  id: string;
  type: "down" | "degraded" | "pending_user" | "performance_pending";
  title: string;
  body: string;
  link?: string;
};

type NotificationSummary = {
  systems_down: { id: string; name: string; detail: string }[];
  systems_degraded: { id: string; name: string; detail: string }[];
  pending_users: number;
};

const PERFORMANCE_ROLES: string[] = ["rh", "gestor", "coordenador", "supervisor", "colaborador", "gestor_ciclo"];

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
