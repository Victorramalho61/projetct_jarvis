export type LookupItem = {
  id: string;
  nome?: string;
  sigla?: string;
  ordem?: number;
  em_aberto?: boolean;
  concluido?: boolean;
  prefixo_requisicao?: string;
  nivel_padrao_id?: string;
  secao_responsavel_id?: string;
  vale_transporte?: number;
  vale_alimentacao?: number;
  seguro_vida?: number;
  plano_saude?: number;
  uniforme?: number;
  cracha_cordao?: number;
  aso?: number;
  insalubridade?: number;
  periculosidade?: number;
  aparelhos_eletronicos?: number;
  outros_creditos?: number;
  taxa_administrativa?: number;
  pct_inss?: number;
  pct_fgts?: number;
  pct_multa_fgts?: number;
};

export type LookupTipo =
  | "empresas" | "ufs" | "alocacoes" | "tipos-contrato" | "tipos-vaga"
  | "cargos" | "niveis" | "hierarquias" | "secoes" | "status"
  | "modalidades" | "analistas" | "requisitantes" | "etapas" | "perfis-calculo";

export const LOOKUP_TIPOS: LookupTipo[] = [
  "empresas", "ufs", "alocacoes", "tipos-contrato", "tipos-vaga",
  "cargos", "niveis", "hierarquias", "secoes", "status",
  "modalidades", "analistas", "requisitantes", "etapas", "perfis-calculo",
];

export type PerfilCalculo = LookupItem;

export type CalculoDetalhado = {
  salario: number;
  vale_transporte: number;
  vale_alimentacao: number;
  provisao_13_ferias: number;
  ferias: number;
  inss: number;
  fgts: number;
  fgts_multa: number;
  inss_13_ferias: number;
  seguro_vida: number;
  plano_saude: number;
  uniforme: number;
  cracha_cordao: number;
  aso: number;
  taxa_administrativa: number;
  insalubridade_informativo: number;
  periculosidade_informativo: number;
  aparelhos_eletronicos_informativo: number;
  outros_creditos_informativo: number;
  custo_total: number;
};

export type Vaga = {
  id: string;
  numero_requisicao: string | null;
  empresa_id: string | null;
  empresa: string | null;
  uf: string | null;
  alocacao_id: string | null;
  alocacao: string | null;
  tipo_contrato_id: string | null;
  tipo_contrato: string | null;
  data_recebimento: string | null;
  data_aprovacao_diretoria: string | null;
  tipo_vaga_id: string | null;
  tipo_vaga: string | null;
  cargo_id: string | null;
  cargo: string | null;
  nivel_id: string | null;
  nivel: string | null;
  hierarquia_id: string | null;
  hierarquia: string | null;
  requisitante_id: string | null;
  requisitante: string | null;
  status_id: string | null;
  status: string | null;
  status_em_aberto: boolean | null;
  status_concluido: boolean | null;
  etapa_atual_id: string | null;
  etapa_atual: string | null;
  secao_id: string | null;
  secao: string | null;
  responsavel_id: string | null;
  responsavel: string | null;
  sla_alvo_dias: number | null;
  justificativa: string | null;
  data_admissao: string | null;
  candidato: string | null;
  centro_custo: string | null;
  carga_horaria: string | null;
  carga_horaria_outros: string | null;
  horario_trabalho: string | null;
  modalidade_id: string | null;
  modalidade: string | null;
  salario: number | null;
  perfil_calculo_id: string | null;
  perfil_calculo: string | null;
  custo_total: number | null;
  calculo_detalhado: CalculoDetalhado | null;
  dias_corridos: number | null;
  sla_ok: boolean | null;
  created_at: string;
  updated_at: string;
};

export type VagasFiltros = {
  q?: string;
  status_id?: string[];
  ano?: number[];
  data_inicio?: string;
  data_fim?: string;
  empresa_id?: string;
  tipo_vaga_id?: string;
  tipo_contrato_id?: string;
  nivel_id?: string;
  hierarquia_id?: string;
  etapa_atual_id?: string;
  secao_id?: string;
  responsavel_id?: string;
  requisitante_id?: string;
  cargo_id?: string;
  modalidade_id?: string;
};

export type VagasPage = {
  total: number;
  page: number;
  page_size: number;
  items: Vaga[];
};

export type DashboardKPIs = {
  total: number;
  abertas: number;
  concluidas_periodo: number;
  sla_medio_dias: number | null;
  pct_no_prazo: number | null;
  atrasadas: number;
  canceladas: number;
  congeladas: number;
};

export type DashboardData = {
  kpis: DashboardKPIs;
  por_status: { status: string; total: number }[];
  por_empresa: { empresa: string; total: number }[];
  top_cargos: { cargo: string; total: number }[];
  tendencia_mensal: { mes: string; abertas: number; concluidas: number }[];
  funil_etapas: { etapa: string; ordem: number; total: number }[];
  por_analista: {
    analista: string; total: number; abertas: number;
    concluidas: number; canceladas: number; congeladas: number;
  }[];
  sla_estourado: AlertaSla[];
  sla_estourando: AlertaSla[];
};

export type AlertaSla = {
  id: string;
  numero_requisicao: string | null;
  cargo: string | null;
  empresa: string | null;
  responsavel: string | null;
  dias_corridos: number | null;
  sla_alvo_dias: number | null;
  etapa_atual: string | null;
};

export type UploadInfo = {
  id: string;
  arquivo_nome: string;
  usuario_nome: string;
  criado_em: string;
  linhas_processadas: number;
  linhas_inseridas: number;
  linhas_atualizadas: number;
  linhas_com_erro: number;
  detalhes: { linha: number | null; motivo: string }[];
};

export type ImportResultado = {
  upload_id: string | null;
  linhas_processadas: number;
  linhas_inseridas: number;
  linhas_atualizadas: number;
  linhas_com_erro: number;
  erros: { linha: number | null; motivo: string }[];
};

// ── Fase 2 — assinatura eletrônica via D4Sign ────────────────────────────

export type PapelSignatario = "solicitante" | "rh" | "depto_pessoal" | "diretoria";

export const PAPEIS_SIGNATARIO: { papel: PapelSignatario; label: string }[] = [
  { papel: "solicitante", label: "Solicitante" },
  { papel: "rh", label: "Recursos Humanos" },
  { papel: "depto_pessoal", label: "Departamento Pessoal" },
  { papel: "diretoria", label: "Diretoria" },
];

export type SignatarioForm = {
  papel: PapelSignatario;
  nome: string;
  email: string;
  cargo: string;
};

export type SignatarioRegistro = SignatarioForm & {
  status: "pendente" | "assinado";
  assinado_em?: string;
};

export type StatusAssinatura = "PRE_ENVIO" | "ENVIADO" | "PARCIAL" | "EM_ALTERACAO" | "CONCLUIDO";

export type AssinaturaRegistro = {
  id?: string;
  vaga_id?: string;
  status: StatusAssinatura;
  signatarios: SignatarioRegistro[];
  aditivo_de_id?: string | null;
  tipo_aditivo?: "CANCELAMENTO" | "ALTERACAO" | null;
  justificativa_aditivo?: string | null;
  documento_assinado?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AssinaturaStatusResponse = {
  configurado: boolean;
  atual: AssinaturaRegistro;
  aditivos: AssinaturaRegistro[];
};
