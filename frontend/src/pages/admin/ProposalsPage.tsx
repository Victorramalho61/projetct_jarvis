import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { Proposal, Priority } from "../../types/agents";

interface ProposalMetrics {
  pending: number;
  approved_waiting: number;
  applied_success: number;
  rejected: number;
  implementation_failed: number;
  total_decided: number;
  execution_rate_pct: number;
  failure_rate_pct: number;
}

const PRIORITY_STYLE: Record<Priority, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  high:     "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  medium:   "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  low:      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
};

const STATUS_STYLE: Record<string, string> = {
  pending:                "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  approved:               "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  rejected:               "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  applied:                "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  implementation_failed:  "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
};

const STATUS_LABEL: Record<string, string> = {
  pending:               "Pendente",
  approved:              "Aprovada",
  rejected:              "Rejeitada",
  applied:               "Aplicada",
  implementation_failed: "Falhou",
};

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export default function ProposalsPage() {
  const { token } = useAuth();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [metrics, setMetrics] = useState<ProposalMetrics | null>(null);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rejectModal, setRejectModal] = useState<{ id: string } | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [failModal, setFailModal] = useState<{ id: string } | null>(null);
  const [failReason, setFailReason] = useState("");

  const loadMetrics = useCallback(async () => {
    if (!token) return;
    try {
      const data = await apiFetch<ProposalMetrics>("/api/agents/proposals/metrics", { token });
      setMetrics(data);
    } catch { /* silencioso */ }
  }, [token]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
      const data = await apiFetch<{ proposals: Proposal[] }>(`/api/agents/proposals?${params}`, { token });
      setProposals(data.proposals || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { loadMetrics(); }, [loadMetrics]);

  useEffect(() => { load(); }, [load]);

  const approve = async (id: string) => {
    if (!token) return;
    try {
      await apiFetch(`/api/agents/proposals/${id}/approve`, { token, method: "PATCH", json: {} });
      await load();
    } catch (e: any) { setError(e.message); }
  };

  const reject = async () => {
    if (!token || !rejectModal) return;
    try {
      await apiFetch(`/api/agents/proposals/${rejectModal.id}/reject`, {
        token, method: "PATCH", json: { reason: rejectReason },
      });
      setRejectModal(null);
      setRejectReason("");
      await load();
    } catch (e: any) { setError(e.message); }
  };

  const markApplied = async (id: string) => {
    if (!token) return;
    try {
      await apiFetch(`/api/agents/proposals/${id}/mark-applied`, { token, method: "PATCH", json: {} });
      await load();
    } catch (e: any) { setError(e.message); }
  };

  const markFailed = async () => {
    if (!token || !failModal) return;
    try {
      await apiFetch(`/api/agents/proposals/${failModal.id}/mark-failed`, {
        token, method: "PATCH", json: { error: failReason },
      });
      setFailModal(null);
      setFailReason("");
      await load();
    } catch (e: any) { setError(e.message); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Proposals de Melhoria</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Propostas geradas pelos agentes para aprovação do CTO
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          >
            <option value="pending">Pendentes</option>
            <option value="approved">Aprovadas</option>
            <option value="rejected">Rejeitadas</option>
            <option value="applied">Aplicadas</option>
            <option value="implementation_failed">Falhou</option>
            <option value="all">Todas</option>
          </select>
          <button onClick={load} className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
            Atualizar
          </button>
        </div>
      </div>

      {/* Painel de métricas */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">{metrics.execution_rate_pct}%</p>
            <p className="text-xs text-gray-500 mt-1">Taxa de execução</p>
            <p className="text-xs text-gray-400">{metrics.applied_success} aplicadas</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{metrics.approved_waiting}</p>
            <p className="text-xs text-gray-500 mt-1">Aprovadas aguardando</p>
            <p className="text-xs text-gray-400">execução pendente</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{metrics.failure_rate_pct}%</p>
            <p className="text-xs text-gray-500 mt-1">Taxa de falha</p>
            <p className="text-xs text-gray-400">{metrics.implementation_failed} com erro</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{metrics.pending}</p>
            <p className="text-xs text-gray-500 mt-1">Aguardando aprovação</p>
            <p className="text-xs text-gray-400">propostas pendentes</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Carregando...</div>
        ) : proposals.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">Nenhuma proposal encontrada</div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {proposals.map(p => (
              <div key={p.id} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${PRIORITY_STYLE[p.priority]}`}>
                        {p.priority}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_STYLE[p.validation_status] ?? ""}`}>
                        {STATUS_LABEL[p.validation_status] ?? p.validation_status}
                      </span>
                      <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                        {p.proposal_type}
                      </span>
                      <span className="text-xs text-gray-400">de: {p.source_agent}</span>
                    </div>
                    <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{p.title}</p>
                    {p.description && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{p.description}</p>
                    )}
                    {/* Implementation error summary */}
                    {p.validation_status === "implementation_failed" && p.implementation_error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1 line-clamp-2">
                        Erro: {p.implementation_error}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-1 flex-wrap">
                      {p.risk && <span className="text-xs text-gray-400">risco: {p.risk}</span>}
                      {p.estimated_effort && <span className="text-xs text-gray-400">esforço: {p.estimated_effort}</span>}
                      <span className="text-xs text-gray-400">criada: {fmt(p.created_at)}</span>
                      {p.approved_at && <span className="text-xs text-blue-500">aprovada: {fmt(p.approved_at)}</span>}
                      {p.applied_at && <span className="text-xs text-green-600">aplicada: {fmt(p.applied_at)}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
                    <button
                      onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                      {expanded === p.id ? "Fechar" : "Detalhes"}
                    </button>
                    {p.validation_status === "pending" && (
                      <>
                        <button
                          onClick={() => approve(p.id)}
                          className="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
                        >
                          Aprovar
                        </button>
                        <button
                          onClick={() => setRejectModal({ id: p.id })}
                          className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                        >
                          Rejeitar
                        </button>
                      </>
                    )}
                    {p.validation_status === "approved" && (
                      <>
                        <button
                          onClick={() => markApplied(p.id)}
                          className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                        >
                          Marcar aplicada
                        </button>
                        <button
                          onClick={() => setFailModal({ id: p.id })}
                          className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                        >
                          Marcar falhou
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {expanded === p.id && (
                  <div className="mt-3 space-y-2 border-t border-gray-100 dark:border-gray-700 pt-3">
                    {p.evidence && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Evidência:</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded p-2">{p.evidence}</p>
                      </div>
                    )}
                    {p.proposed_action && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Ação proposta:</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded p-2">{p.proposed_action}</p>
                      </div>
                    )}
                    {p.proposed_fix && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Código/SQL proposto:</p>
                        <pre className="text-xs text-green-400 bg-gray-900 rounded p-2 overflow-x-auto max-h-48">{p.proposed_fix}</pre>
                      </div>
                    )}
                    {p.expected_gain && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Ganho esperado:</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{p.expected_gain}</p>
                      </div>
                    )}
                    {p.business_value && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Valor de negócio:</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{p.business_value}</p>
                      </div>
                    )}
                    {p.motivational_note && (
                      <div className="bg-indigo-50 dark:bg-indigo-900/20 rounded p-2">
                        <p className="text-xs text-indigo-700 dark:text-indigo-300 italic">{p.motivational_note}</p>
                      </div>
                    )}
                    {p.rejection_reason && (
                      <div>
                        <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">Motivo de rejeição:</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{p.rejection_reason}</p>
                      </div>
                    )}
                    {p.implementation_error && (
                      <div>
                        <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">Erro de implementação:</p>
                        <p className="text-xs text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded p-2 font-mono">{p.implementation_error}</p>
                      </div>
                    )}
                    <div className="flex gap-4 text-xs text-gray-400 pt-1">
                      <span>ID: {p.id.slice(0, 8)}…</span>
                      {p.approved_at && <span>Aprovada em: {fmt(p.approved_at)}</span>}
                      {p.applied_at && <span>Aplicada em: {fmt(p.applied_at)}</span>}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal rejeição */}
      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Rejeitar Proposal</h2>
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

      {/* Modal falhou */}
      {failModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Marcar como Falhou</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Descreva o problema encontrado durante a implementação:</p>
            <textarea
              value={failReason}
              onChange={e => setFailReason(e.target.value)}
              placeholder="Ex: Erro ao aplicar migration — coluna já existe..."
              rows={4}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white mb-4"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setFailModal(null)} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                Cancelar
              </button>
              <button onClick={markFailed} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
