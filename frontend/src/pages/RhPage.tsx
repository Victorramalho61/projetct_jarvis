import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import { useRhLookups } from "../hooks/useRhLookups";
import { filtrosToQueryString } from "../lib/rhFilters";
import type { AlertaSla, DashboardData, VagasFiltros } from "../types/rh";
import KPICard from "../components/expenses/KPICard";
import FiltrosBar from "../components/rh/FiltrosBar";
import EtapaFunnelChart from "../components/rh/EtapaFunnelChart";
import AlertaSlaTile from "../components/rh/AlertaSlaTile";
import ClickableTileWrapper from "../components/rh/ClickableTileWrapper";
import DrillDownVagasModal from "../components/rh/DrillDownVagasModal";
import VagaFormModal from "../components/rh/VagaFormModal";

type DrillDown = { titulo: string; itens: AlertaSla[] };

const STATUS_CORES: Record<string, string> = {
  "EM ANDAMENTO": "#3b82f6",
  "REABERTO": "#f59e0b",
  "CONCLUÍDO": "#22c55e",
  "CANCELADO": "#ef4444",
  "CONGELADO": "#94a3b8",
};

export default function RhPage() {
  const { token } = useAuth();
  const { lookups } = useRhLookups(token);
  const [filtros, setFiltros] = useState<VagasFiltros>({});
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [drillDown, setDrillDown] = useState<DrillDown | null>(null);
  const [vagaAberta, setVagaAberta] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const qs = filtrosToQueryString(filtros);
    apiFetch<DashboardData>(`/api/rh/dashboard${qs ? `?${qs}` : ""}`, { token })
      .then(setData)
      .finally(() => setLoading(false));
  }, [filtros, token]);

  const kpis = data?.kpis;

  const cargosData = useMemo(() => data?.top_cargos.slice(0, 8) ?? [], [data]);

  function handleImprimir() {
    const qs = filtrosToQueryString(filtros);
    window.open(`/rh/relatorio${qs ? `?${qs}` : ""}`, "_blank");
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Recursos Humanos — Vagas</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Acompanhamento de todos os processos de admissão do Grupo Voetur.</p>
        </div>
        <button
          onClick={handleImprimir}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Imprimir Relatório
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <AlertaSlaTile
          titulo="SLA Estourado"
          quantidade={data?.sla_estourado.length ?? 0}
          variante="estourado"
          onClick={() => setDrillDown({ titulo: "SLA Estourado", itens: data?.sla_estourado ?? [] })}
        />
        <AlertaSlaTile
          titulo="SLA Estourando em até 3 dias"
          quantidade={data?.sla_estourando.length ?? 0}
          variante="estourando"
          onClick={() => setDrillDown({ titulo: "SLA Estourando em até 3 dias", itens: data?.sla_estourando ?? [] })}
        />
      </div>

      <FiltrosBar lookups={lookups} value={filtros} onChange={setFiltros} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        <KPICard title="Total" value={String(kpis?.total ?? "—")} loading={loading} accentColor="blue" />
        <ClickableTileWrapper onClick={() => setDrillDown({ titulo: "Vagas Abertas", itens: data?.abertas_lista ?? [] })}>
          <KPICard title="Abertas" value={String(kpis?.abertas ?? "—")} loading={loading} accentColor="blue" />
        </ClickableTileWrapper>
        <KPICard title="Concluídas" value={String(kpis?.concluidas_periodo ?? "—")} loading={loading} accentColor="green" />
        <KPICard title="SLA médio (dias)" value={kpis?.sla_medio_dias != null ? String(kpis.sla_medio_dias) : "—"} loading={loading} accentColor="teal" />
        <KPICard title="% no prazo" value={kpis?.pct_no_prazo != null ? `${kpis.pct_no_prazo}%` : "—"} loading={loading} accentColor="violet" />
        <ClickableTileWrapper onClick={() => setDrillDown({ titulo: "Vagas Atrasadas", itens: data?.sla_estourado ?? [] })}>
          <KPICard title="Atrasadas" value={String(kpis?.atrasadas ?? "—")} loading={loading} accentColor="amber" />
        </ClickableTileWrapper>
        <ClickableTileWrapper onClick={() => setDrillDown({ titulo: "Canceladas / Congeladas", itens: data?.canceladas_congeladas_lista ?? [] })}>
          <KPICard title="Canceladas/Congeladas" value={String((kpis?.canceladas ?? 0) + (kpis?.congeladas ?? 0))} loading={loading} accentColor="red" />
        </ClickableTileWrapper>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Vagas por status</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data?.por_status ?? []}
                dataKey="total"
                nameKey="status"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
              >
                {(data?.por_status ?? []).map((d) => (
                  <Cell key={d.status} fill={STATUS_CORES[d.status] ?? "#94a3b8"} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Vagas por empresa</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data?.por_empresa ?? []}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="empresa" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Tendência mensal — abertas vs. concluídas</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data?.tendencia_mensal ?? []}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="abertas" stroke="#3b82f6" name="Abertas" strokeWidth={2} />
              <Line type="monotone" dataKey="concluidas" stroke="#22c55e" name="Concluídas" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Cargos mais requisitados</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={cargosData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="cargo" width={160} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Funil de etapas do processo</h3>
        <EtapaFunnelChart data={data?.funil_etapas ?? []} />
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Vagas por analista</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Analista</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-right">Abertas</th>
                <th className="px-3 py-2 text-right">Concluídas</th>
                <th className="px-3 py-2 text-right">Canceladas</th>
                <th className="px-3 py-2 text-right">Congeladas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {(data?.por_analista ?? []).map((a) => (
                <tr key={a.analista}>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{a.analista}</td>
                  <td className="px-3 py-2 text-right font-semibold text-gray-900 dark:text-gray-100">{a.total}</td>
                  <td className="px-3 py-2 text-right text-blue-600 dark:text-blue-400">{a.abertas}</td>
                  <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">{a.concluidas}</td>
                  <td className="px-3 py-2 text-right text-red-600 dark:text-red-400">{a.canceladas}</td>
                  <td className="px-3 py-2 text-right text-gray-500 dark:text-gray-400">{a.congeladas}</td>
                </tr>
              ))}
              {(!data?.por_analista || data.por_analista.length === 0) && (
                <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Sem dados para os filtros atuais.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {drillDown && (
        <DrillDownVagasModal
          titulo={drillDown.titulo}
          itens={drillDown.itens}
          onClose={() => setDrillDown(null)}
          onAbrirVaga={(id) => setVagaAberta(id)}
        />
      )}

      {vagaAberta && (
        <VagaFormModal
          vagaId={vagaAberta}
          lookups={lookups}
          token={token}
          onClose={() => setVagaAberta(null)}
          onSaved={() => {
            const qs = filtrosToQueryString(filtros);
            apiFetch<DashboardData>(`/api/rh/dashboard${qs ? `?${qs}` : ""}`, { token }).then(setData);
          }}
        />
      )}
    </div>
  );
}
