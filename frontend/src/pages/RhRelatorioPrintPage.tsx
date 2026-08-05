import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types/rh";

export default function RhRelatorioPrintPage() {
  const [searchParams] = useSearchParams();
  const { token } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    const qs = searchParams.toString();
    apiFetch<DashboardData>(`/api/rh/dashboard${qs ? `?${qs}` : ""}`, { token }).then(setData);
  }, [searchParams, token]);

  const geradoEm = new Date().toLocaleString("pt-BR");
  const periodo = [searchParams.get("data_inicio"), searchParams.get("data_fim")].filter(Boolean).join(" a ");

  if (!data) {
    return <div className="p-8 text-center text-gray-500">Carregando relatório...</div>;
  }

  const k = data.kpis;

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950 py-8 print:bg-white print:py-0">
      <style>{`@media print { .no-print { display: none !important; } body { background: white; } }`}</style>

      <div className="mx-auto max-w-4xl bg-white text-black p-8 shadow-lg print:shadow-none">
        <div className="flex justify-end no-print mb-4">
          <button onClick={() => window.print()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Imprimir
          </button>
        </div>

        <div className="border-b-2 border-black pb-3 mb-4">
          <h1 className="text-2xl font-bold">Status das Vagas de Recursos Humanos do Grupo Voetur</h1>
          <p className="text-sm text-gray-600 mt-1">
            Gerado em {geradoEm}{periodo ? ` — período filtrado: ${periodo}` : ""}
          </p>
        </div>

        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            ["Total de vagas", k.total],
            ["Abertas", k.abertas],
            ["Concluídas", k.concluidas_periodo],
            ["Atrasadas", k.atrasadas],
            ["SLA médio (dias)", k.sla_medio_dias ?? "—"],
            ["% no prazo", k.pct_no_prazo != null ? `${k.pct_no_prazo}%` : "—"],
            ["Canceladas", k.canceladas],
            ["Congeladas", k.congeladas],
          ].map(([label, value]) => (
            <div key={label as string} className="border border-gray-300 rounded-lg p-3 text-center">
              <p className="text-[10px] uppercase tracking-wide text-gray-500">{label}</p>
              <p className="text-xl font-bold">{value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide border-b border-black pb-1 mb-2">Por status</h2>
            <table className="w-full text-sm">
              <tbody>
                {data.por_status.map((s) => (
                  <tr key={s.status} className="border-b border-gray-200">
                    <td className="py-1">{s.status}</td>
                    <td className="py-1 text-right font-semibold">{s.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide border-b border-black pb-1 mb-2">Por empresa</h2>
            <table className="w-full text-sm">
              <tbody>
                {data.por_empresa.map((e) => (
                  <tr key={e.empresa} className="border-b border-gray-200">
                    <td className="py-1">{e.empresa}</td>
                    <td className="py-1 text-right font-semibold">{e.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide border-b border-black pb-1 mb-2">Cargos mais requisitados</h2>
            <table className="w-full text-sm">
              <tbody>
                {data.top_cargos.map((c) => (
                  <tr key={c.cargo} className="border-b border-gray-200">
                    <td className="py-1">{c.cargo}</td>
                    <td className="py-1 text-right font-semibold">{c.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide border-b border-black pb-1 mb-2">Funil de etapas do processo</h2>
            <table className="w-full text-sm">
              <tbody>
                {data.funil_etapas.filter((f) => f.total > 0).map((f) => (
                  <tr key={f.etapa} className="border-b border-gray-200">
                    <td className="py-1">{f.etapa}</td>
                    <td className="py-1 text-right font-semibold">{f.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
