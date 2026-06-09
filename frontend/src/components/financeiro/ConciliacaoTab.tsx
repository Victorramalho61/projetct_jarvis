import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import type { ConciliacaoData } from "../../types/financeiro";
import FiltroFinanceiro from "./FiltroFinanceiro";
import type { FiltroValues } from "./FiltroFinanceiro";
import SqlDebugModal from "./SqlDebugModal";

const BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const STATUS_BADGE: Record<string, string> = {
  conciliado:   "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  contabilizado: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  pendente:     "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
};

export default function ConciliacaoTab() {
  const { token } = useAuth();
  const [data, setData] = useState<ConciliacaoData | null>(null);
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
      if (f.conta)   p.set("conta", f.conta);
      const res = await apiFetch<ConciliacaoData>(`/api/financeiro/conciliacao?${p}`, {
        token,
        onHeaders: h => { const s = h.get("X-SQL"); if (s) setSql(decodeURIComponent(s)); },
      });
      setData(res);
    } catch (e: any) {
      setErro(e.message ?? "Erro ao carregar conciliação.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <FiltroFinanceiro onBuscar={buscar} loading={loading} mostrarFilial mostrarConta />
      {erro && <p className="text-sm text-red-500">{erro}</p>}
      {sql && (
        <button onClick={() => setShowSql(true)} className="text-xs font-mono px-2 py-1 bg-gray-800 text-green-400 rounded border border-gray-600 hover:bg-gray-700">
          {"{ }"} SQL
        </button>
      )}

      {data && (
        <>
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Resumo por Conta ({data.resumoPorConta.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Banco</th>
                    <th className="pb-1 text-left">Conta</th>
                    <th className="pb-1 text-right">Crédito</th>
                    <th className="pb-1 text-right">Débito</th>
                    <th className="pb-1 text-right">Saldo</th>
                    <th className="pb-1 text-right">Lançamentos</th>
                    <th className="pb-1 text-right">Conciliados</th>
                  </tr>
                </thead>
                <tbody>
                  {data.resumoPorConta.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5">{r.banco || "—"}</td>
                      <td className="py-1.5 text-gray-500">{r.conta}</td>
                      <td className="py-1.5 text-right tabular-nums text-green-600">{BRL(r.totalCredito)}</td>
                      <td className="py-1.5 text-right tabular-nums text-red-500">{BRL(r.totalDebito)}</td>
                      <td className={`py-1.5 text-right tabular-nums font-medium ${r.saldo >= 0 ? "text-green-600" : "text-red-500"}`}>{BRL(r.saldo)}</td>
                      <td className="py-1.5 text-right text-gray-500">{r.totalLancamentos}</td>
                      <td className="py-1.5 text-right text-gray-500">{r.conciliados}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Movimentações ({data.movimentacoes.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500">
                    <th className="pb-1 text-left">Data</th>
                    <th className="pb-1 text-left">Documento</th>
                    <th className="pb-1 text-left">Pessoa</th>
                    <th className="pb-1 text-left">Histórico</th>
                    <th className="pb-1 text-left">Banco/Conta</th>
                    <th className="pb-1 text-right">Valor</th>
                    <th className="pb-1 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.movimentacoes.map((m, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-1.5 tabular-nums">{m.data}</td>
                      <td className="py-1.5 text-gray-500 font-mono text-xs">{m.documento}</td>
                      <td className="py-1.5">{m.pessoaNome || "—"}</td>
                      <td className="py-1.5 text-gray-500 max-w-[200px] truncate">{m.historico || "—"}</td>
                      <td className="py-1.5 text-gray-500">{m.banco ? `${m.banco} / ${m.conta}` : m.conta || "—"}</td>
                      <td className={`py-1.5 text-right tabular-nums font-medium ${m.natureza === "C" ? "text-green-600" : "text-red-500"}`}>
                        {m.natureza === "D" ? "−" : "+"}{BRL(m.valor)}
                      </td>
                      <td className="py-1.5 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_BADGE[m.status]}`}>{m.status}</span>
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
