import { useMemo, useState } from "react";
import type { SlaFase, SlaLinhaRelatorio } from "../../types/rh";
import { SLA_STATUS_BADGE, fmtData } from "../../lib/rhSla";

type Props = {
  linhas: SlaLinhaRelatorio[];
  loading: boolean;
  exportando: boolean;
  onExportar: () => void;
  onAbrirVaga: (id: string) => void;
};

type FiltroFase = "todas" | "rs_atrasadas" | "adm_atrasadas" | "etapa_estourada" | "abertas";

const FILTROS: { id: FiltroFase; label: string }[] = [
  { id: "abertas", label: "Abertas" },
  { id: "rs_atrasadas", label: "R&S atrasado" },
  { id: "adm_atrasadas", label: "Admissão atrasada" },
  { id: "etapa_estourada", label: "Etapa externa estourada" },
  { id: "todas", label: "Todas" },
];

function Badge({ status }: { status: string | null }) {
  if (!status || status === "NÃO INICIADA" || status === "SEM DADOS") {
    return <span className="text-[11px] text-gray-400">{status ? status.toLowerCase() : "—"}</span>;
  }
  return (
    <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold ${SLA_STATUS_BADGE[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function CelFase({ f }: { f: SlaFase }) {
  return (
    <div className="space-y-0.5">
      <Badge status={f.status} />
      {f.inicio && (
        <p className="text-[11px] tabular-nums text-gray-500 dark:text-gray-400 whitespace-nowrap">
          {f.dias ?? "—"}/{f.sla ?? "—"} dias · limite {fmtData(f.limite)}
          {f.estimado && <span title="Fim estimado pela data de admissão"> *</span>}
        </p>
      )}
    </div>
  );
}

export default function SlaRelatorioTable({ linhas, loading, exportando, onExportar, onAbrirVaga }: Props) {
  const [filtro, setFiltro] = useState<FiltroFase>("abertas");
  const [busca, setBusca] = useState("");

  const filtradas = useMemo(() => {
    let l = linhas;
    if (filtro === "rs_atrasadas") l = l.filter((x) => x.rs.status === "ATRASADO");
    if (filtro === "adm_atrasadas") l = l.filter((x) => x.adm.status === "ATRASADO");
    if (filtro === "etapa_estourada") l = l.filter((x) => x.etapa.status === "ATRASADO");
    if (filtro === "abertas") l = l.filter((x) => x.status === "ABERTA" || x.status === "REABERTO");
    const b = busca.trim().toLowerCase();
    if (b) {
      l = l.filter((x) =>
        [x.numero_requisicao, x.cargo, x.responsavel, x.empresa].some((v) => (v ?? "").toLowerCase().includes(b))
      );
    }
    return l;
  }, [linhas, filtro, busca]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {FILTROS.map((f) => (
          <button key={f.id} onClick={() => setFiltro(f.id)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${filtro === f.id
              ? "border-[#00694E] bg-[#00694E] text-white"
              : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"}`}>
            {f.label}
          </button>
        ))}
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar requisição, cargo, recrutador…"
          className="ml-auto w-full sm:w-64 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-xs text-gray-900 dark:text-gray-100" />
        <button onClick={onExportar} disabled={exportando}
          className="rounded-lg bg-[#00694E] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#004F3A] disabled:opacity-50">
          {exportando ? "Gerando…" : "Exportar Excel"}
        </button>
      </div>

      <div className="max-h-[520px] overflow-auto rounded-lg border border-gray-100 dark:border-gray-800">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-gray-50 dark:bg-gray-800 text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">Requisição</th>
              <th className="px-3 py-2">Cargo / Empresa</th>
              <th className="px-3 py-2">Recrutador</th>
              <th className="px-3 py-2">Etapa atual</th>
              <th className="px-3 py-2">R&S</th>
              <th className="px-3 py-2">Admissão</th>
              <th className="px-3 py-2">Etapa (externa)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filtradas.map((l) => (
              <tr key={l.id} onClick={() => onAbrirVaga(l.id)} className="cursor-pointer align-top hover:bg-gray-50 dark:hover:bg-gray-800/40">
                <td className="px-3 py-2 whitespace-nowrap font-medium text-gray-900 dark:text-gray-100">{l.numero_requisicao ?? "—"}</td>
                <td className="px-3 py-2">
                  <p className="text-gray-800 dark:text-gray-200">{l.cargo ?? "—"}</p>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400">{l.empresa ?? "—"}</p>
                </td>
                <td className="px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300">{l.responsavel ?? "—"}</td>
                <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">{l.etapa_atual ?? "—"}</td>
                <td className="px-3 py-2"><CelFase f={l.rs} /></td>
                <td className="px-3 py-2"><CelFase f={l.adm} /></td>
                <td className="px-3 py-2">
                  {l.etapa.externa ? (
                    <div className="space-y-0.5">
                      <Badge status={l.etapa.status} />
                      {l.etapa.inicio && (
                        <p className="text-[11px] tabular-nums text-gray-500 whitespace-nowrap">{l.etapa.dias ?? "—"}/{l.etapa.sla} dias</p>
                      )}
                    </div>
                  ) : <span className="text-[11px] text-gray-400">—</span>}
                </td>
              </tr>
            ))}
            {!loading && filtradas.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Nenhuma vaga para este filtro.</td></tr>
            )}
            {loading && (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Carregando…</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-gray-400">
        {filtradas.length} de {linhas.length} vagas · dias/SLA = dias corridos na fase / prazo da fase · * fim estimado (histórico)
      </p>
    </div>
  );
}
