import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { LinhaAdiantamento } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function AdiantamentosTab() {
  const { token } = useAuth();
  const [data, setData] = useState<LinhaAdiantamento[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [sql, setSql] = useState("");
  const [showSql, setShowSql] = useState(false);

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const p = new URLSearchParams({ natureza: f.natureza, dataInicio: f.dataInicio, dataFim: f.dataFim });
      if (f.empresa) p.set("empresa", f.empresa);
      const res = await apiFetch<LinhaAdiantamento[]>(`/api/financeiro/adiantamentos?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar adiantamentos.");
    } finally {
      setLoading(false);
    }
  }

  const totalPendente = data.filter(r => r.status === "pendente").reduce((s, r) => s + r.valor, 0);
  const totalBaixado  = data.filter(r => r.status === "baixado").reduce((s, r) => s + r.valor, 0);

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} mostrarNatureza />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data.length > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="rounded-lg border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950 px-4 py-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Pendente</p>
              <p className="text-xl font-bold text-yellow-600 tabular-nums">{BRL(totalPendente)}</p>
            </div>
            <div className="rounded-lg border-l-4 border-green-500 bg-green-50 dark:bg-green-950 px-4 py-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Baixado</p>
              <p className="text-xl font-bold text-green-600 tabular-nums">{BRL(totalBaixado)}</p>
            </div>
            <div className="rounded-lg border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950 px-4 py-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Total</p>
              <p className="text-xl font-bold text-blue-600 tabular-nums">{BRL(totalPendente + totalBaixado)}</p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Adiantamentos ({data.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Data</th>
                    <th className="pb-1 text-left">Documento</th>
                    <th className="pb-1 text-left">Pessoa</th>
                    <th className="pb-1 text-left">CPF/CNPJ</th>
                    <th className="pb-1 text-left">Histórico</th>
                    <th className="pb-1 text-right">Valor</th>
                    <th className="pb-1 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5 tabular-nums">{r.data}</td>
                      <td className="py-1.5 font-mono text-xs text-gray-500">{r.documento}</td>
                      <td className="py-1.5">{r.pessoaNome || "—"}</td>
                      <td className="py-1.5 font-mono text-xs text-gray-400">{r.cpfCnpj || "—"}</td>
                      <td className="py-1.5 text-gray-500 max-w-[160px] truncate">{r.historico || "—"}</td>
                      <td className="py-1.5 text-right tabular-nums font-medium">{BRL(r.valor)}</td>
                      <td className="py-1.5 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${
                          r.status === "baixado"
                            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                            : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                        }`}>{r.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {showSql && <SqlDebugModal sql={sql} onClose={() => setShowSql(false)} />}
    </div>
  );
}
