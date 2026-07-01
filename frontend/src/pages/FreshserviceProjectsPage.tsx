import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import type { FsProject } from "../types/freshservice";
import KPICard from "../components/freshservice/KPICard";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function ProgressBar({ pct }: { pct: number | null }) {
  if (pct == null) {
    return <span className="text-[11px] text-gray-400 dark:text-gray-500">Sem tarefas sincronizadas</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div className="h-full rounded-full bg-brand-green/70" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 w-9 text-right">{pct}%</span>
    </div>
  );
}

function ProjectCard({ p, onOpen }: { p: FsProject; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full text-left rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 hover:border-brand-green/60 hover:shadow-sm transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {p.key && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 shrink-0">
              {p.key}
            </span>
          )}
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{p.name}</h3>
        </div>
        <span className="text-[10px] font-medium text-brand-green shrink-0">Ver timeline →</span>
      </div>

      <div className="mt-3">
        <ProgressBar pct={p.percent_complete} />
      </div>

      <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-2 text-[12px]">
        <div>
          <div className="text-gray-400 dark:text-gray-500">Prazo estimado</div>
          <div className="font-medium text-gray-800 dark:text-gray-200 truncate">{fmtDate(p.end_date)}</div>
        </div>
        <div>
          <div className="text-gray-400 dark:text-gray-500">Sponsor</div>
          <div className="font-medium text-gray-800 dark:text-gray-200 truncate">{p.manager_name ?? "—"}</div>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <div className="text-gray-400 dark:text-gray-500">Atividade atual</div>
          <div className="font-medium text-gray-800 dark:text-gray-200 truncate">
            {p.current_task_title ?? (p.total_tasks ? "Todas concluídas" : "—")}
          </div>
        </div>
        <div>
          <div className="text-gray-400 dark:text-gray-500">Com quem</div>
          <div className="font-medium text-gray-800 dark:text-gray-200 truncate">
            {p.current_task_title ? p.current_task_assignee ?? "Sem responsável" : "—"}
          </div>
        </div>
      </div>
    </button>
  );
}

export default function FreshserviceProjectsPage() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [projects, setProjects] = useState<FsProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<FsProject[]>(`/api/freshservice/projects`, { token });
      setProjects(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar projetos.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  async function triggerSync() {
    setSyncing(true);
    try {
      await apiFetch("/api/freshservice/projects/sync", { method: "POST", token });
      await fetchProjects();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erro ao sincronizar projetos.");
    } finally {
      setSyncing(false);
    }
  }

  const active = projects.filter((p) => !p.archived);
  const withTasks = active.filter((p) => p.percent_complete != null);
  const avgComplete = withTasks.length
    ? Math.round(withTasks.reduce((sum, p) => sum + (p.percent_complete ?? 0), 0) / withTasks.length)
    : null;

  return (
    <div className="p-4 sm:p-8 space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Projetos</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Andamento dos projetos cadastrados no Freshservice
          </p>
        </div>
        {isAdmin && (
          <button
            type="button"
            onClick={triggerSync}
            disabled={syncing}
            className="px-3 py-1.5 rounded-lg text-[13px] bg-brand-deep text-white hover:bg-brand-green transition-colors disabled:opacity-50"
          >
            {syncing ? "Sincronizando..." : "Sincronizar agora"}
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-3 gap-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <KPICard label="Projetos ativos" value={active.length} colorClass="text-brand-deep dark:text-brand-mid" />
          <KPICard
            label="% conclusão média"
            value={avgComplete != null ? `${avgComplete}%` : "—"}
            colorClass="text-brand-deep dark:text-brand-mid"
          />
          <KPICard
            label="Tarefas pendentes"
            value={active.reduce((sum, p) => sum + p.pending_tasks, 0).toLocaleString("pt-BR")}
            colorClass="text-amber-600 dark:text-amber-400"
          />
        </div>
      )}

      {!loading && active.length === 0 && !error && (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">
          Nenhum projeto sincronizado ainda.{isAdmin ? ' Clique em "Sincronizar agora".' : ""}
        </p>
      )}

      <div className="space-y-3">
        {active.map((p) => (
          <ProjectCard key={p.id} p={p} onOpen={() => navigate(`/freshservice/projetos/${p.id}`)} />
        ))}
      </div>
    </div>
  );
}
