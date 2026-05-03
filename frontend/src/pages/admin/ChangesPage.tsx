import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { ChangeRequest } from "../../types/agents";

const TYPE_STYLE: Record<string, string> = {
  emergency: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-l-4 border-red-500",
  normal:    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-l-4 border-blue-500",
  standard:  "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 border-l-4 border-green-500",
};

const STATUS_STYLE: Record<string, string> = {
  pending:     "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  approved:    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  rejected:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  implemented: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  cancelled:   "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function slaStatus(deadline?: string): { label: string; style: string } {
  if (!deadline) return { label: "Sem SLA", style: "text-gray-400" };
  const diff = new Date(deadline).getTime() - Date.now();
  const hours = diff / 3_600_000;
  if (hours < 0) return { label: "SLA VIOLADO", style: "text-red-600 font-bold" };
  if (hours < 2) return { label: `${Math.floor(hours * 60)}min restantes`, style: "text-orange-500 font-medium" };
  if (hours < 24) return { label: `${Math.floor(hours)}h restantes`, style: "text-yellow-500" };
  return { label: fmt(deadline), style: "text-gray-400" };
}

export default function ChangesPage() {
  const { token } = useAuth();
  const [changes, setChanges] = useState<ChangeRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [rejectModal, setRejectModal] = useState<{ id: string } | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
      const data = await apiFetch<{ changes: ChangeRequest[] }>(`/api/agents/changes?${params}`, { token });
      setChanges(data.changes || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const approve = async (id: string) => {
    if (!token) return;
    try {
      await apiFetch(`/api/agents/changes/${id}/approve`, { token, method: "PATCH", json: {} });
      await load();
    } catch (e: any) { setError(e.message); }
  };

  const reject = async () => {
    if (!token || !rejectModal) return;
    try {
      await apiFetch(`/api/agents/changes/${rejectModal.id}/reject`, {
        token, method: "PATCH", json: { reason: rejectReason },
      });
      setRejectModal(null);
      setRejectReason("");
      await load();
    } catch (e: any) { setError(e.message); }
  };

  const typeLabel: Record<string, string> = { emergency: "Emergência", normal: "Normal", standard: "Padrão" };
  const priorityLabel: Record<string, string> = { critical: "Crítica", high: "Alta", medium: "Média", low: "Baixa" };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Gestão de Mudanças</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Change Requests ITIL — aprovação e acompanhamento de SLA
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="px-2 py-0.5 rounded border-l-4 border-red-500 bg-red-50 dark:bg-red-900/20">Emergência</span>
            <span className="px-2 py-0.5 rounded border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-900/20">Normal</span>
            <span className="px-2 py-0.5 rounded border-l-4 border-green-500 bg-green-50 dark:bg-green-900/20">Padrão</span>
          </div>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          >
            <option value="pending">Pendentes</option>
            <option value="approved">Aprovadas</option>
            <option value="rejected">Rejeitadas</option>
            <option value="implemented">Implementadas</option>
            <option value="all">Todas</option>
          </select>
          <button onClick={load} className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
            Atualizar
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Carregando...</div>
        ) : changes.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">Nenhuma mudança encontrada</div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {changes.map(c => {
              const sla = slaStatus(c.sla_deadline);
              return (
                <div key={c.id} className={`p-4 ${TYPE_STYLE[c.change_type] ?? ""}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                          {typeLabel[c.change_type] ?? c.change_type}
                        </span>
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_STYLE[c.status]}`}>
                          {c.status}
                        </span>
                        <span className="text-xs text-gray-400">
                          prioridade: {priorityLabel[c.priority] ?? c.priority}
                        </span>
                        <span className={`text-xs ${sla.style}`}>{sla.label}</span>
                      </div>
                      <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{c.title}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        Solicitado por: {c.requested_by} — {fmt(c.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                        className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                      >
                        {expanded === c.id ? "Fechar" : "Detalhes"}
                      </button>
                      {c.status === "pending" && (
                        <>
                          <button
                            onClick={() => approve(c.id)}
                            className="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
                          >
                            Aprovar
                          </button>
                          <button
                            onClick={() => setRejectModal({ id: c.id })}
                            className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                          >
                            Rejeitar
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {expanded === c.id && (
                    <div className="mt-3 space-y-2 border-t border-gray-100 dark:border-gray-700 pt-3">
                      {c.description && (
                        <div>
                          <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Descrição:</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded p-2">{c.description}</p>
                        </div>
                      )}
                      {c.approved_by && (
                        <p className="text-xs text-green-600 dark:text-green-400">Aprovado por: {c.approved_by}</p>
                      )}
                      {c.rejection_reason && (
                        <p className="text-xs text-red-600 dark:text-red-400">Motivo de rejeição: {c.rejection_reason}</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Rejeitar Mudança</h2>
            <textarea
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              placeholder="Motivo da rejeição..."
              rows={3}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white mb-4"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setRejectModal(null)} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                Cancelar
              </button>
              <button onClick={reject} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">
                Rejeitar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
