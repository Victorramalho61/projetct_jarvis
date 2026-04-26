import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";
import type { ChecksPage, MonitoredSystem, SystemCheck } from "../../types/monitoring";
import StatusBadge, { STATUS_LABEL } from "../../components/monitoring/StatusBadge";
import Sparkline from "../../components/monitoring/Sparkline";
import SystemFormModal from "../../components/monitoring/SystemFormModal";

const LIMIT = 50;

export default function SystemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [system, setSystem] = useState<MonitoredSystem | null>(null);
  const [checks, setChecks] = useState<SystemCheck[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [checksLoading, setChecksLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manualChecking, setManualChecking] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const fetchSystem = useCallback(async () => {
    if (!id) return;
    try {
      const s = await apiFetch<MonitoredSystem>(`/api/monitoring/systems/${id}`, { token });
      setSystem(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar sistema.");
    }
  }, [id, token]);

  const fetchChecks = useCallback(async (off = 0, sf = "") => {
    if (!id) return;
    setChecksLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(LIMIT), offset: String(off) });
      if (sf) params.set("status", sf);
      const data = await apiFetch<ChecksPage>(`/api/monitoring/systems/${id}/checks?${params}`, { token });
      setChecks(data.data);
      setTotal(data.total ?? 0);
    } catch {
      /* silencioso */
    } finally {
      setChecksLoading(false);
    }
  }, [id, token]);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchSystem(), fetchChecks(0, "")]).finally(() => setLoading(false));
  }, [fetchSystem, fetchChecks]);

  async function runManualCheck() {
    if (!id) return;
    setManualChecking(true);
    try {
      await apiFetch(`/api/monitoring/systems/${id}/check`, { method: "POST", token });
      await Promise.all([fetchSystem(), fetchChecks(offset, statusFilter)]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro no check manual.");
    } finally {
      setManualChecking(false);
    }
  }

  function applyFilter(sf: string) {
    setStatusFilter(sf);
    setOffset(0);
    fetchChecks(0, sf);
  }

  function changePage(newOffset: number) {
    setOffset(newOffset);
    fetchChecks(newOffset, statusFilter);
  }

  if (loading) return <div className="p-4 sm:p-8 text-sm text-gray-400 dark:text-gray-500">Carregando...</div>;
  if (error || !system) return (
    <div className="p-4 sm:p-8">
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error ?? "Sistema não encontrado"}</div>
    </div>
  );

  return (
    <div className="p-4 sm:p-8">
      <button onClick={() => navigate(-1)} className="mb-4 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
        ← Voltar
      </button>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Painel esquerdo */}
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <div className="flex items-start justify-between">
              <h2 className="font-bold text-gray-900 dark:text-gray-100">{system.name}</h2>
              <StatusBadge status={system.last_check?.status ?? "unknown"} />
            </div>
            {system.description && (
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{system.description}</p>
            )}
            {system.url && (
              <p className="mt-1 break-all text-xs text-gray-400 dark:text-gray-500">{system.url}</p>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3 text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {system.uptime_24h != null ? `${system.uptime_24h}%` : "—"}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Uptime 24h</p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3 text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {system.last_check?.latency_ms != null ? `${system.last_check.latency_ms}ms` : "—"}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Latência</p>
              </div>
            </div>

            {system.last_check?.metrics && (
              <div className="mt-3 space-y-1 text-xs text-gray-600 dark:text-gray-400">
                {system.last_check.metrics.cpu_pct != null && (
                  <div className="flex justify-between"><span>CPU</span><span className="font-medium">{system.last_check.metrics.cpu_pct}%</span></div>
                )}
                {system.last_check.metrics.ram_pct != null && (
                  <div className="flex justify-between"><span>RAM</span><span className="font-medium">{system.last_check.metrics.ram_pct}% ({system.last_check.metrics.ram_used_gb}GB / {system.last_check.metrics.ram_total_gb}GB)</span></div>
                )}
                {system.last_check.metrics.disk_pct != null && (
                  <div className="flex justify-between"><span>Disco</span><span className="font-medium">{system.last_check.metrics.disk_pct}%</span></div>
                )}
              </div>
            )}

            <Sparkline checks={checks.slice(0, 48).reverse()} maxBars={48} className="mt-4 h-10 w-full" />

            <div className="mt-4 flex gap-2">
              <button
                onClick={runManualCheck}
                disabled={manualChecking}
                className="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
              >
                {manualChecking ? "Checando..." : "Check manual"}
              </button>
              <button
                onClick={() => setShowEdit(true)}
                className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Editar
              </button>
            </div>
          </div>
        </div>

        {/* Painel direito — Histórico */}
        <div className="lg:col-span-2">
          <h3 className="mb-3 font-medium text-gray-900 dark:text-gray-100">Histórico de checks</h3>

          <div className="mb-3 flex flex-wrap gap-2">
            {(["", "up", "down", "degraded"] as const).map((s) => (
              <button
                key={s}
                onClick={() => applyFilter(s)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? "border-gray-900 bg-gray-900 text-white dark:border-gray-100 dark:bg-gray-100 dark:text-gray-900"
                    : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
              >
                {s === "" ? "Todos" : STATUS_LABEL[s]}
              </button>
            ))}
          </div>

          {checksLoading && <p className="text-sm text-gray-400 dark:text-gray-500">Carregando...</p>}

          {!checksLoading && checks.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">Nenhum check encontrado.</p>
          )}

          {!checksLoading && checks.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800/50 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3 text-left">Horário</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Latência</th>
                    <th className="px-4 py-3 text-left">Detalhe</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {checks.map((chk) => (
                    <tr key={chk.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="whitespace-nowrap px-4 py-2.5 text-gray-600 dark:text-gray-400">
                        {new Date(chk.checked_at).toLocaleString("pt-BR")}
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={chk.status} size="sm" />
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">
                        {chk.latency_ms != null ? `${chk.latency_ms}ms` : "—"}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2.5 text-xs text-gray-400 dark:text-gray-500">
                        {chk.detail ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > LIMIT && (
            <div className="mt-3 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
              <button
                disabled={offset === 0}
                onClick={() => changePage(Math.max(0, offset - LIMIT))}
                className="rounded border border-gray-300 dark:border-gray-700 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
              >
                ← Anterior
              </button>
              <span>{offset + 1}–{Math.min(offset + LIMIT, total)} de {total}</span>
              <button
                disabled={offset + LIMIT >= total}
                onClick={() => changePage(offset + LIMIT)}
                className="rounded border border-gray-300 dark:border-gray-700 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
              >
                Próxima →
              </button>
            </div>
          )}
        </div>
      </div>

      {showEdit && (
        <SystemFormModal
          system={system}
          token={token}
          onClose={() => setShowEdit(false)}
          onSaved={() => { setShowEdit(false); fetchSystem(); }}
        />
      )}
    </div>
  );
}
