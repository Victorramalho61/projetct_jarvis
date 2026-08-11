import { useMemo, useState } from "react";
import type { ExpenseRow } from "../../types/expenses";

type Props = {
  titulo: string;
  subtitulo?: string;
  itens: ExpenseRow[];
  onClose: () => void;
};

type Coluna = "PESSOA" | "FILIAL" | "DATAVENCIMENTO" | "DATALIQUIDACAO" | "VALOR";

const FMT_BRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const FMT_DATA = (v: string | null) =>
  v ? new Date(v).toLocaleDateString("pt-BR") : "—";

function statusPagamento(row: ExpenseRow): { label: string; className: string } {
  const hoje = new Date().toISOString().slice(0, 10);
  const vencimento = row.DATAVENCIMENTO ?? null;
  const liquidacao = row.DATALIQUIDACAO ?? null;

  if (!liquidacao) {
    if (vencimento && vencimento.slice(0, 10) < hoje) {
      return { label: "Atrasada", className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300" };
    }
    return { label: "A vencer", className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300" };
  }
  if (vencimento && liquidacao.slice(0, 10) > vencimento.slice(0, 10)) {
    return { label: "Pago com atraso", className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" };
  }
  return { label: "Pago no prazo", className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300" };
}

export default function ExpenseDrillDownModal({ titulo, subtitulo, itens, onClose }: Props) {
  const [busca, setBusca] = useState("");
  const [ordenarPor, setOrdenarPor] = useState<Coluna>("VALOR");
  const [ordemDesc, setOrdemDesc] = useState(true);

  const itensFiltrados = useMemo(() => {
    let lista = itens;
    if (busca.trim()) {
      const b = busca.trim().toLowerCase();
      lista = lista.filter((i) =>
        (i.PESSOA ?? "").toLowerCase().includes(b) ||
        (i.HISTORICO ?? "").toLowerCase().includes(b) ||
        (i.FILIAL ?? "").toLowerCase().includes(b)
      );
    }
    const copia = [...lista];
    copia.sort((a, b) => {
      const va = a[ordenarPor];
      const vb = b[ordenarPor];
      const na = va == null ? -Infinity : va;
      const nb = vb == null ? -Infinity : vb;
      const cmp = typeof na === "string" && typeof nb === "string" ? na.localeCompare(nb) : (na as number) - (nb as number);
      return ordemDesc ? -cmp : cmp;
    });
    return copia;
  }, [itens, busca, ordenarPor, ordemDesc]);

  const totalValor = useMemo(() => itensFiltrados.reduce((acc, i) => acc + (i.VALOR ?? 0), 0), [itensFiltrados]);

  function alternarOrdenacao(coluna: Coluna) {
    if (ordenarPor === coluna) {
      setOrdemDesc((v) => !v);
    } else {
      setOrdenarPor(coluna);
      setOrdemDesc(true);
    }
  }

  function Th({ coluna, label, className = "" }: { coluna: Coluna; label: string; className?: string }) {
    const ativo = ordenarPor === coluna;
    return (
      <th
        onClick={() => alternarOrdenacao(coluna)}
        className={`cursor-pointer select-none px-3 py-2 hover:text-gray-700 dark:hover:text-gray-200 ${className}`}
      >
        {label} {ativo && (ordemDesc ? "↓" : "↑")}
      </th>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        className="flex w-full max-w-4xl flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">{titulo}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {subtitulo ? `${subtitulo} · ` : ""}{itensFiltrados.length} de {itens.length} parcela(s) · {FMT_BRL(totalValor)}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        <div className="border-b border-gray-100 dark:border-gray-800 px-4 py-3 sm:px-6">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por fornecedor, filial ou histórico..."
            className="w-full max-w-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex-1 overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800/80 text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <tr>
                <Th coluna="PESSOA" label="Fornecedor" />
                <Th coluna="FILIAL" label="Filial" />
                <Th coluna="DATAVENCIMENTO" label="Vencimento" />
                <Th coluna="DATALIQUIDACAO" label="Liquidação" />
                <Th coluna="VALOR" label="Valor" className="text-right" />
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {itensFiltrados.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">Nenhuma parcela encontrada.</td></tr>
              )}
              {itensFiltrados.map((i, idx) => {
                const status = statusPagamento(i);
                return (
                  <tr key={idx} className="text-gray-700 dark:text-gray-300">
                    <td className="px-3 py-2">{i.PESSOA ?? "—"}</td>
                    <td className="px-3 py-2">{i.FILIAL ?? "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{FMT_DATA(i.DATAVENCIMENTO)}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{FMT_DATA(i.DATALIQUIDACAO)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{FMT_BRL(i.VALOR ?? 0)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${status.className}`}>
                        {status.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
