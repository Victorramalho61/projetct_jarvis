import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart,
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

  // Produtividade por analista — congelada é bucket próprio, separado de "em andamento"
  const analistaStats = useMemo(() => {
    const linhas = data?.por_analista ?? [];
    const totalConcluidas = linhas.reduce((s, a) => s + a.concluidas, 0);
    const totalAbertas = linhas.reduce((s, a) => s + a.abertas, 0);
    const totalCongeladas = linhas.reduce((s, a) => s + a.congeladas, 0);
    return linhas
      .map((a) => ({
        ...a,
        pctConcluidaDoTotal: a.total > 0 ? (a.concluidas / a.total) * 100 : 0,
        pctAbertaDoTotal: a.total > 0 ? (a.abertas / a.total) * 100 : 0,
        pctCongeladaDoTotal: a.total > 0 ? (a.congeladas / a.total) * 100 : 0,
        pctCanceladaDoTotal: a.total > 0 ? (a.canceladas / a.total) * 100 : 0,
        pctShareConcluidas: totalConcluidas > 0 ? (a.concluidas / totalConcluidas) * 100 : 0,
        pctShareAbertas: totalAbertas > 0 ? (a.abertas / totalAbertas) * 100 : 0,
        pctShareCongeladas: totalCongeladas > 0 ? (a.congeladas / totalCongeladas) * 100 : 0,
      }))
      .sort((a, b) => b.total - a.total);
  }, [data]);

  const rankingConcluidas = useMemo(
    () => [...analistaStats].sort((a, b) => b.concluidas - a.concluidas),
    [analistaStats]
  );
  const rankingAbertas = useMemo(
    () => [...analistaStats].sort((a, b) => b.abertas - a.abertas),
    [analistaStats]
  );
  const rankingCongeladas = useMemo(
    () => [...analistaStats].sort((a, b) => b.congeladas - a.congeladas),
    [analistaStats]
  );

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
        <ClickableTileWrapper hintSempreVisivel onClick={() => setDrillDown({ titulo: "Vagas Abertas", itens: data?.abertas_lista ?? [] })}>
          <KPICard title="Abertas" value={String(kpis?.abertas ?? "—")} loading={loading} accentColor="blue" />
        </ClickableTileWrapper>
        <KPICard title="Concluídas" value={String(kpis?.concluidas_periodo ?? "—")} loading={loading} accentColor="green" />
        <KPICard title="SLA médio (dias)" value={kpis?.sla_medio_dias != null ? String(kpis.sla_medio_dias) : "—"} loading={loading} accentColor="teal" />
        <KPICard title="% no prazo" value={kpis?.pct_no_prazo != null ? `${kpis.pct_no_prazo}%` : "—"} loading={loading} accentColor="violet" />
        <ClickableTileWrapper hintSempreVisivel onClick={() => setDrillDown({ titulo: "Vagas Atrasadas", itens: data?.sla_estourado ?? [] })}>
          <KPICard title="Atrasadas" value={String(kpis?.atrasadas ?? "—")} loading={loading} accentColor="amber" />
        </ClickableTileWrapper>
        <ClickableTileWrapper hintSempreVisivel onClick={() => setDrillDown({ titulo: "Canceladas / Congeladas", itens: data?.canceladas_congeladas_lista ?? [] })}>
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
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Vagas fechadas por empresa</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data?.por_empresa_fechadas ?? []} margin={{ top: 20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="empresa" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                <LabelList dataKey="total" position="top" style={{ fontSize: 11, fill: "#3b82f6", fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Vagas por analista</h3>
          <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#22c55e]" /> Concluída</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#3b82f6]" /> Em andamento</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#94a3b8]" /> Congelada</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#ef4444]" /> Cancelada</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Analista</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2">Progresso</th>
                <th className="px-3 py-2 text-right">Concluídas</th>
                <th className="px-3 py-2 text-right">Andamento</th>
                <th className="px-3 py-2 text-right">Congeladas</th>
                <th className="px-3 py-2 text-right">Canceladas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {analistaStats.map((a) => (
                <tr key={a.analista}>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{a.analista}</td>
                  <td className="px-3 py-2 text-right font-semibold text-gray-900 dark:text-gray-100">{a.total}</td>
                  <td className="px-3 py-2 min-w-[160px]">
                    <div className="flex h-2 w-full gap-[2px] overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                      {a.pctConcluidaDoTotal > 0 && (
                        <div className="h-2 rounded-full bg-[#22c55e]" style={{ width: `${a.pctConcluidaDoTotal}%` }} />
                      )}
                      {a.pctAbertaDoTotal > 0 && (
                        <div className="h-2 rounded-full bg-[#3b82f6]" style={{ width: `${a.pctAbertaDoTotal}%` }} />
                      )}
                      {a.pctCongeladaDoTotal > 0 && (
                        <div className="h-2 rounded-full bg-[#94a3b8]" style={{ width: `${a.pctCongeladaDoTotal}%` }} />
                      )}
                      {a.pctCanceladaDoTotal > 0 && (
                        <div className="h-2 rounded-full bg-[#ef4444]" style={{ width: `${a.pctCanceladaDoTotal}%` }} />
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-gray-400">{a.pctConcluidaDoTotal.toFixed(0)}% concluído</p>
                  </td>
                  <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">
                    {a.concluidas} <span className="text-gray-400">({a.pctConcluidaDoTotal.toFixed(0)}%)</span>
                  </td>
                  <td className="px-3 py-2 text-right text-blue-600 dark:text-blue-400">
                    {a.abertas} <span className="text-gray-400">({a.pctAbertaDoTotal.toFixed(0)}%)</span>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-500 dark:text-slate-400">
                    {a.congeladas} <span className="text-gray-400">({a.pctCongeladaDoTotal.toFixed(0)}%)</span>
                  </td>
                  <td className="px-3 py-2 text-right text-red-600 dark:text-red-400">
                    {a.canceladas} <span className="text-gray-400">({a.pctCanceladaDoTotal.toFixed(0)}%)</span>
                  </td>
                </tr>
              ))}
              {analistaStats.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Sem dados para os filtros atuais.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-gray-100 dark:border-gray-800 p-3">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Produtividade — vagas concluídas
            </h4>
            <p className="mb-3 text-[11px] text-gray-400">% de quanto cada analista fechou em relação ao total concluído pela equipe</p>
            <div className="space-y-2">
              {rankingConcluidas.map((a) => (
                <div key={a.analista} className="flex items-center gap-2 text-xs">
                  <span className="w-28 shrink-0 truncate text-gray-600 dark:text-gray-300">{a.analista}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                    <div className="h-2 rounded-full bg-[#22c55e]" style={{ width: `${a.pctShareConcluidas}%` }} />
                  </div>
                  <span className="w-20 shrink-0 text-right tabular-nums text-gray-500 dark:text-gray-400">
                    {a.concluidas} · {a.pctShareConcluidas.toFixed(0)}%
                  </span>
                </div>
              ))}
              {rankingConcluidas.length === 0 && <p className="text-xs text-gray-400">Sem dados.</p>}
            </div>
          </div>

          <div className="rounded-lg border border-gray-100 dark:border-gray-800 p-3">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Carga atual — vagas em andamento
            </h4>
            <p className="mb-3 text-[11px] text-gray-400">% de quanto cada analista está atuando em relação ao total em andamento da equipe (não inclui congelada)</p>
            <div className="space-y-2">
              {rankingAbertas.map((a) => (
                <div key={a.analista} className="flex items-center gap-2 text-xs">
                  <span className="w-28 shrink-0 truncate text-gray-600 dark:text-gray-300">{a.analista}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                    <div className="h-2 rounded-full bg-[#3b82f6]" style={{ width: `${a.pctShareAbertas}%` }} />
                  </div>
                  <span className="w-20 shrink-0 text-right tabular-nums text-gray-500 dark:text-gray-400">
                    {a.abertas} · {a.pctShareAbertas.toFixed(0)}%
                  </span>
                </div>
              ))}
              {rankingAbertas.length === 0 && <p className="text-xs text-gray-400">Sem dados.</p>}
            </div>
          </div>

          <div className="rounded-lg border border-gray-100 dark:border-gray-800 p-3">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Vagas congeladas
            </h4>
            <p className="mb-3 text-[11px] text-gray-400">% de quanto cada analista tem parado em relação ao total congelado da equipe</p>
            <div className="space-y-2">
              {rankingCongeladas.map((a) => (
                <div key={a.analista} className="flex items-center gap-2 text-xs">
                  <span className="w-28 shrink-0 truncate text-gray-600 dark:text-gray-300">{a.analista}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                    <div className="h-2 rounded-full bg-[#94a3b8]" style={{ width: `${a.pctShareCongeladas}%` }} />
                  </div>
                  <span className="w-20 shrink-0 text-right tabular-nums text-gray-500 dark:text-gray-400">
                    {a.congeladas} · {a.pctShareCongeladas.toFixed(0)}%
                  </span>
                </div>
              ))}
              {rankingCongeladas.length === 0 && <p className="text-xs text-gray-400">Sem dados.</p>}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Tendência mensal — abertas vs. concluídas</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data?.tendencia_mensal ?? []}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="abertas" stroke="#3b82f6" name="Abertas" strokeWidth={2}>
                <LabelList dataKey="abertas" position="top" style={{ fontSize: 10, fill: "#64748b" }} />
              </Line>
              <Line type="monotone" dataKey="concluidas" stroke="#22c55e" name="Concluídas" strokeWidth={2}>
                <LabelList dataKey="concluidas" position="bottom" style={{ fontSize: 10, fill: "#64748b" }} />
              </Line>
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
              <Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]}>
                <LabelList dataKey="total" position="right" style={{ fontSize: 11, fill: "#64748b" }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Funil de etapas do processo</h3>
        <EtapaFunnelChart data={data?.funil_etapas ?? []} />
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
