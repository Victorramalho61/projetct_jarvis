// Tipos e catálogo de campos do preenchimento inicial do Plano de Ação — compartilhado
// entre o formulário do gestor (pages/PublicActionPlanPage.tsx) e o do colaborador
// (components/actionPlan/ActionPlanForm.tsx, usado logo após a ciência da avaliação).

export interface IndicatorOption {
  indicator_id: string;
  name: string;
  description: string;
  original_score: number | null;
}

export interface ItemFields {
  situacao_observada: string;
  meta_esperada: string;
  acoes: string;
  responsavel_acompanhamento: string;
  como_sera_verificado: string;
}

export const EMPTY_ITEM: ItemFields = {
  situacao_observada: "", meta_esperada: "", acoes: "",
  responsavel_acompanhamento: "", como_sera_verificado: "",
};

export const FIELD_LABELS: { key: keyof ItemFields; label: string; placeholder: string }[] = [
  { key: "situacao_observada", label: "Situação observada", placeholder: "Descreva o que foi observado nessa competência..." },
  { key: "meta_esperada", label: "Meta esperada / Objetivo", placeholder: "Qual o resultado esperado ao final do acompanhamento?" },
  { key: "acoes", label: "Ações — O quê", placeholder: "Quais ações concretas serão tomadas?" },
  { key: "responsavel_acompanhamento", label: "Responsável pelo acompanhamento", placeholder: "Quem vai acompanhar essa ação?" },
  { key: "como_sera_verificado", label: "Como será verificado", placeholder: "Como o progresso será medido/verificado?" },
];

export const REQUIRED_ITEMS = 2;
