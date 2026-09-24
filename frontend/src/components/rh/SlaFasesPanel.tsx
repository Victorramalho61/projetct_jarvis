import type { SlaFasesData, SlaResumoFase } from "../../types/rh";
import { FASE_LABEL, SLA_STATUS_COR, SLA_STATUS_ORDEM, type FaseSla } from "../../lib/rhSla";

type Props = {
  data: SlaFasesData | undefined;
  loading: boolean;
  onDrill: (fase: FaseSla, status: string[], titulo: string) => void;
};

const REGRA: Record<FaseSla, string> = {
  rs: "Data de abertura → fechamento do R&S · SLA pela tabela de cargos (10/15/20 dias)",
  adm: "Solicitação do link admissional → entrega da documentação · SLA link + exames + documentos",
};

function StatTile({
  label, valor, tom, onClick,
}: { label: string; valor: number; tom: "ok" | "ruim" | "okConcl" | "ruimConcl"; onClick: () => void }) {
  const cores = {
    ok: "border-blue-200 dark:border-blue-900/50 text-blue-700 dark:text-blue-300",
    ruim: "border-red-200 dark:border-red-900/50 text-red-700 dark:text-red-300",
    okConcl: "border-green-200 dark:border-green-900/50 text-green-700 dark:text-green-300",
    ruimConcl: "border-amber-200 dark:border-amber-900/50 text-amber-700 dark:text-amber-300",
  }[tom];
  return (
    <button
      onClick={onClick}
      disabled={valor === 0}
      className={`rounded-lg border bg-white dark:bg-gray-900 px-3 py-2 text-left transition hover:shadow-sm disabled:cursor-default disabled:opacity-60 ${cores}`}
    >
      <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{valor}</p>
    </button>
  );
}

function BarraStatus({ resumo, onDrill }: { resumo: SlaResumoFase; onDrill: (status: string) => void }) {
  const itens = SLA_STATUS_ORDEM
    .map((s) => ({ status: s as string, total: resumo.por_status[s] ?? 0 }))
    .filter((i) => i.total > 0 && i.status !== "NÃO INICIADA");
  const total = itens.reduce((s, i) => s + i.total, 0);
  if (!total) return <p className="text-xs text-gray-400">Sem vagas nesta fase para os filtros atuais.</p>;
  return (
    <div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full" role="img" aria-label="Distribuição por status de prazo">
        {itens.map((i) => (
          <button
            key={i.status}
            title={`${i.status}: ${i.total}`}
            onClick={() => onDrill(i.status)}
            className="h-3 first:rounded-l-full last:rounded-r-full hover:opacity-80"
            style={{ width: `${(100 * i.total) / total}%`, background: SLA_STATUS_COR[i.status] ?? "#94a3b8" }}
          />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-600 dark:text-gray-400">
        {itens.map((i) => (
          <li key={i.status}>
            <button onClick={() => onDrill(i.status)} className="flex items-center gap-1 hover:underline">
              <span className="h-2 w-2 rounded-full" style={{ background: SLA_STATUS_COR[i.status] ?? "#94a3b8" }} />
              {i.status.toLowerCase()} <span className="font-semibold tabular-nums text-gray-800 dark:text-gray-200">{i.total}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Fase({ fase, resumo, loading, onDrill }: { fase: FaseSla; resumo?: SlaResumoFase; loading: boolean; onDrill: Props["onDrill"] }) {
  const titulo = FASE_LABEL[fase];
  const pct = resumo?.pct_no_prazo;
  const pctCor = pct == null ? "text-gray-400" : pct >= 80 ? "text-green-600 dark:text-green-400" : pct >= 50 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400";
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">{titulo}</h3>
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{REGRA[fase]}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className={`text-3xl font-extrabold tabular-nums ${pctCor}`}>{loading ? "…" : pct != null ? `${pct}%` : "—"}</p>
          <p className="text-[11px] text-gray-500 dark:text-gray-400">no prazo · {resumo?.avaliadas ?? 0} vagas avaliadas</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
        <StatTile label="Abertas no prazo" valor={resumo?.em_andamento_no_prazo ?? 0} tom="ok"
          onClick={() => onDrill(fase, ["NO PRAZO"], `${titulo} — abertas no prazo`)} />
        <StatTile label="Abertas atrasadas" valor={resumo?.em_andamento_atrasadas ?? 0} tom="ruim"
          onClick={() => onDrill(fase, ["ATRASADO"], `${titulo} — atrasadas`)} />
        <StatTile label="Concluídas no prazo" valor={resumo?.concluidas_no_prazo ?? 0} tom="okConcl"
          onClick={() => onDrill(fase, ["CONCLUÍDA NO PRAZO"], `${titulo} — concluídas no prazo`)} />
        <StatTile label="Concluídas com atraso" valor={resumo?.concluidas_com_atraso ?? 0} tom="ruimConcl"
          onClick={() => onDrill(fase, ["CONCLUÍDA COM ATRASO"], `${titulo} — concluídas com atraso`)} />
      </div>

      <p className="mt-3 text-xs text-gray-600 dark:text-gray-300">
        Tempo médio das concluídas: <strong className="tabular-nums">{resumo?.media_dias_concluidas ?? "—"} dias</strong>
        {" "}· SLA médio: <strong className="tabular-nums">{resumo?.media_sla ?? "—"} dias</strong>
      </p>

      <div className="mt-3">
        {resumo && <BarraStatus resumo={resumo} onDrill={(s) => onDrill(fase, [s], `${titulo} — ${s.toLowerCase()}`)} />}
      </div>

      {!!resumo?.estimadas && (
        <p className="mt-2 text-[11px] text-gray-400">
          {resumo.estimadas} vaga(s) do histórico sem data de fechamento do R&S: fim estimado pela data de admissão e comparado ao SLA total.
        </p>
      )}
    </div>
  );
}

export default function SlaFasesPanel({ data, loading, onDrill }: Props) {
  return (
    <section className="rounded-2xl border-2 border-[#00694E]/40 bg-white dark:bg-gray-900 p-4 sm:p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#00694E] dark:text-emerald-400">Painel de SLA</p>
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Recrutamento & Seleção e Admissão</h2>
        </div>
        <p className="text-[11px] text-gray-500 dark:text-gray-400">Dias corridos · clique em um número para ver as vagas</p>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Fase fase="rs" resumo={data?.rs} loading={loading} onDrill={onDrill} />
        <Fase fase="adm" resumo={data?.adm} loading={loading} onDrill={onDrill} />
      </div>
    </section>
  );
}
