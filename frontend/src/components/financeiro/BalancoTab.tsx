import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { LinhaBalanco } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function BalancoTab() {
  const { token } = useAuth();
  const [data, setData] = useState<LinhaBalanco[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [sql, setSql] = useState("");
  const [showSql, setShowSql] = useState(false);

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const p = new URLSearchParams({ dataInicio: f.dataInicio, dataFim: f.dataFim });
      if (f.empresa) p.set("empresa", f.empresa);
      const res = await apiFetch<LinhaBalanco[]>(`/api/financeiro/balanco?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar balanço.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            Balanço Contábil ({data.length} contas)
          </h3>
          <p className="text-xs text-gray-400 mb-2">Competência baseada no período selecionado (AAAA-MM)</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                  <th className="pb-1 text-left">Estrutura</th>
                  <th className="pb-1 text-left">Conta</th>
                  <th className="pb-1 text-center">Tipo</th>
                  <th className="pb-1 text-right">Débitos</th>
                  <th className="pb-1 text-right">Créditos</th>
                  <th className="pb-1 text-right">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {data.map((l, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-1.5 font-mono text-xs text-gray-400">{l.estrutura}</td>
                    <td className="py-1.5">{l.nome}</td>
                    <td className="py-1.5 text-center text-gray-500">{l.tipo}</td>
                    <td className="py-1.5 text-right tabular-nums text-red-500">{BRL(l.debitos)}</td>
                    <td className="py-1.5 text-right tabular-nums text-green-600">{BRL(l.creditos)}</td>
                    <td className={`py-1.5 text-right tabular-nums font-medium ${l.saldo >= 0 ? "text-blue-600" : "text-red-500"}`}>
                      {BRL(l.saldo)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {showSql && <SqlDebugModal sql={sql} onClose={() => setShowSql(false)} />}
    </div>
  );
}
