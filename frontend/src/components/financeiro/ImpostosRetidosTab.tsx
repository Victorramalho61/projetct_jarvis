import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { ImpostosRetidosData } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function ImpostosRetidosTab() {
  const { token } = useAuth();
  const [data, setData] = useState<ImpostosRetidosData | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const p = new URLSearchParams({ dataInicio: f.dataInicio, dataFim: f.dataFim });
      if (f.empresa) p.set("empresa", f.empresa);
      const res = await apiFetch<ImpostosRetidosData>(`/api/financeiro/impostos-retidos?${p}`, { token });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar impostos retidos.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} />
      {erro && <p className="text-sm text-red-500">{erro}</p>}

      {data && (
        <>
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Totais do Período</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { label: "IRRF",   value: data.totais.irrf },
                { label: "PIS",    value: data.totais.pis },
                { label: "COFINS", value: data.totais.cofins },
                { label: "ISS",    value: data.totais.iss },
                { label: "CSLL",   value: data.totais.csll },
                { label: "Total Retido", value: data.totais.totalRetido },
              ].map(t => (
                <div key={t.label} className={`rounded-lg p-3 ${t.label === "Total Retido" ? "bg-yellow-50 dark:bg-yellow-950 border border-yellow-300 dark:border-yellow-700" : "bg-gray-100 dark:bg-gray-800"}`}>
                  <p className="text-xs text-gray-500">{t.label}</p>
                  <p className={`text-base font-bold tabular-nums ${t.label === "Total Retido" ? "text-yellow-700 dark:text-yellow-300" : "text-gray-800 dark:text-gray-100"}`}>
                    {BRL(t.value)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Detalhes ({data.detalhes.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Data</th>
                    <th className="pb-1 text-left">Documento</th>
                    <th className="pb-1 text-left">Pessoa</th>
                    <th className="pb-1 text-right">Vl. Bruto</th>
                    <th className="pb-1 text-right">IRRF</th>
                    <th className="pb-1 text-right">PIS</th>
                    <th className="pb-1 text-right">COFINS</th>
                    <th className="pb-1 text-right">ISS</th>
                    <th className="pb-1 text-right">CSLL</th>
                    <th className="pb-1 text-right">Total Ret.</th>
                    <th className="pb-1 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.detalhes.map((d, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5 tabular-nums">{d.data}</td>
                      <td className="py-1.5 font-mono text-xs text-gray-500">{d.documento}</td>
                      <td className="py-1.5 max-w-[160px] truncate">{d.pessoaNome || "—"}</td>
                      <td className="py-1.5 text-right tabular-nums">{BRL(d.valorBruto)}</td>
                      <td className="py-1.5 text-right tabular-nums text-orange-500">{BRL(d.irrf)}</td>
                      <td className="py-1.5 text-right tabular-nums text-orange-500">{BRL(d.pis)}</td>
                      <td className="py-1.5 text-right tabular-nums text-orange-500">{BRL(d.cofins)}</td>
                      <td className="py-1.5 text-right tabular-nums text-orange-500">{BRL(d.iss)}</td>
                      <td className="py-1.5 text-right tabular-nums text-orange-500">{BRL(d.csll)}</td>
                      <td className="py-1.5 text-right tabular-nums font-medium text-yellow-600">{BRL(d.totalRetencoes)}</td>
                      <td className="py-1.5 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${
                          d.statusBaixa === "baixado"
                            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                            : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                        }`}>{d.statusBaixa}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
