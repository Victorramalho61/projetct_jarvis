import type { AlertaSla, SlaLinhaRelatorio } from "../types/rh";

// Status de prazo (mesmos rótulos da planilha / rh-service/services/sla.py).
// Cores de status: sempre acompanhadas do rótulo por extenso — nunca cor sozinha.
export const SLA_STATUS_ORDEM = [
  "NO PRAZO",
  "ATRASADO",
  "CONCLUÍDA NO PRAZO",
  "CONCLUÍDA COM ATRASO",
  "CONGELADA (SLA PAUSADO)",
  "CANCELADA",
  "FALTA DATA DE FECHAMENTO DO R&S",
  "FALTA DATA DE INÍCIO DA ADMISSÃO",
  "DATAS INCONSISTENTES",
  "SEM DADOS",
  "NÃO INICIADA",
] as const;

export const SLA_STATUS_COR: Record<string, string> = {
  "NO PRAZO": "#3b82f6",
  "ATRASADO": "#ef4444",
  "CONCLUÍDA NO PRAZO": "#16a34a",
  "CONCLUÍDA COM ATRASO": "#f59e0b",
  "CONGELADA (SLA PAUSADO)": "#94a3b8",
  "CANCELADA": "#cbd5e1",
  "FALTA DATA DE FECHAMENTO DO R&S": "#a78bfa",
  "FALTA DATA DE INÍCIO DA ADMISSÃO": "#a78bfa",
  "DATAS INCONSISTENTES": "#f472b6",
  "SEM DADOS": "#e2e8f0",
  "NÃO INICIADA": "#e2e8f0",
};

export const SLA_STATUS_BADGE: Record<string, string> = {
  "NO PRAZO": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  "ATRASADO": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  "CONCLUÍDA NO PRAZO": "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  "CONCLUÍDA COM ATRASO": "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  "CONGELADA (SLA PAUSADO)": "bg-slate-200 text-slate-700 dark:bg-slate-700/40 dark:text-slate-300",
  "CANCELADA": "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
  "FALTA DATA DE FECHAMENTO DO R&S": "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  "FALTA DATA DE INÍCIO DA ADMISSÃO": "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  "DATAS INCONSISTENTES": "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300",
  "INFORMAR DATA DE INÍCIO": "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
};

export type FaseSla = "rs" | "adm";

export const FASE_LABEL: Record<FaseSla, string> = {
  rs: "Recrutamento & Seleção",
  adm: "Admissão",
};

/** Converte linha do relatório de SLA pro formato do DrillDownVagasModal (dias/SLA da fase). */
export function paraAlerta(l: SlaLinhaRelatorio, fase: FaseSla | "etapa"): AlertaSla {
  const f = fase === "etapa" ? l.etapa : l[fase];
  return {
    id: l.id,
    numero_requisicao: l.numero_requisicao,
    cargo: l.cargo,
    empresa: l.empresa,
    responsavel: l.responsavel,
    dias_corridos: f.dias,
    sla_alvo_dias: f.sla,
    etapa_atual: l.etapa_atual,
    status: f.status ?? l.status,
  };
}

export function fmtData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}
