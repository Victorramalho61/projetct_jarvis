import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import type { FsProjectDetail, FsProjectTask } from "../types/freshservice";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function stripHtml(html: string | null | undefined): string {
  if (!html) return "";
  return html
    .replace(/<\/(p|div|li|h[1-6])>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function ProgressBar({ pct }: { pct: number | null }) {
  if (pct == null) {
    return <span className="text-[12px] text-gray-400 dark:text-gray-500">Sem tarefas sincronizadas</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div className="h-full rounded-full bg-brand-green/70" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[12px] font-semibold text-gray-600 dark:text-gray-300 w-10 text-right">{pct}%</span>
    </div>
  );
}

function TaskTimelineItem({ task, isLast }: { task: FsProjectTask; isLast: boolean }) {
  const [open, setOpen] = useState(false);
  const description = stripHtml(task.raw?.description);

  return (
    <div className="relative pb-5 pl-6">
      {!isLast && <span className="absolute left-[5px] top-4 bottom-0 w-px bg-gray-200 dark:bg-gray-700" />}
      <span
        className={`absolute left-0 top-1.5 w-[11px] h-[11px] rounded-full ring-4 ring-white dark:ring-gray-950 ${
          task.is_done ? "bg-brand-green" : "bg-gray-300 dark:bg-gray-600"
        }`}
      />
      <button type="button" onClick={() => setOpen((o) => !o)} className="w-full text-left group">
        <div className="flex flex-wrap items-center gap-2">
          {task.display_key && <span className="font-mono text-[11px] text-gray-400 shrink-0">{task.display_key}</span>}
          <span
            className={`text-[13px] font-medium ${
              task.is_done ? "text-gray-400 dark:text-gray-500 line-through" : "text-gray-900 dark:text-gray-100"
            }`}
          >
            {task.title}
          </span>
          {task.is_done && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 shrink-0">
              Concluída
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-1 text-[11px] text-gray-500 dark:text-gray-400">
          <span>{task.assignee_name ?? "Sem responsável"}</span>
          {task.planned_start_date && <span>Início: {fmtDate(task.planned_start_date)}</span>}
          {task.planned_end_date && <span>Prazo: {fmtDate(task.planned_end_date)}</span>}
          {description && (
            <span className="ml-auto text-brand-green group-hover:underline shrink-0">
              {open ? "Ocultar descrição ↑" : "Ver descrição ↓"}
            </span>
          )}
        </div>
      </button>
      {open && description && (
        <p className="mt-2 text-[12px] text-gray-600 dark:text-gray-400 whitespace-pre-line bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
          {description}
        </p>
      )}
    </div>
  );
}

export default function FreshserviceProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<FsProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDescription, setShowDescription] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<FsProjectDetail>(`/api/freshservice/projects/${id}`, { token });
      setDetail(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar projeto.");
    } finally {
      setLoading(false);
    }
  }, [id, token]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  const sortedTasks = detail
    ? [...detail.tasks].sort((a, b) => {
        const da = a.planned_start_date ?? "";
        const db_ = b.planned_start_date ?? "";
        if (!da && !db_) return a.id - b.id;
        if (!da) return 1;
        if (!db_) return -1;
        return da.localeCompare(db_) || a.id - b.id;
      })
    : [];

  return (
    <div className="p-4 sm:p-8 space-y-6 max-w-4xl mx-auto">
      <button
        type="button"
        onClick={() => navigate("/freshservice/projetos")}
        className="text-[13px] text-gray-500 hover:text-brand-deep dark:hover:text-brand-mid transition-colors"
      >
        ← Voltar para Projetos
      </button>

      {loading ? (
        <div className="h-40 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
      ) : error ? (
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      ) : detail ? (
        <>
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                {detail.project.key && (
                  <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 shrink-0">
                    {detail.project.key}
                  </span>
                )}
                <h1 className="text-xl font-bold text-gray-900 dark:text-white truncate">{detail.project.name}</h1>
              </div>
              {detail.project.status_label && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 shrink-0">
                  {detail.project.status_label}
                </span>
              )}
            </div>

            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-3 text-[13px]">
              <div>
                <div className="text-gray-400 dark:text-gray-500 text-[11px]">Sponsor</div>
                <div className="font-medium text-gray-800 dark:text-gray-200">{detail.project.manager_name ?? "—"}</div>
              </div>
              <div>
                <div className="text-gray-400 dark:text-gray-500 text-[11px]">Início</div>
                <div className="font-medium text-gray-800 dark:text-gray-200">{fmtDate(detail.project.start_date)}</div>
              </div>
              <div>
                <div className="text-gray-400 dark:text-gray-500 text-[11px]">Prazo estimado</div>
                <div className="font-medium text-gray-800 dark:text-gray-200">{fmtDate(detail.project.end_date)}</div>
              </div>
              <div>
                <div className="text-gray-400 dark:text-gray-500 text-[11px]">Tarefas</div>
                <div className="font-medium text-gray-800 dark:text-gray-200">
                  {detail.project.done_tasks}/{detail.project.total_tasks}
                </div>
              </div>
            </div>

            <div className="mt-4">
              <ProgressBar pct={detail.project.percent_complete} />
            </div>

            {detail.project.description && (
              <div className="mt-4 border-t border-gray-100 dark:border-gray-800 pt-3">
                <button
                  type="button"
                  onClick={() => setShowDescription((o) => !o)}
                  className="text-[12px] font-medium text-brand-green hover:underline"
                >
                  {showDescription ? "Ocultar descrição ↑" : "Ver descrição do projeto ↓"}
                </button>
                {showDescription && (
                  <p className="mt-2 text-[13px] text-gray-600 dark:text-gray-400 whitespace-pre-line">
                    {stripHtml(detail.project.description)}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Timeline de tarefas</h2>
            {sortedTasks.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 py-4">Nenhuma tarefa sincronizada para este projeto.</p>
            ) : (
              <div>
                {sortedTasks.map((t, i) => (
                  <TaskTimelineItem key={t.id} task={t} isLast={i === sortedTasks.length - 1} />
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
