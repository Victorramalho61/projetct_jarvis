import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";
import type { ChecksPage, MonitoredSystem, SystemCheck, SystemStatus } from "../../types/monitoring";
import StatusBadge from "../../components/monitoring/StatusBadge";
import Sparkline from "../../components/monitoring/Sparkline";
import SystemFormModal from "../../components/monitoring/SystemFormModal";

const STATUS_LABEL: Record<SystemStatus, string> = {
  up: "UP", down: "FALHA", degraded: "DEGRADADO", unknown: "DESCONHECIDO",
};

export default function SystemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [system, setSystem] = useState<MonitoredSystem | null>(null);
  const [checks, setChecks] = useState<SystemCheck[]>([]);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState<"history" | "logs">("history");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;
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

  if (loading) return <div className="p-8 text-sm text-gray-400">Carregando...</div>;
  if (error || !system) return (
    <div className="p-8">
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error ?? "Sistema não encontrado"}</div>
    </div>
  );

  const status: StatusBadge_Status = (system.last_check?.status ?? "unknown") as any;

  return (
    <div className="p-8">
      <button onClick={() => navigate(-1)} className="mb-4 text-sm text-gray-500 hover:text-gray-800">
        ← Voltar
      </button>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Painel esquerdo */}
        <div className="space-y-4">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between">
              <h2 className="font-bold text-gray-900">{system.name}</h2>
              <StatusBadge status={system.last_check?.status ?? "unknown"} />
            </div>
            {system.description && (
              <p className="mt-1 text-sm text-gray-500">{system.description}</p>
            )}
            {system.url && (
              <p className="mt-1 break-all text-xs text-gray-400">{system.url}</p>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-gray-50 p-3 text-center">
                <p className="text-lg font-bold text-gray-900">
                  {system.uptime_24h != null ? `${system.uptime_24h}%` : "—"}
                </p>
                <p className="text-xs text-gray-500">Uptime 24h</p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 text-center">
                <p className="text-lg font-bold text-gray-900">
                  {system.last_check?.latency_ms != null ? `${system.last_check.latency_ms}ms` : "—"}
                </p>
                <p className="text-xs text-gray-500">Latência</p>
              </div>
            </div>

            {system.last_check?.metrics && (
              <div className="mt-3 space-y-1 text-xs text-gray-600">
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
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {manualChecking ? "Checando..." : "Check manual"}
              </button>
              <button
                onClick={() => setShowEdit(true)}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Editar
              </button>
            </div>
          </div>
        </div>

        {/* Painel direito */}
        <div className="lg:col-span-2">
          <div className="flex border-b">
            {(["history", "logs"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  tab === t
                    ? "border-b-2 border-blue-600 text-blue-600"
                    : "text-gray-500 hover:text-gray-800"
                }`}
              >
                {t === "history" ? "Histórico de checks" : "Logs"}
              </button>
            ))}
          </div>

          {tab === "history" && (
            <div className="mt-4">
              <div className="mb-3 flex gap-2">
                {["", "up", "down", "degraded"].map((s) => (
                  <button
                    key={s}
                    onClick={() => applyFilter(s)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                      statusFilter === s
                        ? "border-gray-900 bg-gray-900 text-white"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {s === "" ? "Todos" : STATUS_LABEL[s as SystemStatus]}
                  </button>
                ))}
              </div>

              {checksLoading && <p className="text-sm text-gray-400">Carregando...</p>}

              {!checksLoading && checks.length === 0 && (
                <p className="py-8 text-center text-sm text-gray-400">Nenhum check encontrado.</p>
              )}

              {!checksLoading && checks.length > 0 && (
                <div className="overflow-hidden rounded-xl border bg-white">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Horário</th>
                        <th className="px-4 py-3 text-left">Status</th>
                        <th className="px-4 py-3 text-left">Latência</th>
                        <th className="px-4 py-3 text-left">Detalhe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {checks.map((chk) => (
                        <tr key={chk.id} className="hover:bg-gray-50">
                          <td className="whitespace-nowrap px-4 py-2.5 text-gray-600">
                            {new Date(chk.checked_at).toLocaleString("pt-BR")}
                          </td>
                          <td className="px-4 py-2.5">
                            <StatusBadge status={chk.status} size="sm" />
                          </td>
                          <td className="px-4 py-2.5 text-gray-600">
                            {chk.latency_ms != null ? `${chk.latency_ms}ms` : "—"}
                          </td>
                          <td className="max-w-xs truncate px-4 py-2.5 text-xs text-gray-400">
                            {chk.detail ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {total > LIMIT && (
                <div className="mt-3 flex justify-between text-sm text-gray-500">
                  <button
                    disabled={offset === 0}
                    onClick={() => changePage(Math.max(0, offset - LIMIT))}
                    className="rounded border border-gray-300 px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40"
                  >
                    ← Anterior
                  </button>
                  <span>{offset + 1}–{Math.min(offset + LIMIT, total)} de {total}</span>
                  <button
                    disabled={offset + LIMIT >= total}
                    onClick={() => changePage(offset + LIMIT)}
                    className="rounded border border-gray-300 px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40"
                  >
                    Próxima →
                  </button>
                </div>
              )}
            </div>
          )}

          {tab === "logs" && (
            <div className="mt-4 text-sm text-gray-500">
              <p>Veja os logs relacionados a este sistema na página de{" "}
                <button onClick={() => navigate("/admin/logs")} className="text-blue-600 hover:underline">
                  Logs
                </button>{" "}
                filtrando por módulo <code className="rounded bg-gray-100 px-1">monitoring</code>.
              </p>
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

// alias para evitar conflito de nome
type StatusBadge_Status = Parameters<typeof StatusBadge>[0]["status"];
