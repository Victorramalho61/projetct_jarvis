import type { Vaga } from "../../types/rh";

type Props = {
  vagas: Vaga[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onSelect: (vaga: Vaga) => void;
  loading?: boolean;
};

const STATUS_COLOR: Record<string, string> = {
  "EM ANDAMENTO": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  "REABERTO": "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  "CONCLUÍDO": "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  "CANCELADO": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  "CONGELADO": "bg-slate-200 text-slate-700 dark:bg-slate-700/40 dark:text-slate-300",
};

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-gray-400">—</span>;
  const cls = STATUS_COLOR[status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${cls}`}>{status}</span>;
}

function SlaBadge({ vaga }: { vaga: Vaga }) {
  if (vaga.sla_ok === null || vaga.sla_ok === undefined) return <span className="text-gray-400 text-xs">—</span>;
  return vaga.sla_ok ? (
    <span className="text-[11px] font-semibold text-green-600 dark:text-green-400">NO PRAZO</span>
  ) : (
    <span className="text-[11px] font-semibold text-red-600 dark:text-red-400">ATRASO</span>
  );
}

export default function VagasTable({ vagas, total, page, pageSize, onPageChange, onSelect, loading }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800/60 text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-4 py-2.5">Nº Requisição</th>
              <th className="px-4 py-2.5">Empresa</th>
              <th className="px-4 py-2.5">Cargo</th>
              <th className="px-4 py-2.5">Candidato</th>
              <th className="px-4 py-2.5">Etapa atual</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Dias / SLA</th>
              <th className="px-4 py-2.5">Responsável</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Carregando...</td></tr>
            )}
            {!loading && vagas.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Nenhuma vaga encontrada com os filtros atuais.</td></tr>
            )}
            {!loading && vagas.map((v) => (
              <tr
                key={v.id}
                onClick={() => onSelect(v)}
                className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/60"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-gray-700 dark:text-gray-300">{v.numero_requisicao ?? "—"}</td>
                <td className="px-4 py-2.5">{v.empresa ?? "—"}</td>
                <td className="px-4 py-2.5">{v.cargo ?? "—"}</td>
                <td className="px-4 py-2.5">{v.candidato ?? "—"}</td>
                <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">{v.etapa_atual ?? "—"}</td>
                <td className="px-4 py-2.5"><StatusBadge status={v.status} /></td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-col">
                    <span className="text-xs text-gray-600 dark:text-gray-300">{v.dias_corridos ?? "—"} dias</span>
                    <SlaBadge vaga={v} />
                  </div>
                </td>
                <td className="px-4 py-2.5">{v.responsavel ?? "—"}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); window.open(`/rh/vagas/${v.id}/imprimir`, "_blank"); }}
                    className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
                  >
                    Imprimir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-gray-100 dark:border-gray-800 px-4 py-3 text-sm">
        <span className="text-gray-500 dark:text-gray-400">{total} vaga(s) encontrada(s)</span>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1 disabled:opacity-40"
          >
            ← Anterior
          </button>
          <span className="text-gray-500 dark:text-gray-400">{page} / {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1 disabled:opacity-40"
          >
            Próxima →
          </button>
        </div>
      </div>
    </div>
  );
}
