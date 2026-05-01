// KPI with comparison dimensions
export interface KPIComparison {
  valor: number
  pct: number
  direcao: 'alta' | 'baixa' | 'estavel'
}

export interface KPIWithContext {
  valor: number
  sparkline: number[]         // up to 12 months, oldest first
  vs_mes_anterior?: KPIComparison
  vs_forecast?: KPIComparison  // vs statistical projection
  vs_ly?: KPIComparison        // only for year=2026
}

export interface DashboardKPIs {
  total_ytd: KPIWithContext
  contratos: KPIWithContext
  eventual: KPIWithContext
  media_mensal: KPIWithContext
  // legacy fields still returned by API
  total_valor: number
  total_efetivo: number
  total_previsao: number
  count_parcelas: number
  count_efetivo: number
  count_previsao: number
  media_mensal_valor: number
  total_recorrente: number
  total_eventual: number
}

export interface ExpenseByMonth { month: string; valor: number }
export interface ExpenseByOrigem { origem: string; valor: number }
export interface ExpenseByOrigemmMensal { mes: string; contrato: number; eventual: number }
export interface ExpenseByFilial { filial: string; valor: number }
export interface ExpenseByFornecedor { pessoa: string; valor: number; origem: string }

export interface ExpenseRow {
  FILIAL: string
  COD_PESSOA: string | null
  CATEGORIA: string
  PESSOA: string
  DATA_EMISSAO: string | null
  DATAVENCIMENTO: string | null
  DATALIQUIDACAO: string | null
  VALOR: number | null
  VALOR_CONTA_FINANCEIRA: number | null
  TIPO_DOC: string
  STATUS_DOC: string
  STATUS_PAR: string
  ORIGEM: string
  CONTA: string | null
  CONTA_CONCATENADA: string | null
  HISTORICO: string | null
  DOCUMENTODIGITADO: string | null
  GRUPO_ALCADA: string | null
}

export interface ExpenseDashboard {
  kpis: DashboardKPIs
  by_month: ExpenseByMonth[]
  by_origem: ExpenseByOrigem[]
  by_origem_mensal: ExpenseByOrigemmMensal[]
  by_filial: ExpenseByFilial[]
  by_fornecedor: ExpenseByFornecedor[]
  by_conta: { conta: string; valor: number }[]
  by_categoria: { categoria: string; valor: number }[]
  filiais: string[]
  yoy: Record<string, number>  // {month: valor_ly}
  rows: ExpenseRow[]
}

// Forecast types
export type ForecastTipo = 'real' | 'projecao'
export interface ForecastMes {
  mes: string
  valor: number
  tipo: ForecastTipo
  valor_min?: number
  valor_max?: number
}

export interface ForecastFornecedor {
  pessoa: string
  valor_executado: number
  media_mensal: number
  meses_restantes: number
  valor_projetado_restante: number
  total_estimado_ano: number
  tendencia: 'alta' | 'baixa' | 'estavel'
}

export interface ForecastDashboard {
  meses: ForecastMes[]
  total_2025: number
  total_2026_real: number
  total_2026_projecao: number
  total_2026_estimado: number
  modelo: string
  by_fornecedor: ForecastFornecedor[]
}
