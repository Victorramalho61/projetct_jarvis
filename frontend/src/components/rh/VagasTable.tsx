import type { Vaga } from "../../types/rh";
import { STATUS_VAGA_BADGE } from "../../lib/rhSla";

type Props = {
  vagas: Vaga[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onSelect: (vaga: Vaga) => void;
  loading?: boolean;
};


// Status + fase em que a vaga aberta está (nunca "Aberta" sem dizer a fase)
function StatusBadge({ vaga }: { vaga: Vaga }) {
  const { status } = vaga;
  if (!status) return <span className="text-gray-400">—</span>;
  const cls = STATUS_VAGA_BADGE[status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  const fase = vaga.sla?.fase_atual;
  return (
    <div className="flex flex-col items-start gap-0.5">
      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${cls}`}>{status}</span>
      {fase && <span className="text-[10px] text-gray-500 dark:text-gray-400 whitespace-nowrap">fase: {fase}</span>}
    </div>
  );
}

function PendenciaBadge({ motivos }: { motivos?: string[] }) {
  if (!motivos?.length) return null;
  return (
    <span title={motivos.join(" · ")}
      className="mt-0.5 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 whitespace-nowrap">
      pendência de cadastro
    </span>
  );
}

// Fase corrente: Admissão se já começou, senão R&S (services/sla.py)
function SlaBadge({ vaga }: { vaga: Vaga }) {
  const sla = vaga.sla;
  if (!sla) return <span className="text-gray-400 text-xs">—</span>;
  if (vaga.pendencias?.length) return <PendenciaBadge motivos={vaga.pendencias} />;
  const emAdm = !!sla.adm.inicio;
  const f = emAdm ? sla.adm : sla.rs;
  const cor = f.status.includes("ATRAS") ? "text-red-600 dark:text-red-400"
    : f.status.includes("PRAZO") ? "text-green-600 dark:text-green-400" : "text-gray-500 dark:text-gray-400";
  return (
    <span className={`text-[11px] font-semibold ${cor}`}>
      {emAdm ? "ADM" : "R&S"} · {f.status}
    </span>
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
                <td className="px-4 py-2.5"><StatusBadge vaga={v} /></td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-col">
                    <span className="text-xs text-gray-600 dark:text-gray-300">{(v.sla?.adm.inicio ? v.sla.adm.dias : v.dias_corridos) ?? "—"}/{(v.sla?.adm.inicio ? v.sla.adm.sla : v.sla?.rs.sla) ?? "—"} dias</span>
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
