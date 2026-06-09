import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { DespesasData } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function DespesasTab() {
  const { token } = useAuth();
  const [data, setData] = useState<DespesasData | null>(null);
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
      const res = await apiFetch<DespesasData>(`/api/financeiro/despesas?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar despesas.");
    } finally {
      setLoading(false);
    }
  }

  const totalGeral = data?.resumoPorCC.reduce((s, r) => s + r.total, 0) ?? 0;

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} mostrarFilial />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data && (
        <>
          <div>
            <div className="rounded-lg bg-red-50 dark:bg-red-950 border-l-4 border-red-500 px-5 py-3 inline-block">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Total do Período</p>
              <p className="text-2xl font-bold text-red-600 tabular-nums">{BRL(totalGeral)}</p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Resumo por Centro de Custo</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Centro de Custo</th>
                    <th className="pb-1 text-left">Código</th>
                    <th className="pb-1 text-right">Total</th>
                    <th className="pb-1 text-right">Qtd</th>
                    <th className="pb-1 text-right">%</th>
                    <th className="pb-1 pl-3">Participação</th>
                  </tr>
                </thead>
                <tbody>
                  {data.resumoPorCC.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5">{r.centroCusto}</td>
                      <td className="py-1.5 text-gray-500 font-mono text-xs">{r.codigo || "—"}</td>
                      <td className="py-1.5 text-right tabular-nums font-medium text-red-500">{BRL(r.total)}</td>
                      <td className="py-1.5 text-right text-gray-500">{r.qtd}</td>
                      <td className="py-1.5 text-right text-gray-500">{r.pct?.toFixed(1)}%</td>
                      <td className="py-1.5 pl-3">
                        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full w-32">
                          <div className="h-2 bg-red-500 rounded-full" style={{ width: `${Math.min(r.pct ?? 0, 100)}%` }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Detalhe ({data.detalhe.length})</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Data</th>
                    <th className="pb-1 text-left">Documento</th>
                    <th className="pb-1 text-left">Pessoa</th>
                    <th className="pb-1 text-left">Histórico</th>
                    <th className="pb-1 text-left">CC</th>
                    <th className="pb-1 text-left">Conta</th>
                    <th className="pb-1 text-right">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {data.detalhe.map((d, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5 tabular-nums">{d.data}</td>
                      <td className="py-1.5 font-mono text-xs text-gray-500">{d.documento}</td>
                      <td className="py-1.5">{d.pessoaNome || "—"}</td>
                      <td className="py-1.5 text-gray-500 max-w-[160px] truncate">{d.historico || "—"}</td>
                      <td className="py-1.5 text-gray-500 max-w-[120px] truncate">{d.centroCusto || "—"}</td>
                      <td className="py-1.5 text-gray-500">{d.conta || "—"}</td>
                      <td className="py-1.5 text-right tabular-nums font-medium text-red-500">{BRL(d.valor)}</td>
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
