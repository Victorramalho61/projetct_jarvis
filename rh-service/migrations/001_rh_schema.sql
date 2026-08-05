-- rh-service -- Gestao de Recursos Humanos / Vagas
-- Execute via Supabase SQL Editor

CREATE TABLE IF NOT EXISTS rh_empresas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    prefixo_requisicao text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_ufs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sigla text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_alocacoes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_tipos_contrato (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_tipos_vaga (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_niveis (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_hierarquias (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_secoes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_modalidades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_analistas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_requisitantes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_status_vaga (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    em_aberto boolean NOT NULL DEFAULT false,
    concluido boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_cargos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    nivel_padrao_id uuid REFERENCES rh_niveis(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rh_vagas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_requisicao text UNIQUE,
    empresa_id uuid REFERENCES rh_empresas(id),
    uf text,
    alocacao_id uuid REFERENCES rh_alocacoes(id),
    tipo_contrato_id uuid REFERENCES rh_tipos_contrato(id),
    data_recebimento date NOT NULL DEFAULT current_date,
    data_aprovacao_diretoria date,
    tipo_vaga_id uuid REFERENCES rh_tipos_vaga(id),
    cargo_id uuid REFERENCES rh_cargos(id),
    nivel_id uuid REFERENCES rh_niveis(id),
    hierarquia_id uuid REFERENCES rh_hierarquias(id),
    requisitante_id uuid REFERENCES rh_requisitantes(id),
    status_id uuid REFERENCES rh_status_vaga(id),
    etapa_atual_id uuid,
    secao_id uuid REFERENCES rh_secoes(id),
    responsavel_id uuid REFERENCES rh_analistas(id),
    sla_alvo_dias int,
    justificativa text,
    data_admissao date,
    candidato text,
    centro_custo text,
    carga_horaria text,
    carga_horaria_outros text,
    horario_trabalho text,
    modalidade_id uuid REFERENCES rh_modalidades(id),
    salario numeric(12,2),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES profiles(id),
    updated_by uuid REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS rh_uploads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arquivo_nome text NOT NULL,
    usuario_id uuid REFERENCES profiles(id),
    usuario_nome text NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT now(),
    linhas_processadas int NOT NULL DEFAULT 0,
    linhas_inseridas int NOT NULL DEFAULT 0,
    linhas_atualizadas int NOT NULL DEFAULT 0,
    linhas_com_erro int NOT NULL DEFAULT 0,
    detalhes jsonb
);

-- Seeds -- valores oficiais extraidos da aba LISTA da planilha real

INSERT INTO rh_empresas (nome, prefixo_requisicao) VALUES
    ('VOETUR TURISMO', 'TUR'),
    ('VTCLOG', 'VTC'),
    ('VIP MARINA', 'MAR'),
    ('VIP LOCADORA', 'LOC'),
    ('VIP CARGAS', 'CAR'),
    ('CLUBE DE LAZER', 'CDL'),
    ('VOETUR OPERADORA', 'OPE'),
    ('VOETUR EVENTOS', 'EVE'),
    ('VIP AVIATION', 'AVI'),
    ('PAYFLY', 'PAY')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_ufs (sigla) VALUES
    ('DF'),
    ('SP'),
    ('RJ'),
    ('MG'),
    ('PR'),
    ('PE')
ON CONFLICT (sigla) DO NOTHING;

INSERT INTO rh_alocacoes (nome) VALUES
    ('AEROPORTO'),
    ('BRASIL 21'),
    ('BRASILIA SHOPPING'),
    ('CEMIG - BELO HORIZONTE'),
    ('CENTRAL ATENDIMENTO RIO'),
    ('DIRETORES'),
    ('FIEP - CURITIBA'),
    ('GALEAO'),
    ('HOME OFFICE'),
    ('LIBERTY MALL'),
    ('LOCADORA - AEROPORTO'),
    ('LOJA TECA'),
    ('OPERAÇÕES - FILIAL SP'),
    ('POSTO CAIXA'),
    ('SIA'),
    ('TURISMO - RJ'),
    ('TURISMO RJ - BNDES'),
    ('TURISMO RJ- FIOTEC'),
    ('TURISMO PR- FIEP'),
    ('TURISMO PR-FIEP'),
    ('TURISMO SP'),
    ('VIP CARGAS BSB'),
    ('VIP CARGAS RJ'),
    ('VIP CARGAS RIO'),
    ('VIP MARINA'),
    ('VTC - GRU - MEDICAMENTOS'),
    ('VTC - RECIFE')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_tipos_contrato (nome) VALUES
    ('CLT'),
    ('PJ'),
    ('ESTÁGIO'),
    ('APRENDIZAGEM')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_tipos_vaga (nome) VALUES
    ('AUMENTO DE QUADRO'),
    ('COTA DE JOVEM APRENDIZ/PCD'),
    ('SUBSTITUIÇÃO'),
    ('NOVA POSIÇÃO')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_niveis (nome) VALUES
    ('OPERACIONAL'),
    ('TÁTICO'),
    ('ESTRATÉGICO')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_hierarquias (nome) VALUES
    ('ADM. OPERACIONAL'),
    ('ADMINISTRATIVO BLACK'),
    ('ADMINISTRATIVO - MARINA'),
    ('ADMINISTRATIVO - VIP CARGAS BSB'),
    ('ARQUIVO'),
    ('ATENDIMENTO'),
    ('ATENDIMENTO BRASIL'),
    ('AUDITORIA LEI KANDIR'),
    ('BANCO DO BRASIL'),
    ('BNDES'),
    ('CADASTRO'),
    ('CEMIG'),
    ('CENTRAL DE LICITAÇÕES'),
    ('CENTRAL DE ATENDIMENTO PETROBRAS'),
    ('CENTRAL DE ATENDIMENTO PETROBRAS_BSB'),
    ('CENTRAL DE ATENDIMENTO RIO'),
    ('CENTRAL UNIFICADA'),
    ('COBRANÇA'),
    ('COMERCIAL'),
    ('COMERCIAL GERAL'),
    ('COMERCIAL - TURISMO SP'),
    ('COMERCIAL - VIP CARGAS RIO'),
    ('COMPLIANCE'),
    ('CONCILIAÇÃO AÉREA'),
    ('CONCILIAÇÃO TERRESTRE'),
    ('CONTABILIDADE'),
    ('CONTROLADORIA'),
    ('DEPARTAMENTO PESSOAL'),
    ('DIRETORIA'),
    ('FACILITIES'),
    ('FATURAMENTO'),
    ('FATURAMENTO ATAS'),
    ('FATURAMENTO DEMAIS CONTRATOS PÚBLICOS'),
    ('FIEP - CURITIBA'),
    ('GARANTIA DA QUALIDADE'),
    ('GERENCIAMENTO DE RISCO E MONITORAMENTO'),
    ('GESTÃO DE FROTA BRASÍLIA'),
    ('JURÍDICO'),
    ('MANUTENÇÃO'),
    ('MARKETING'),
    ('MRE'),
    ('OPERACIONAL'),
    ('OPERACIONAL TERRESTRE'),
    ('OPERAÇÃO AÉREO BRASÍLIA'),
    ('OPERAÇÃO TERRESTRE BRASÍLIA'),
    ('OPERACIONAL - VIP CARGAS BRASÍLIA'),
    ('OPERACIONAL - VIP CARGAS RIO'),
    ('OPERACIONAL - VIP CARGAS SP'),
    ('OPERACIONAL VIP TÁXI - SAC'),
    ('OPERADORA'),
    ('OPERAÇÕES - FILIAL SP'),
    ('PLANTÃO'),
    ('POSTO CAIXA'),
    ('POSTO - CAIXA ECONÔMICA (BRASÍLIA)'),
    ('PRODUTOS'),
    ('PRODUTOS TERRESTRES'),
    ('RECEPÇÃO'),
    ('RECURSOS HUMANOS'),
    ('REEMBOLSO'),
    ('REGULATÓRIO BRASÍLIA'),
    ('SECRETARIA'),
    ('SEGURANÇA DO TRABALHO'),
    ('SESMT'),
    ('SERVIÇOS GERAIS'),
    ('SGI (SISTEMA DE GESTÃO INTEGRADA)'),
    ('SISTEMAS'),
    ('SUPRIMENTOS'),
    ('T.I SISTEMAS'),
    ('TERRESTRE'),
    ('TRANSPETRO'),
    ('VIP - MARINA'),
    ('VTC LOG')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_secoes (nome) VALUES
    ('RH'),
    ('RH/DP'),
    ('DP'),
    ('SESMT'),
    ('RH/DP/AREAS AFINS')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_modalidades (nome) VALUES
    ('HORISTA'),
    ('INTERMITENTE'),
    ('DETERMINADO'),
    ('INDETERMINADO')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO rh_status_vaga (nome, em_aberto, concluido) VALUES
    ('EM ANDAMENTO', true, false),
    ('REABERTO', true, false),
    ('CONCLUÍDO', false, true),
    ('CANCELADO', false, false),
    ('CONGELADO', false, false)
ON CONFLICT (nome) DO NOTHING;

-- Cargos com nivel padrao (autopreenche o nivel ao selecionar o cargo)
INSERT INTO rh_cargos (nome, nivel_padrao_id)
SELECT v.nome, rn.id
FROM (VALUES
    ('ADVOGADO', 'ESTRATÉGICO'),
    ('AJUDANTE DE CARGAS', 'OPERACIONAL'),
    ('ANALISTA', 'OPERACIONAL'),
    ('ANALISTA ADMINISTRATIVO', 'OPERACIONAL'),
    ('ANALISTA ADMINISTRATIVO SENIOR', 'OPERACIONAL'),
    ('ANALISTA COMERCIAL JUNIOR', 'OPERACIONAL'),
    ('ANALISTA COMERCIAL PLENO', 'OPERACIONAL'),
    ('ANALISTA COMERCIAL SENIOR', 'OPERACIONAL'),
    ('ANALISTA CONTÁBIL', 'OPERACIONAL'),
    ('ANALISTA CONTÁBIL JUNIOR', 'OPERACIONAL'),
    ('ANALISTA CONTÁBIL PLENO', 'OPERACIONAL'),
    ('ANALISTA CONTÁBIL SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE ASSUNTOS REGULATÓRIOS JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE CADASTRO JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE COBRANÇA', 'OPERACIONAL'),
    ('ANALISTA DE COBRANÇA JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE COMPLIANCE PLENO', 'OPERACIONAL'),
    ('ANALISTA DE CONCILIAÇÃO JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE CONTROLADORIA JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE DEPARTAMENTO PESSOAL', 'OPERACIONAL'),
    ('ANALISTA DE DEPARTAMENTO PESSOAL JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE DEPARTAMENTO PESSOAL PLENO', 'OPERACIONAL'),
    ('ANALISTA DE DEPARTAMENTO PESSOAL SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE DESENVOLVIMENTO DE NEGÓCIOS SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE DOCUMENTAÇÃO E PROJETOS DE TI PLENO', 'OPERACIONAL'),
    ('ANALISTA DE ENDOMARKETING JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE ENDOMARKETING PLENO', 'OPERACIONAL'),
    ('ANALISTA DE FATURAMENTO', 'OPERACIONAL'),
    ('ANALISTA DE FATURAMENTO JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE FATURAMENTO SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE FROTA JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE FROTA SÊNIOR', 'OPERACIONAL'),
    ('ANALISTA DE INFORMAÇÕES GERENCIAIS PLENO', 'OPERACIONAL'),
    ('ANALISTA DE LICITAÇÃO', 'OPERACIONAL'),
    ('ANALISTA DE MARKETING', 'OPERACIONAL'),
    ('ANALISTA DE MARKETING PLENO', 'OPERACIONAL'),
    ('ANALISTA DE MARKETING SÊNIOR', 'OPERACIONAL'),
    ('ANALSITA DE NEGÓCIOS', 'OPERACIONAL'),
    ('ANALISTA DE NEGOCIOS PLENO', 'OPERACIONAL'),
    ('ANALISTA DE PATRIMÔNIO PLENO', 'OPERACIONAL'),
    ('ANALISTA DE PRODUTOS', 'OPERACIONAL'),
    ('ANALISTA DE PROTEÇÃO DE DADOS (LGPD)', 'OPERACIONAL'),
    ('ANALISTA DE QUALIDADE PLENO', 'OPERACIONAL'),
    ('ANALISTA DE RECURSOS HUMANOS JR', 'OPERACIONAL'),
    ('ANALISTA DE RECURSOS HUMANOS PLENO', 'OPERACIONAL'),
    ('ANALISTA DE RECURSOS HUMANOS SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE REDE', 'OPERACIONAL'),
    ('ANALISTA DE SGI JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE SGI PLENO', 'OPERACIONAL'),
    ('ANALISTA DE SGI SÊNIOR', 'OPERACIONAL'),
    ('ANALISTA DE SISTEMAS E CADASTROS SÊNIOR', 'OPERACIONAL'),
    ('ANALISTA DE SISTEMAS JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE SISTEMAS PLENO', 'OPERACIONAL'),
    ('ANALISTA DE SISTEMAS SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE SUPRIMENTOS', 'OPERACIONAL'),
    ('ANALISTA DE SUPRIMENTOS JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE SUPRIMENTOS PLENO', 'OPERACIONAL'),
    ('ANALISTA DE SUPRIMENTOS SENIOR', 'OPERACIONAL'),
    ('ANALISTA DE VIAGEM', 'OPERACIONAL'),
    ('ANALISTA DE VIAGENS JUNIOR', 'OPERACIONAL'),
    ('ANALISTA DE VIAGENS SENIOR', 'OPERACIONAL'),
    ('ANALISTA FINANCEIRO', 'OPERACIONAL'),
    ('ANALISTA FINANCEIRO JUNIOR', 'OPERACIONAL'),
    ('ANALISTA FINANCEIRO PLENO', 'OPERACIONAL'),
    ('ANALISTA FISCAL PLENO', 'OPERACIONAL'),
    ('ANALISTA FISCAL SENIOR', 'OPERACIONAL'),
    ('ARQUIVISTA DE DOCUMENTOS', 'OPERACIONAL'),
    ('ASSISTENTE ADMINISTRATIVO', 'OPERACIONAL'),
    ('ASSISTENTE ADMINISTRATIVO I', 'OPERACIONAL'),
    ('ASSISTENTE COMERCIAL', 'OPERACIONAL'),
    ('ASSISTENTE DE CONCILIAÇÃO', 'OPERACIONAL'),
    ('ASSISTENTE DE CONCILIAÇÃO SENIOR', 'OPERACIONAL'),
    ('ASSISTENTE DE DEPARTAMENTO PESSOAL', 'OPERACIONAL'),
    ('ASSISTENTE DE FATURAMENTO', 'OPERACIONAL'),
    ('ASSISTENTE DE RH SÊNIOR', 'OPERACIONAL'),
    ('ASSISTENTE DE SGI', 'OPERACIONAL'),
    ('ASSISTENTE DE TÉCNICO DE SEGURANÇA DO TRABALHO', 'OPERACIONAL'),
    ('ASSISTENTE DE CONTROLADORIA', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO I', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO II', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO JUNIOR', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO PLENO', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO PLENO (PCD)', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO SENIOR', 'OPERACIONAL'),
    ('AUXILIAR ADMINISTRATIVO (APRENDIZ)', 'OPERACIONAL'),
    ('AUXILIAR DE COBRANCA III', 'OPERACIONAL'),
    ('AUXILIAR DE CONCILIAÇÃO', 'OPERACIONAL'),
    ('AUXILIAR DE CONCILIACAO JUNIOR', 'OPERACIONAL'),
    ('AUXILIAR DE LICITAÇÃO', 'OPERACIONAL'),
    ('AUXILIAR DE LICITAÇÃO JUNIOR', 'OPERACIONAL'),
    ('AUXILIAR DE MANUTENÇÃO', 'OPERACIONAL'),
    ('AUXILIAR DE MARINHEIRO', 'OPERACIONAL'),
    ('AUXILIAR DE SEGURANÇA DO TRABALHO', 'OPERACIONAL'),
    ('AUXILIAR DE SERVICOS GERAIS', 'OPERACIONAL'),
    ('AUXILIAR FISCAL', 'OPERACIONAL'),
    ('AUXILIAR SISTEMA DE GESTÃO INTEGRADO', 'OPERACIONAL'),
    ('BOMBEIRO CIVIL (BRIGADISTA)', 'OPERACIONAL'),
    ('CIENTISTA DE DADOS PLENO', 'OPERACIONAL'),
    ('CONFIDENCIAL', 'OPERACIONAL'),
    ('CONSULTOR (A) DE VIAGEM', 'OPERACIONAL'),
    ('CONSULTOR (A) DE VIAGEM JUNIOR', 'OPERACIONAL'),
    ('CONSULTOR (A) DE VIAGEM PLENO', 'OPERACIONAL'),
    ('CONSULTOR (A) DE VIAGEM SENIOR', 'OPERACIONAL'),
    ('CONSULTOR DE ATENDIMENTO PLENO', 'OPERACIONAL'),
    ('CONSULTOR DE BUSINESS INTELLIGENCE SENIOR', 'OPERACIONAL'),
    ('CONSULTOR DE DADOS SENIOR', 'OPERACIONAL'),
    ('CONSULTOR DE EVENTOS JUNIOR', 'OPERACIONAL'),
    ('CONSULTOR DE SISTEMAS', 'OPERACIONAL'),
    ('COORDENADOR (A) DE ATENDIMENTO PLENO', 'TÁTICO'),
    ('COORDENADOR COMERCIAL', 'TÁTICO'),
    ('COORDENADOR DE ATENDIMENTO JR', 'TÁTICO'),
    ('COORDENADOR DE ATENDIMENTO SÊNIOR', 'TÁTICO'),
    ('COORDENADOR DE ATENDIMENTO BILÍNGUE SÊNIOR', 'TÁTICO'),
    ('COORDENADOR DE MARKETING', 'TÁTICO'),
    ('COORDENADOR DE PRODUTOS', 'TÁTICO'),
    ('COORDENADOR DE RECEITA', 'TÁTICO'),
    ('COORDENADOR DE RH', 'TÁTICO'),
    ('COORDENADOR DE SESMT', 'TÁTICO'),
    ('COORDENADOR DE SUPRIMENTOS', 'TÁTICO'),
    ('COORDENADOR DE PROJETOS', 'TÁTICO'),
    ('DESIGNER', 'OPERACIONAL'),
    ('DESIGNER GRÁFICO', 'OPERACIONAL'),
    ('DESIGNER PLENO', 'OPERACIONAL'),
    ('DESENVOLVEDOR DE SISTEMAS SENIOR', 'OPERACIONAL'),
    ('DESENVOLVEDOR DE SOFTWARE', 'OPERACIONAL'),
    ('DIRETOR DE PRODUTOS', 'ESTRATÉGICO'),
    ('EMISSOR', 'OPERACIONAL'),
    ('EMISSOR I', 'OPERACIONAL'),
    ('EMISSOR INTERNACIONAL', 'OPERACIONAL'),
    ('ENFERMEIRA DE SEGURANÇA DO TRABALHO', 'OPERACIONAL'),
    ('ENGENHEIRO DE PRODUÇÃO', 'OPERACIONAL'),
    ('ESPECIALISTA DE IMPLANTAÇÃO', 'OPERACIONAL'),
    ('ESTAGIARIO (A)', 'OPERACIONAL'),
    ('ESTAGIÁRIO DE TI', 'OPERACIONAL'),
    ('EXECUTIVO DE CONTAS', 'OPERACIONAL'),
    ('EXECUTIVO DE RELACIONAMENTO JUNIOR', 'OPERACIONAL'),
    ('FARMACÊUTICO(A)', 'OPERACIONAL'),
    ('FATURISTA', 'OPERACIONAL'),
    ('FATURISTA JUNIOR', 'OPERACIONAL'),
    ('GERENTE COMERCIAL', 'ESTRATÉGICO'),
    ('GERENTE DE CONTAS', 'ESTRATÉGICO'),
    ('GERENTE DE IMPLANTAÇÃO', 'ESTRATÉGICO'),
    ('GERENTE DE PROJETOS JUNIOR', 'ESTRATÉGICO'),
    ('GERENTE DE SUPRIMENTOS', 'ESTRATÉGICO'),
    ('LÍDER DE FACILITIES', 'OPERACIONAL'),
    ('MARINHEIRO', 'OPERACIONAL'),
    ('MOTORISTA', 'OPERACIONAL'),
    ('MOTORISTA DE CAMINHAO', 'OPERACIONAL'),
    ('OPERADOR (A) DE VIAGEM', 'OPERACIONAL'),
    ('OPERADOR (A) DE VIAGEM PLENO', 'OPERACIONAL'),
    ('OPERADOR (A) DE VIAGENS SÊNIOR', 'OPERACIONAL'),
    ('OPERADOR DE MONITORAMENTO PLENO', 'OPERACIONAL'),
    ('OPERADOR DE MONITORAMENTO SÊNIOR', 'OPERACIONAL'),
    ('OPERADOR DE VIAGEM DE GRUPOS', 'OPERACIONAL'),
    ('PILOTO', 'OPERACIONAL'),
    ('RECEPCIONISTA', 'OPERACIONAL'),
    ('REDATOR', 'OPERACIONAL'),
    ('SECRETARIA EXECUTIVA', 'OPERACIONAL'),
    ('SIGILOSA', 'OPERACIONAL'),
    ('SUPERVISOR (A) DE RH', 'TÁTICO'),
    ('SUPERVISOR DE ATENDIMENTO PLENO', 'TÁTICO'),
    ('SUPERVISOR DE ATENDIMENTO SÊNIOR', 'TÁTICO'),
    ('SUPERVISOR DE MARKETING', 'TÁTICO'),
    ('SUPERVISOR DE PATRIMÔNIO', 'TÁTICO'),
    ('TÉCNICO EM SEGURANÇA DO TRABALHO', 'OPERACIONAL'),
    ('VIGIA', 'OPERACIONAL'),
    ('ANALISTA DE NEGÓCIOS', 'OPERACIONAL'),
    ('ASSISTENTE DE EVENTOS', 'OPERACIONAL'),
    ('ESTAGIÁRIO DE EVENTOS', 'OPERACIONAL'),
    ('CONSULTOR DE ATENDIMENTO SENIOR', 'OPERACIONAL')
) AS v(nome, nivel_nome)
JOIN rh_niveis rn ON rn.nome = v.nivel_nome
ON CONFLICT (nome) DO NOTHING;

-- Indices
CREATE INDEX IF NOT EXISTS idx_rh_vagas_empresa     ON rh_vagas(empresa_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_status      ON rh_vagas(status_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_tipo_vaga   ON rh_vagas(tipo_vaga_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_cargo       ON rh_vagas(cargo_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_hierarquia  ON rh_vagas(hierarquia_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_responsavel ON rh_vagas(responsavel_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_requisitante ON rh_vagas(requisitante_id);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_data_receb  ON rh_vagas(data_recebimento);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_candidato   ON rh_vagas(candidato);
CREATE INDEX IF NOT EXISTS idx_rh_vagas_numero_req  ON rh_vagas(numero_requisicao);
CREATE INDEX IF NOT EXISTS idx_rh_uploads_criado_em ON rh_uploads(criado_em);

-- RLS -- service_role (backend usa SERVICE_ROLE_KEY, mesmo padrao dos demais servicos)
ALTER TABLE rh_ufs ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_ufs FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_ufs_service_role" ON rh_ufs FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_alocacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_alocacoes FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_alocacoes_service_role" ON rh_alocacoes FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_tipos_contrato ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_tipos_contrato FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_tipos_contrato_service_role" ON rh_tipos_contrato FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_tipos_vaga ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_tipos_vaga FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_tipos_vaga_service_role" ON rh_tipos_vaga FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_niveis ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_niveis FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_niveis_service_role" ON rh_niveis FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_hierarquias ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_hierarquias FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_hierarquias_service_role" ON rh_hierarquias FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_secoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_secoes FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_secoes_service_role" ON rh_secoes FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_modalidades ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_modalidades FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_modalidades_service_role" ON rh_modalidades FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_analistas ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_analistas FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_analistas_service_role" ON rh_analistas FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_requisitantes ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_requisitantes FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_requisitantes_service_role" ON rh_requisitantes FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_empresas FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_empresas_service_role" ON rh_empresas FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_status_vaga ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_status_vaga FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_status_vaga_service_role" ON rh_status_vaga FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_cargos ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_cargos FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_cargos_service_role" ON rh_cargos FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_vagas ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_vagas FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_vagas_service_role" ON rh_vagas FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE rh_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_uploads FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_uploads_service_role" ON rh_uploads FOR ALL TO service_role USING (true) WITH CHECK (true);
