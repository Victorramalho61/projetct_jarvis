export interface EmpresaBenner {
  handle: string;
  nome: string;
  codigo: string;
}

// Dashboard
export interface DashboardData {
  periodo: { inicio: string; fim: string };
  empresa: string;
  entradas: { total: number | null; qtd: number };
  saidas: { total: number | null; qtd: number };
  saldoPorConta: { banco: string; conta: string; saldo: number }[];
  topCentrosCusto: { centroCusto: string; total: number }[];
  impostosRetidos: { irrf: number | null; pis: number | null; cofins: number | null; iss: number | null };
}

// Conciliação
export interface Movimentacao {
  handle: number;
  data: string;
  documento: string;
  valor: number;
  natureza: "C" | "D";
  contabilizado: string;
  encontroContas: string | null;
  pessoaNome: string;
  conta: string;
  banco: string;
  historico: string;
  status: "conciliado" | "contabilizado" | "pendente";
}

export interface ResumoConta {
  conta: string;
  banco: string;
  totalCredito: number;
  totalDebito: number;
  saldo: number;
  totalLancamentos: number;
  conciliados: number;
}

export interface ConciliacaoData {
  movimentacoes: Movimentacao[];
  resumoPorConta: ResumoConta[];
}

// Receitas
export interface ResumoOperacao {
  operacao: string;
  total: number;
  qtd: number;
  pct: number;
}

export interface DetalheReceita {
  data: string;
  documento: string;
  valor: number;
  pessoaNome: string;
  historico: string;
  centroCusto: string;
}

export interface ReceitasData {
  resumoPorOperacao: ResumoOperacao[];
  detalhe: DetalheReceita[];
}

// Despesas
export interface ResumoCentroCusto {
  centroCusto: string;
  codigo: string;
  total: number;
  qtd: number;
  pct: number;
}

export interface DetalheDespesa {
  data: string;
  documento: string;
  valor: number;
  pessoaNome: string;
  historico: string;
  centroCusto: string;
  conta: string;
}

export interface DespesasData {
  resumoPorCC: ResumoCentroCusto[];
  detalhe: DetalheDespesa[];
}

// Balanço
export interface LinhaBalanco {
  estrutura: string;
  nome: string;
  tipo: string;
  debitos: number;
  creditos: number;
  saldo: number;
}

// Razão
export interface LinhaRazao {
  data: string;
  documento: string;
  valor: number;
  natureza: string;
  contabilizado: string;
  pessoaNome: string;
  cpfCnpj: string;
  historico: string;
  centroCusto: string;
  contaContabil: string;
  handle: number;
}

// Adiantamentos
export interface LinhaAdiantamento {
  data: string;
  documento: string;
  valor: number;
  pessoaNome: string;
  cpfCnpj: string;
  status: "baixado" | "pendente";
  historico: string;
}

// Impostos Retidos
export interface TotaisImpostos {
  irrf: number;
  pis: number;
  cofins: number;
  iss: number;
  csll: number;
  totalRetido: number;
}

export interface DetalheImposto {
  data: string;
  documento: string;
  pessoaNome: string;
  cpfCnpj: string;
  valorBruto: number;
  irrf: number;
  pis: number;
  cofins: number;
  iss: number;
  csll: number;
  totalRetencoes: number;
  statusBaixa: string;
}

export interface ImpostosRetidosData {
  totais: TotaisImpostos;
  detalhes: DetalheImposto[];
}

// Log Movimentações
export interface LinhaLog {
  data: string;
  handle: number;
  documento: string;
  valor: number;
  natureza: string;
  contabilizado: string;
  encontroContas: string | null;
  pessoaNome: string;
  operacao: string;
  centroCusto: string;
  contaContabil: string;
  dataInclusao: string;
  usuarioInclusao: string;
}
