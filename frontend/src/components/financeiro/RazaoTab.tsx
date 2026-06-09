import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { LinhaRazao } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function RazaoTab() {
  const { token } = useAuth();
  const [data, setData] = useState<LinhaRazao[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [sql, setSql] = useState("");
  const [showSql, setShowSql] = useState(false);

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const p = new URLSearchParams({ natureza: f.natureza, dataInicio: f.dataInicio, dataFim: f.dataFim });
      if (f.empresa) p.set("empresa", f.empresa);
      if (f.filial)  p.set("filial", f.filial);
      const res = await apiFetch<LinhaRazao[]>(`/api/financeiro/razao?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar razão.");
    } finally {
      setLoading(false);
    }
  }

  const total = data.reduce((s, r) => s + r.valor, 0);

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} mostrarFilial mostrarNatureza />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data.length > 0 && (
        <div>
          <div className="flex items-center gap-4 mb-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Razão Auxiliar ({data.length} registros)
            </h3>
            <span className="text-sm font-bold tabular-nums text-blue-600">{BRL(total)}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                  <th className="pb-1 text-left">Data</th>
                  <th className="pb-1 text-left">Documento</th>
                  <th className="pb-1 text-left">Pessoa</th>
                  <th className="pb-1 text-left">CPF/CNPJ</th>
                  <th className="pb-1 text-left">Histórico</th>
                  <th className="pb-1 text-left">CC</th>
                  <th className="pb-1 text-left">Conta Contábil</th>
                  <th className="pb-1 text-right">Valor</th>
                  <th className="pb-1 text-center">Contab.</th>
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
                    <td className="py-1.5 text-gray-500 max-w-[120px] truncate">{r.centroCusto || "—"}</td>
                    <td className="py-1.5 text-gray-500 max-w-[120px] truncate">{r.contaContabil || "—"}</td>
                    <td className="py-1.5 text-right tabular-nums font-medium text-blue-600">{BRL(r.valor)}</td>
                    <td className="py-1.5 text-center text-gray-400">{r.contabilizado}</td>
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
