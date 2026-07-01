import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import type { FsProject, FsProjectDetail } from "../types/freshservice";
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

function ProjectDetailPanel({ detail }: { detail: FsProjectDetail }) {
  if (!detail.tasks.length) {
    return <p className="text-sm text-gray-400 dark:text-gray-500 py-3">Nenhuma tarefa sincronizada para este projeto.</p>;
  }
  return (
    <div className="space-y-4 pt-3">
      {detail.pending_by_assignee.length === 0 ? (
        <p className="text-sm text-green-600 dark:text-green-400">Todas as tarefas mapeadas como concluídas.</p>
      ) : (
        detail.pending_by_assignee.map((group) => (
          <div key={group.assignee_name}>
            <h4 className="text-[12px] font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
              {group.assignee_name} <span className="font-normal text-gray-400">({group.tasks.length} pendente{group.tasks.length > 1 ? "s" : ""})</span>
            </h4>
            <ul className="space-y-1">
              {group.tasks.map((t) => (
                <li key={t.id} className="flex items-center gap-2 text-[13px] text-gray-700 dark:text-gray-300 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
                  {t.display_key && <span className="font-mono text-[11px] text-gray-400 shrink-0">{t.display_key}</span>}
                  <span className="truncate">{t.title}</span>
                  {t.planned_end_date && (
                    <span className="ml-auto text-[11px] text-gray-400 shrink-0">{fmtDate(t.planned_end_date)}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </div>
  );
}

export default function FreshserviceProjectsPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [projects, setProjects] = useState<FsProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, FsProjectDetail>>({});
  const [detailLoading, setDetailLoading] = useState<number | null>(null);

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

  async function toggleExpand(id: number) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (details[id]) return;
    setDetailLoading(id);
    try {
      const data = await apiFetch<FsProjectDetail>(`/api/freshservice/projects/${id}`, { token });
      setDetails((prev) => ({ ...prev, [id]: data }));
    } catch {
      // painel de detalhe é opcional — não bloqueia a timeline
    } finally {
      setDetailLoading(null);
    }
  }

  async function triggerSync() {
    setSyncing(true);
    try {
      await apiFetch("/api/freshservice/projects/sync", { method: "POST", token });
      await fetchProjects();
      setDetails({});
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

      <div className="relative pl-6">
        {active.length > 0 && (
          <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-700" />
        )}
        {active.map((p) => {
          const isExpanded = expandedId === p.id;
          const isComplete = p.percent_complete === 100;
          return (
            <div key={p.id} className="relative pb-4">
              <span
                className={`absolute -left-6 top-2 w-3 h-3 rounded-full ring-4 ring-gray-50 dark:ring-gray-950 ${
                  isComplete ? "bg-brand-green" : "bg-gray-300 dark:bg-gray-600"
                }`}
              />
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
                <button
                  type="button"
                  onClick={() => toggleExpand(p.id)}
                  className="w-full text-left"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {p.key && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 shrink-0">
                            {p.key}
                          </span>
                        )}
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{p.name}</h3>
                      </div>
                      {p.description && (
                        <p className="text-[12px] text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{p.description}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-gray-400 dark:text-gray-500 shrink-0">
                      {fmtDate(p.start_date)} → {fmtDate(p.end_date)}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-4">
                    <div className="flex-1 min-w-[160px]">
                      <ProgressBar pct={p.percent_complete} />
                    </div>
                    <span className="text-[11px] text-gray-500 dark:text-gray-400">
                      {p.done_tasks}/{p.total_tasks} tarefas
                    </span>
                    {p.manager_name && (
                      <span className="text-[11px] text-gray-500 dark:text-gray-400">Resp.: {p.manager_name}</span>
                    )}
                    <span className="ml-auto text-[10px] font-medium text-brand-green">
                      {isExpanded ? "Fechar ↑" : "O que falta ↓"}
                    </span>
                  </div>
                </button>

                {isExpanded && (
                  detailLoading === p.id ? (
                    <div className="h-16 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse mt-3" />
                  ) : details[p.id] ? (
                    <ProjectDetailPanel detail={details[p.id]} />
                  ) : null
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
