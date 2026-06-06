export type CartaoPerfil = "colaborador" | "supervisor";

export interface CartoesCliente {
  id: string;
  nome: string;
  cnpj?: string;
  ativo: boolean;
  created_at: string;
}

export interface CartaoItem {
  id: string;
  bandeira: string;
  numero_final: string;
  ativo: boolean;
  cards_clientes: { id: string; nome: string } | null;
}

export interface CartaoManagement extends CartaoItem {
  cliente_id: string;
  created_at: string;
}

export interface RevealRequest {
  localizador_os: string;
  nome_cliente: string;
  produto: "aereo" | "hotel" | "locacao";
  data_reserva: string;
  nome_pax: string;
  fornecedor: string;
  valor_transacao: number;
}

export interface RevealResponse {
  status: "revealed" | "pending_approval";
  numero?: string;
  cvv?: string;
  expiracao?: string;
  titular?: string;
  bandeira?: string;
  solicitacao_id?: string;
  message?: string;
}

export interface Solicitacao {
  id: string;
  cartao_id: string;
  cliente_id?: string;
  user_id: string;
  user_login: string;
  user_nome: string;
  localizador_os: string;
  nome_cliente: string;
  produto: string;
  data_reserva: string;
  nome_pax: string;
  fornecedor: string;
  valor_transacao: number;
  status: "pendente" | "aprovada" | "rejeitada" | "consumida";
  aprovado_por_nome?: string;
  aprovado_em?: string;
  aprovacao_expira_em?: string;
  motivo_rejeicao?: string;
  created_at: string;
  cards_cartoes?: {
    bandeira: string;
    numero_final: string;
    cards_clientes?: { nome: string };
  };
}

export interface SolicitacaoStatus {
  id: string;
  status: "pendente" | "aprovada" | "rejeitada" | "consumida";
  motivo_rejeicao?: string;
  aprovado_em?: string;
  aprovacao_expira_em?: string;
  aprovado_por_nome?: string;
}

export interface AcessoLog {
  id: string;
  cartao_id: string;
  cliente_id?: string;
  user_id: string;
  user_login: string;
  user_nome: string;
  data_hora_acesso: string;
  ip_origem?: string;
  localizador_os: string;
  nome_cliente: string;
  produto: string;
  data_reserva: string;
  nome_pax: string;
  fornecedor: string;
  valor_transacao: number;
  cards_cartoes?: {
    bandeira: string;
    numero_final: string;
    cards_clientes?: { nome: string };
  };
}

export interface AccessLogsResponse {
  data: AcessoLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface CartoesPermissao {
  id: string;
  user_id: string;
  user_login: string;
  user_nome: string;
  perfil: CartaoPerfil;
  ativo: boolean;
  created_at: string;
}
