// Módulo Governança de Contratos

export type ContractModalidade = 'servico' | 'fornecimento' | 'manutencao' | 'licenca' | 'outro'
export type ContractStatus = 'vigente' | 'vencendo' | 'vencido' | 'rescindido' | 'suspenso'
export type OccurrenceTipo = 'glosa' | 'multa' | 'desconto' | 'acrescimo' | 'reajuste' | 'notificacao'
export type OccurrenceStatus = 'pendente' | 'aplicado' | 'contestado' | 'cancelado'
export type SLAViolationStatus = 'registrado' | 'notificado' | 'aplicado' | 'contestado' | 'resolvido'
export type DivergenceTipo = 'a_maior' | 'a_menor' | 'ok' | 'nao_pago' | 'extra'

export interface SLADefinition {
  metrica: string
  valor_contratado: number
  unidade: string
  penalidade_pct: number
}

export interface Contract {
  id: string
  benner_documento_match?: string
  numero?: string
  titulo: string
  fornecedor_nome: string
  fornecedor_benner_handle?: number
  valor_total: number
  valor_mensal?: number
  qtd_parcelas?: number
  data_inicio: string
  data_fim: string
  modalidade: ContractModalidade
  status: ContractStatus
  objeto?: string
  sla_config: SLADefinition[]
  observacoes?: string
  arquivo_url?: string
  created_at: string
  updated_at?: string
  // Computed by backend
  dias_para_vencer?: number
  total_pago_benner?: number
  divergencia_valor?: number
  ocorrencias_pendentes?: number
  // Joined on detail endpoint
  contract_items?: ContractItem[]
  contract_occurrences?: ContractOccurrence[]
  contract_sla_violations?: SLAViolation[]
  benner_payments?: ContractPayment[]
}

export interface ContractItem {
  id: string
  contract_id: string
  descricao: string
  quantidade: number
  valor_unitario: number
  valor_total: number
  unidade: string
  periodicidade: 'mensal' | 'anual' | 'unico'
  conta_contabil?: string
  created_at: string
}

export interface ContractPayment {
  ap: number
  mes: string
  datavencimento: string
  dataliquidacao?: string
  valor: number
  status_par: 'pago' | 'pendente'
  historico?: string
  filial: string
}

export interface ContractDivergence {
  mes: string
  previsto: number
  pago: number
  delta: number
  tipo: DivergenceTipo
}

export interface DivergenceResult {
  status: 'ok' | 'divergente' | 'not_found' | 'sem_datas'
  total_previsto: number
  total_pago: number
  delta_total: number
  divergencias: ContractDivergence[]
}

export interface ContractOccurrence {
  id: string
  contract_id: string
  tipo: OccurrenceTipo
  valor?: number
  descricao: string
  data_ocorrencia: string
  competencia?: string
  status: OccurrenceStatus
  email_enviado: boolean
  email_destinatarios?: string[]
  email_assunto?: string
  email_corpo?: string
  email_enviado_at?: string
  created_at: string
  updated_at?: string
}

export interface SLAViolation {
  id: string
  contract_id: string
  sla_metrica: string
  valor_contratado: number
  valor_medido: number
  periodo: string
  impacto?: string
  penalidade_valor?: number
  status: SLAViolationStatus
  created_at: string
}

export interface GovernanceDashboard {
  total_contratos: number
  contratos_vigentes: number
  vencendo_30d: number
  vencendo_60d: number
  vencendo_90d: number
  ocorrencias_pendentes: number
  valor_glosas_pendentes: number
  sla_violations_abertas: number
  valor_total_contratos: number
  contracts: Contract[]
  last_updated?: string
}

// For Benner discovery
export interface BennerContract {
  benner_handle: number
  num_contrato?: string
  fornecedor_handle?: number
  fornecedor: string
  primeira_parcela?: string
  ultima_parcela?: string
  qtd_parcelas: number
  total_valor: number
  ultima_liquidacao?: string
}
