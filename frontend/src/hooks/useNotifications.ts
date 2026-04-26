import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types/monitoring";

export type Notification = {
  id: string;
  type: "down" | "degraded" | "pending_user";
  title: string;
  body: string;
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
        if (status === "down") {
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

    setNotifications(next);
  }, [token, user?.role]);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, 60_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  return notifications;
}
