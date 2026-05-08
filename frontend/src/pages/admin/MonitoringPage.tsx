import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";
import type { DashboardData, MonitoredSystem } from "../../types/monitoring";
import SummaryBar from "../../components/monitoring/SummaryBar";
import SystemCard from "../../components/monitoring/SystemCard";
import SystemFormModal from "../../components/monitoring/SystemFormModal";

export default function MonitoringPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingSystem, setEditingSystem] = useState<MonitoredSystem | undefined>();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDashboard = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    setError(null);
    try {
      const d = await apiFetch<DashboardData>("/api/monitoring/dashboard", { token });
      setData(d);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar dashboard.");
    } finally {
      if (initial) setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchDashboard(true); }, [fetchDashboard]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => fetchDashboard(), 60_000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, fetchDashboard]);

  function openEdit(system: MonitoredSystem) {
    setEditingSystem(system);
    setShowForm(true);
  }

  function openCreate() {
    setEditingSystem(undefined);
    setShowForm(true);
  }

  const summary = data?.summary ?? { up: 0, down: 0, degraded: 0, unknown: 0 };

  return (
    <div className="p-4 sm:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Monitoramento</h2>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">Status dos sistemas em tempo real</p>
        </div>
        <button
          onClick={openCreate}
          className="rounded-lg bg-voetur-600 px-4 py-2 text-sm font-medium text-white hover:bg-voetur-700 transition-colors"
        >
          + Adicionar sistema
        </button>
      </div>

      <SummaryBar
        summary={summary}
        lastRefresh={lastRefresh}
        autoRefresh={autoRefresh}
        loading={loading}
        onToggleAutoRefresh={() => setAutoRefresh((v) => !v)}
        onRefresh={() => fetchDashboard()}
      />

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="mt-10 text-center text-sm text-gray-400 dark:text-gray-500">Carregando...</div>
      )}

      {data && data.systems.length === 0 && (
        <div className="mt-10 text-center text-sm text-gray-400 dark:text-gray-500">
          Nenhum sistema cadastrado.{" "}
          <button onClick={openCreate} className="text-voetur-600 hover:underline">
            Adicionar o primeiro
          </button>
        </div>
      )}

      {data && data.systems.length > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.systems.map((system) => (
            <div key={system.id} className="relative">
              <SystemCard
                system={system}
                onClick={() => navigate(`/admin/monitoramento/${system.id}`)}
              />
              <button
                onClick={(e) => { e.stopPropagation(); openEdit(system); }}
                className="absolute right-3 top-3 rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300"
                title="Editar"
              >
                ✎
              </button>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <SystemFormModal
          system={editingSystem}
          token={token}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); fetchDashboard(); }}
        />
      )}
    </div>
  );
}
