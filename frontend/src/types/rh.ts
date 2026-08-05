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
};

export type LookupTipo =
  | "empresas" | "ufs" | "alocacoes" | "tipos-contrato" | "tipos-vaga"
  | "cargos" | "niveis" | "hierarquias" | "secoes" | "status"
  | "modalidades" | "analistas" | "requisitantes" | "etapas";

export const LOOKUP_TIPOS: LookupTipo[] = [
  "empresas", "ufs", "alocacoes", "tipos-contrato", "tipos-vaga",
  "cargos", "niveis", "hierarquias", "secoes", "status",
  "modalidades", "analistas", "requisitantes", "etapas",
];

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
  dias_corridos: number | null;
  sla_ok: boolean | null;
  created_at: string;
  updated_at: string;
};

export type VagasFiltros = {
  q?: string;
  status_id?: string[];
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
