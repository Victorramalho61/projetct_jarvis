import type { SlaEtapaResumo } from "../../types/rh";

type Props = {
  etapas: SlaEtapaResumo[];
  onDrillEtapa: (etapa: string) => void;
};

/** Prazo por etapa do funil — vagas abertas paradas em cada etapa agora. */
export default function EtapasSlaChart({ etapas, onDrillEtapa }: Props) {
  const max = Math.max(1, ...etapas.map((e) => e.qtd_atual));
  const temHistorico = etapas.some((e) => e.amostras_historico > 0);
  const grupos: { fase: "RS" | "ADMISSAO"; titulo: string }[] = [
    { fase: "RS", titulo: "Recrutamento & Seleção" },
    { fase: "ADMISSAO", titulo: "Admissão" },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wider text-gray-500 dark:text-gray-400">
          <tr>
            <th className="px-3 py-2">Etapa</th>
            <th className="px-3 py-2">Vagas na etapa agora</th>
            <th className="px-3 py-2 text-right">Dias médios na etapa</th>
            <th className="px-3 py-2 text-right">SLA da etapa</th>
            <th className="px-3 py-2 text-right">Estouradas</th>
            {temHistorico && <th className="px-3 py-2 text-right">Média histórica</th>}
          </tr>
        </thead>
        {grupos.map((g) => (
          <tbody key={g.fase} className="divide-y divide-gray-100 dark:divide-gray-800">
            <tr>
              <td colSpan={temHistorico ? 6 : 5} className="bg-gray-50 dark:bg-gray-800/50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                {g.titulo}
              </td>
            </tr>
            {etapas.filter((e) => e.fase === g.fase).map((e) => (
              <tr key={e.etapa} className={e.qtd_atual ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40" : ""}
                onClick={() => e.qtd_atual && onDrillEtapa(e.etapa)}>
                <td className="px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  <span className="mr-2 tabular-nums text-gray-400">{e.ordem}.</span>{e.etapa}
                  {e.externa && (
                    <span className="ml-2 rounded bg-sky-100 dark:bg-sky-900/30 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700 dark:text-sky-300">externa</span>
                  )}
                </td>
                <td className="px-3 py-2 min-w-[180px]">
                  <div className="flex items-center gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                      {e.qtd_atual > 0 && (
                        <div className="h-2 rounded-full bg-[#00694E]" style={{ width: `${(100 * e.qtd_atual) / max}%` }} />
                      )}
                    </div>
                    <span className="w-6 text-right text-xs font-semibold tabular-nums text-gray-800 dark:text-gray-200">{e.qtd_atual}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-700 dark:text-gray-300">{e.dias_medio_atual ?? "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-500">{e.sla != null ? `${e.sla} dias` : "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {e.estouradas > 0 ? <span className="font-semibold text-red-600 dark:text-red-400">{e.estouradas}</span> : <span className="text-gray-400">0</span>}
                  {e.sem_data_inicio > 0 && (
                    <span className="ml-1 text-[10px] text-violet-600 dark:text-violet-300" title="Vagas sem data de início da etapa">
                      +{e.sem_data_inicio} s/ data
                    </span>
                  )}
                </td>
                {temHistorico && (
                  <td className="px-3 py-2 text-right tabular-nums text-gray-500">
                    {e.dias_medio_historico != null ? `${e.dias_medio_historico} d (${e.amostras_historico})` : "—"}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
      <p className="mt-2 text-[11px] text-gray-400">
        Etapas externas (Líder, DP, SESMT) têm prazo de 3 dias, limitado ao prazo da fase; etapas do RH seguem o SLA da fase.
        O tempo por etapa passa a ser registrado a cada mudança de etapa (no Jarvis ou no upload da planilha).
      </p>
    </div>
  );
}
