import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import type { FsOverdueSummary, FsOverdueProject, FsProjectStatus } from "../types/freshservice";
import KPICard from "../components/freshservice/KPICard";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function StatusCurationRow({ status, onSaved }: { status: FsProjectStatus; onSaved: (s: FsProjectStatus) => void }) {
  const { token } = useAuth();
  const [label, setLabel] = useState(status.label ?? "");
  const [isDone, setIsDone] = useState(status.is_done);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiFetch<FsProjectStatus>(`/api/freshservice/projects/statuses/${status.status_id}`, {
        method: "PATCH",
        token,
        json: { label: label.trim() || null, is_done: isDone },
      });
      onSaved({ ...status, ...updated });
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erro ao salvar status.");
    } finally {
      setSaving(false);
    }
  }

  const dirty = label !== (status.label ?? "") || isDone !== status.is_done;

  return (
    <tr className="border-t border-gray-100 dark:border-gray-800">
      <td className="py-2 pr-3 align-top">
        <div className="font-mono text-[11px] text-gray-400">{status.status_id}</div>
        <div className="text-[11px] text-gray-400 mt-0.5">{status.task_count ?? 0} tasks</div>
      </td>
      <td className="py-2 pr-3 align-top max-w-xs">
        {status.sample_titles?.map((t, i) => (
          <div key={i} className="text-[12px] text-gray-500 dark:text-gray-400 truncate">{t}</div>
        ))}
      </td>
      <td className="py-2 pr-3 align-top">
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Nome do status (ex: Concluído)"
          className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-[13px]"
        />
      </td>
      <td className="py-2 pr-3 align-top text-center">
        <input type="checkbox" checked={isDone} onChange={(e) => setIsDone(e.target.checked)} className="w-4 h-4" />
      </td>
      <td className="py-2 align-top">
        <button
          type="button"
          disabled={!dirty || saving}
          onClick={save}
          className="px-2.5 py-1 rounded-lg text-[12px] bg-brand-deep text-white hover:bg-brand-green transition-colors disabled:opacity-40"
        >
          {saving ? "Salvando..." : "Salvar"}
        </button>
      </td>
    </tr>
  );
}

function ProjectOverdueRow({ project, onOpenProject }: { project: FsOverdueProject; onOpenProject: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          {project.project_key && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 shrink-0">
              {project.project_key}
            </span>
          )}
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{project.project_name}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm font-bold text-red-600 dark:text-red-400">{project.overdue_count}</span>
          <span className="text-[11px] text-gray-400">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-gray-100 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
          {project.tasks.map((t) => (
            <div key={t.id} className="px-4 py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[13px] text-gray-800 dark:text-gray-200 truncate">{t.title}</div>
                <div className="text-[11px] text-gray-400 mt-0.5">
                  {t.assignee_name ?? "Sem responsável"} · prazo {fmtDate(t.planned_end_date)}
                  {t.status_label ? ` · ${t.status_label}` : ""}
                </div>
              </div>
              <span className="shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                {t.days_overdue}d atraso
              </span>
            </div>
          ))}
          <button
            type="button"
            onClick={onOpenProject}
            className="w-full px-4 py-2 text-[12px] font-medium text-brand-green hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors text-left"
          >
            Ver projeto completo →
          </button>
        </div>
      )}
    </div>
  );
}

export default function FreshserviceOverdueTasksPage() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<FsOverdueSummary | null>(null);
  const [statuses, setStatuses] = useState<FsProjectStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCuration, setShowCuration] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, statusData] = await Promise.all([
        apiFetch<FsOverdueSummary>("/api/freshservice/projects/overdue-summary", { token }),
        apiFetch<FsProjectStatus[]>("/api/freshservice/projects/statuses", { token }),
      ]);
      setSummary(summaryData);
      setStatuses(statusData.filter((s) => s.kind === "task"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar tasks estouradas.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const uncuratedCount = statuses.filter((s) => !s.label).length;
  const topProject = summary?.projects[0];

  return (
    <div className="p-4 sm:p-8 space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Tasks Estouradas</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Tasks com prazo vencido e não concluídas, por projeto
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/freshservice/projetos")}
          className="px-3 py-1.5 rounded-lg text-[13px] border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          ← Voltar para Projetos
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {!loading && uncuratedCount > 0 && (
        <div className="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
          <div className="flex items-center justify-between gap-3">
            <span>
              <strong>{uncuratedCount} de {statuses.length}</strong> status de task ainda não foram classificados como "concluído" ou não —
              os números abaixo podem estar contando tasks já concluídas como estouradas.
            </span>
            <button
              type="button"
              onClick={() => setShowCuration((v) => !v)}
              className="shrink-0 px-2.5 py-1 rounded-lg text-[12px] bg-amber-600 text-white hover:bg-amber-700 transition-colors"
            >
              {showCuration ? "Fechar" : "Classificar agora"}
            </button>
          </div>

          {showCuration && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-amber-700/70 dark:text-amber-400/70">
                    <th className="pb-1.5 pr-3 font-medium">Status ID</th>
                    <th className="pb-1.5 pr-3 font-medium">Exemplos de task</th>
                    <th className="pb-1.5 pr-3 font-medium">Nome</th>
                    <th className="pb-1.5 pr-3 font-medium">Concluído?</th>
                    <th className="pb-1.5 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {statuses.map((s) => (
                    <StatusCurationRow
                      key={s.status_id}
                      status={s}
                      onSaved={(updated) => {
                        setStatuses((prev) => prev.map((row) => (row.status_id === updated.status_id ? updated : row)));
                        fetchAll();
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
          <KPICard
            label="Tasks estouradas"
            value={summary?.total_overdue_tasks.toLocaleString("pt-BR") ?? "—"}
            colorClass="text-red-600 dark:text-red-400"
          />
          <KPICard
            label="Projetos afetados"
            value={summary?.projects.length ?? "—"}
            colorClass="text-red-600 dark:text-red-400"
          />
          <KPICard
            label="Projeto mais crítico"
            value={topProject ? topProject.overdue_count : "—"}
            sub={topProject?.project_name}
            colorClass="text-red-600 dark:text-red-400"
          />
        </div>
      )}

      {!loading && summary && summary.projects.length === 0 && !error && (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">
          Nenhuma task estourada encontrada. 🎉
        </p>
      )}

      <div className="space-y-3">
        {summary?.projects.map((p) => (
          <ProjectOverdueRow
            key={p.project_id}
            project={p}
            onOpenProject={() => navigate(`/freshservice/projetos/${p.project_id}`)}
          />
        ))}
      </div>
    </div>
  );
}
