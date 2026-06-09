import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { LinhaLog } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function LogMovimentacoesTab() {
  const { token } = useAuth();
  const [data, setData] = useState<LinhaLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [sql, setSql] = useState("");
  const [showSql, setShowSql] = useState(false);

  async function buscar(f: FiltroValues) {
    setLoading(true); setErro("");
    try {
      const p = new URLSearchParams({ dataInicio: f.dataInicio, dataFim: f.dataFim });
      if (f.empresa) p.set("empresa", f.empresa);
      if (f.filial)  p.set("filial", f.filial);
      const res = await apiFetch<LinhaLog[]>(`/api/financeiro/log-movimentacoes?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar log.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} mostrarFilial />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            Log de Movimentações ({data.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                  <th className="pb-1 text-left">Data Mov.</th>
                  <th className="pb-1 text-left">Documento</th>
                  <th className="pb-1 text-left">Pessoa</th>
                  <th className="pb-1 text-left">Operação</th>
                  <th className="pb-1 text-left">CC</th>
                  <th className="pb-1 text-left">Conta Contábil</th>
                  <th className="pb-1 text-right">Valor</th>
                  <th className="pb-1 text-center">N</th>
                  <th className="pb-1 text-center">C</th>
                  <th className="pb-1 text-left">Inclusão</th>
                  <th className="pb-1 text-left">Usuário</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-1.5 tabular-nums">{r.data}</td>
                    <td className="py-1.5 font-mono text-xs text-gray-500">{r.documento}</td>
                    <td className="py-1.5 max-w-[140px] truncate">{r.pessoaNome || "—"}</td>
                    <td className="py-1.5 text-gray-500 max-w-[120px] truncate">{r.operacao || "—"}</td>
                    <td className="py-1.5 text-gray-500 max-w-[100px] truncate">{r.centroCusto || "—"}</td>
                    <td className="py-1.5 text-gray-500 max-w-[120px] truncate">{r.contaContabil || "—"}</td>
                    <td className={`py-1.5 text-right tabular-nums font-medium ${r.natureza === "C" ? "text-green-600" : "text-red-500"}`}>
                      {r.natureza === "D" ? "−" : "+"}{BRL(r.valor)}
                    </td>
                    <td className="py-1.5 text-center text-gray-400 text-xs">{r.natureza}</td>
                    <td className="py-1.5 text-center text-gray-400 text-xs">{r.contabilizado}</td>
                    <td className="py-1.5 tabular-nums text-xs text-gray-400">{r.dataInclusao?.slice(0, 16)}</td>
                    <td className="py-1.5 text-gray-500">{r.usuarioInclusao || "—"}</td>
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
