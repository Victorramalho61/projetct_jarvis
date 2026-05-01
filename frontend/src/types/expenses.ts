export interface ExpenseKPIs {
  total_valor: number;
  total_efetivo: number;
  total_previsao: number;
  total_recorrente: number;
  total_pontual: number;
  count_parcelas: number;
  count_efetivo: number;
  count_previsao: number;
  media_mensal: number;
}

export interface ExpenseByMonth {
  month: string;
  valor: number;
}

export interface ExpenseByConta {
  conta: string;
  valor: number;
}

export interface ExpenseByOrigem {
  origem: string;
  valor: number;
}

export interface ExpenseByCategoria {
  categoria: string;
  valor: number;
}

export interface ExpenseRow {
  FILIAL: string;
  COD_PESSOA: string | null;
  CATEGORIA: string;
  PESSOA: string;
  DATA_EMISSAO: string | null;
  DATAVENCIMENTO: string | null;
  DATALIQUIDACAO: string | null;
  VALOR: number | null;
  VALOR_CONTA_FINANCEIRA: number | null;
  TIPO_DOC: string;
  STATUS_DOC: string;
  STATUS_PAR: string;
  ORIGEM: string;
  CONTA: string | null;
  CONTA_CONCATENADA: string | null;
  HISTORICO: string | null;
  DOCUMENTODIGITADO: string | null;
  GRUPO_ALCADA: string | null;
}

export interface ExpenseDashboard {
  kpis: ExpenseKPIs;
  by_month: ExpenseByMonth[];
  by_conta: ExpenseByConta[];
  by_origem: ExpenseByOrigem[];
  by_categoria: ExpenseByCategoria[];
  rows: ExpenseRow[];
}
