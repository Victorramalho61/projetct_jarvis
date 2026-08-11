import { useMemo, useState } from "react";
import type { AlertaSla } from "../../types/rh";

type Props = {
  titulo: string;
  itens: AlertaSla[];
  onClose: () => void;
  onAbrirVaga: (id: string) => void;
};

type Coluna = "numero_requisicao" | "cargo" | "empresa" | "responsavel" | "dias_corridos" | "status";

const STATUS_COLOR: Record<string, string> = {
  "EM ANDAMENTO": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  "REABERTO": "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  "CONCLUÍDO": "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  "CANCELADO": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  "CONGELADO": "bg-slate-200 text-slate-700 dark:bg-slate-700/40 dark:text-slate-300",
};

export default function DrillDownVagasModal({ titulo, itens, onClose, onAbrirVaga }: Props) {
  const [busca, setBusca] = useState("");
  const [ordenarPor, setOrdenarPor] = useState<Coluna>("dias_corridos");
  const [ordemDesc, setOrdemDesc] = useState(true);

  const itensFiltrados = useMemo(() => {
    let lista = itens;
    if (busca.trim()) {
      const b = busca.trim().toLowerCase();
      lista = lista.filter((i) =>
        (i.responsavel ?? "").toLowerCase().includes(b) ||
        (i.cargo ?? "").toLowerCase().includes(b) ||
        (i.numero_requisicao ?? "").toLowerCase().includes(b)
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
      <div className="flex w-full max-w-4xl flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">{titulo}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">{itensFiltrados.length} de {itens.length} vaga(s)</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        <div className="border-b border-gray-100 dark:border-gray-800 px-4 py-3 sm:px-6">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por analista, cargo ou nº requisição..."
            className="w-full max-w-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex-1 overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800/80 text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <tr>
                <Th coluna="numero_requisicao" label="Nº Requisição" />
                <Th coluna="cargo" label="Cargo" />
                <Th coluna="empresa" label="Empresa" />
                <Th coluna="responsavel" label="Analista" />
                <Th coluna="dias_corridos" label="Dias/Alvo" />
                <Th coluna="status" label="Status" />
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {itensFiltrados.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-gray-400">Nenhuma vaga encontrada.</td></tr>
              )}
              {itensFiltrados.map((i) => (
                <tr key={i.id} className="text-gray-700 dark:text-gray-300">
                  <td className="px-3 py-2 font-mono text-xs">{i.numero_requisicao ?? "—"}</td>
                  <td className="px-3 py-2">{i.cargo ?? "—"}</td>
                  <td className="px-3 py-2">{i.empresa ?? "—"}</td>
                  <td className="px-3 py-2">{i.responsavel ?? "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{i.dias_corridos ?? "—"}/{i.sla_alvo_dias ?? "—"} dias</td>
                  <td className="px-3 py-2">
                    {i.status && (
                      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${STATUS_COLOR[i.status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"}`}>
                        {i.status}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => onAbrirVaga(i.id)} className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline">
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
