import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { DashboardData, EmpresaBenner } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";

const BRL = (v: number | null) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v ?? 0);

interface KPIProps { label: string; value: string; sub?: string; color?: string }
function KPI({ label, value, sub, color = "blue" }: KPIProps) {
  const colors: Record<string, string> = {
    blue: "border-blue-500 bg-blue-50 dark:bg-blue-950",
    green: "border-green-500 bg-green-50 dark:bg-green-950",
    red: "border-red-500 bg-red-50 dark:bg-red-950",
    yellow: "border-yellow-500 bg-yellow-50 dark:bg-yellow-950",
  };
  return (
    <div className={`rounded-lg border-l-4 p-4 ${colors[color]}`}>
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-800 dark:text-gray-100 tabular-nums">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function DashboardTab() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const params = new URLSearchParams({ empresa: f.empresa });
      if (f.dataInicio) params.set("data", f.dataInicio);
      const res = await apiFetch<DashboardData>(`/api/financeiro/dashboard?${params}`, { token });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar dashboard.");
    } finally {
      setLoading(false);
    }
  }

  const saldo = (data?.entradas.total ?? 0) - (data?.saidas.total ?? 0);

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} dataUnica />

      {erro && <p className="text-sm text-red-500 px-1">{erro}</p>}

      {data && (
        <>
          <p className="text-xs text-gray-400">Referência: {data.referencia}</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KPI label="Entradas" value={BRL(data.entradas.total)} sub={`${data.entradas.qtd} lançamentos`} color="green" />
            <KPI label="Saídas" value={BRL(data.saidas.total)} sub={`${data.saidas.qtd} lançamentos`} color="red" />
            <KPI label="Saldo do dia" value={BRL(saldo)} color={saldo >= 0 ? "blue" : "red"} />
            <KPI label="Total Impostos Retidos" value={BRL((data.impostosRetidos.irrf ?? 0) + (data.impostosRetidos.pis ?? 0) + (data.impostosRetidos.cofins ?? 0) + (data.impostosRetidos.iss ?? 0))} color="yellow" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Saldo por Conta</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Banco</th>
                    <th className="pb-1 text-left">Conta</th>
                    <th className="pb-1 text-right">Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {data.saldoPorConta.map((c, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-1.5 text-gray-700 dark:text-gray-300">{c.banco || "—"}</td>
                      <td className="py-1.5 text-gray-500">{c.conta || "—"}</td>
                      <td className={`py-1.5 text-right tabular-nums font-medium ${c.saldo >= 0 ? "text-green-600" : "text-red-500"}`}>{BRL(c.saldo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Top 5 Centros de Custo</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Centro de Custo</th>
                    <th className="pb-1 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.topCentrosCusto.map((cc, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-1.5 text-gray-700 dark:text-gray-300">{cc.centroCusto}</td>
                      <td className="py-1.5 text-right tabular-nums text-red-500 font-medium">{BRL(cc.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Impostos Retidos</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "IRRF", value: data.impostosRetidos.irrf },
                { label: "PIS",  value: data.impostosRetidos.pis },
                { label: "COFINS", value: data.impostosRetidos.cofins },
                { label: "ISS",  value: data.impostosRetidos.iss },
              ].map(i => (
                <div key={i.label} className="rounded p-3 bg-gray-100 dark:bg-gray-800">
                  <p className="text-xs text-gray-500">{i.label}</p>
                  <p className="text-base font-bold tabular-nums text-gray-800 dark:text-gray-100">{BRL(i.value)}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
