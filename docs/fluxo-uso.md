# Jarvis — Fluxo de Uso do Sistema

---

## 1. Fluxo Geral do Sistema

```mermaid
flowchart TD
    A([Usuário acessa Jarvis]) --> B{Tem conta?}
    B -- Não --> C[Admin cria conta\nem Gerenc. de Acesso]
    C --> D[Usuário recebe e-mail\ncom link de senha]
    D --> E[Define senha e faz login]
    B -- Sim --> E
    E --> F{Qual o perfil?}

    F -- admin/user --> G[Monitoramento\nFreshservice\nMoneypenny\nAgentes]
    F -- rh --> H[Desempenho\nCiclos + Dashboard]
    F -- gestor/coord/supervisor --> I[Desempenho\nMetas + Avaliação de Liderados]
    F -- colaborador --> J[Desempenho\nMetas próprias + Autoavaliação]
```

---

## 2. Fluxo de Login e Recuperação de Senha

```mermaid
flowchart TD
    A([Abre o Jarvis]) --> B[Digita usuário e senha]
    B --> C{Credenciais corretas?}
    C -- Sim --> D[Dashboard principal]
    C -- Não --> E[Mensagem de erro]
    E --> F{Esqueceu a senha?}
    F -- Não --> B
    F -- Sim --> G[Clica em Esqueceu a senha]
    G --> H[Informa e-mail]
    H --> I[Recebe link por e-mail\nválido por 1h]
    I --> J[Define nova senha]
    J --> B
```

---

## 3. Fluxo VoeIA — Abertura de Chamado pelo WhatsApp

```mermaid
flowchart TD
    A([Usuário envia mensagem\nno WhatsApp]) --> B{Já tem cadastro?}

    B -- Não --> C[Bot pede e-mail]
    C --> D{E-mail encontrado\nno Freshservice?}
    D -- Sim --> E[Confirma nome + empresa\nauto-detectada]
    D -- Não --> F[Preenche nome,\nempresa e local\nmanualmente]
    F --> E

    B -- Sim --> E

    E --> G[Escolhe departamento\n1-TI 2-Financeiro 3-RH\n4-Operações 5-Suprimentos]
    G --> H[Escolhe subcategoria]
    H --> I{Quer voltar?}
    I -- Sim / digita 0 ou voltar --> G
    I -- Não --> J[Descreve o problema]
    J --> K[Confirma os dados]
    K --> L{Confirma?}
    L -- Não --> G
    L -- Sim --> M[Chamado criado\nno Freshservice]
    M --> N[Bot envia número\ndo chamado]
    N --> O([Notificações automáticas\npor WhatsApp])
```

### Notificações automáticas após abertura

```mermaid
flowchart LR
    A([Chamado criado]) --> B{Evento no\nFreshservice}
    B --> C[Atribuído a agente]
    B --> D[Resolvido]
    B --> E[Fechado]
    C --> F[WhatsApp: chamado\natribuído a Nome]
    D --> G[WhatsApp: chamado\nresolvido - avalie]
    E --> H[WhatsApp: chamado\nfechado]
```

---

## 4. Fluxo Completo de Gestão de Desempenho

### 4.1 Visão Macro do Ciclo

```mermaid
flowchart TD
    A([RH cria Ciclo]) --> B[Status: Rascunho]
    B --> C[RH cria Metas\npara colaboradores]
    C --> D[RH abre o Ciclo]
    D --> E[Status: Aberto\nMetas visíveis]

    E --> F[Colaborador assina\nas metas — Momento 1]
    F --> G[Status meta:\nPending Ack → Active]

    G --> H[RH inicia fase\nde Avaliação]
    H --> I[Status: Avaliação]

    I --> J[Colaborador preenche\nAutoavaliação]
    J --> K[Gestor avalia\no colaborador]
    K --> L[Gestor assina\no resultado]

    L --> M[Colaborador toma\nciência — Momento 2]
    M --> N{Aceita ou\ncontesta?}
    N -- Aceita --> O[Status: Concluída]
    N -- Contesta --> P[Status: Contestada\nRH analisa]
    P --> Q[RH resolve\ndisputa]
    Q --> O

    O --> R[RH calibra\nse necessário]
    R --> S[RH fecha o Ciclo]
    S --> T([Status: Fechado])
```

### 4.2 Fluxo detalhado — RH (Criação e Gestão)

```mermaid
flowchart TD
    A([Acessa módulo\nDesempenho]) --> B[Aba: Ciclos]
    B --> C[Cria novo ciclo:\nnome + período]
    C --> D[Status: Rascunho]

    D --> E[Cria metas\npara colaboradores]
    E --> F{Meta para\nquem?}
    F -- Colaborador específico --> G[Define owner_id]
    F -- Departamento --> H[Define department_id]

    G --> I[Preenche:\ntítulo, tipo, KPI,\nmeta, período, peso]
    H --> I
    I --> J[Salva meta\nStatus: draft]

    J --> K{Mais metas?}
    K -- Sim --> E
    K -- Não --> L[Clica em Abrir Ciclo]
    L --> M[Ciclo muda para Aberto\nColaboradores recebem metas]

    M --> N[Aguarda autoavaliações]
    N --> O[Dashboard: acompanha\ncompletude %]

    O --> P[Aba Dashboard:\nCalibra notas se necessário]
    P --> Q[Fecha o ciclo\nquando todos concluírem]
```

### 4.3 Fluxo detalhado — Colaborador

```mermaid
flowchart TD
    A([Acessa aba\nMeus Objetivos]) --> B[Vê lista de metas\ncom status Rascunho]
    B --> C[Clica Assinar e Aceitar\nem cada meta]
    C --> D[Momento 1 registrado\nMeta → Active]
    D --> E{Mais metas\npara assinar?}
    E -- Sim --> C
    E -- Não --> F[Aguarda ciclo\nentrar em Avaliação]

    F --> G([Aba: Minha Avaliação])
    G --> H[Preenche autoavaliação:\nMetas / Competências /\nComportamento / Compliance]
    H --> I{Score compliance\n≥ 2,0?}
    I -- Não --> J[⚠️ Aviso: score final\nsera limitado a 2,5]
    I -- Sim --> K[Score calculado\nnormalmente]
    J --> L[Envia autoavaliação]
    K --> L

    L --> M[Aguarda gestor\navaliar]
    M --> N[Recebe notificação:\nAvaliação disponível]
    N --> O[Aba: Minha Avaliação\nVê resultado final]
    O --> P{Aceita ou\ncontesta?}
    P -- Aceita --> Q[Momento 2 registrado\nStatus: Concluída]
    P -- Contesta --> R[Informa motivo\nda contestação]
    R --> S[Status: Contestada\nRH analisa]
```

### 4.4 Fluxo detalhado — Gestor / Supervisor

```mermaid
flowchart TD
    A([Acessa aba\nAvaliar Liderados]) --> B[Vê lista de liderados\ne seus status]
    B --> C{Colaborador concluiu\nautoavaliação?}
    C -- Não --> D[Aguarda / acompanha]
    C -- Sim --> E[Clica em Avaliar]

    E --> F[Preenche notas:\nMetas, Competências,\nComportamento, Compliance]
    F --> G[Sistema calcula\nscore automaticamente]
    G --> H[Adiciona comentários]
    H --> I[Assina a avaliação\nMomento 2 — gestor]
    I --> J[Colaborador recebe\nnotificação para ciência]

    J --> K{Criar metas para\npróximo ciclo?}
    K -- Sim --> L[Aba: Minha Avaliação\n→ nova meta]
    K -- Não --> M([Aguarda próximo ciclo])
```

---

## 5. Fluxo de Score de Desempenho

```mermaid
flowchart TD
    A([Gestor preenche\nnotas 1-5]) --> B[Score Metas\n× 50%]
    A --> C[Score Competências\n× 25%]
    A --> D[Score Comportamento\n× 15%]
    A --> E[Score Compliance\n× 10%]

    B --> F[Score Bruto =\nMédia ponderada]
    C --> F
    D --> F
    E --> F

    F --> G{Compliance < 2,0?}
    G -- Sim --> H[⚠️ Score Final\nlimitado a 2,5]
    G -- Não --> I[Score Final =\nScore Bruto]

    H --> J([Score Final registrado\nna avaliação])
    I --> J
```

**Exemplo de cálculo:**
```
Metas:        4,0  × 0,50 = 2,00
Competências: 3,0  × 0,25 = 0,75
Comportamento:3,5  × 0,15 = 0,53
Compliance:   3,0  × 0,10 = 0,30
                    Total = 3,58
Compliance ≥ 2,0 → Score Final = 3,58
```

---

## 6. Fluxo de Monitoramento de Sistemas

```mermaid
flowchart TD
    A([Scheduler a cada\n5 minutos]) --> B[Verifica cada\nsistema monitorado]
    B --> C{Sistema respondeu?}

    C -- Sim, dentro do prazo --> D[Registra: ✅ Online\nlatência em ms]
    C -- Lento > limite --> E[Registra: ⚠️ Degradado]
    C -- Sem resposta --> F[Registra: ❌ Offline]

    D --> G{Mudou de status\ndesde o último check?}
    E --> G
    F --> G

    G -- Não --> H([Aguarda próximo ciclo])
    G -- Sim + sistema offline --> I[Envia alerta\npor e-mail]
    I --> H
```

---

## 7. Fluxo de Sincronização Freshservice

```mermaid
flowchart TD
    A([Diariamente\n01:00 BRT]) --> B[Freshservice Sync\ncomeça]
    B --> C[Busca todos os tickets\nupdated_at de ontem]
    C --> D[Upsert em\nfreshservice_tickets]
    D --> E[Sincroniza agentes,\ngrupos e empresas]
    E --> F[Claude AI analisa\nos tickets do dia]
    F --> G[Gera resumo em\nfreshservice_sync_log]
    G --> H([Dashboard atualizado])
```

---

## 8. Fluxo de Gastos TI

```mermaid
flowchart TD
    A([Usuário acessa\nGastos TI]) --> B{Cache válido\n< 5 minutos?}

    B -- Sim --> C[Retorna dados\ndo cache Supabase]
    B -- Não --> D{Circuit Breaker\nBenner aberto?}

    D -- Sim --> E[Retorna último\ncache disponível\n+ aviso de degradação]
    D -- Não --> F[Tenta conexão\nSQL Server Benner]

    F --> G{Conectou?}
    G -- Não / Timeout --> H[Retry 1 de 3\nwait 2s]
    H --> I{Retry 2?}
    I -- Falhou --> J[Retry 3\nwait 10s]
    J -- Falhou --> K[Abre Circuit Breaker\nRetorna cache antigo]
    G -- Sim --> L[Executa query\nfiltro: empresa=1, gestor=23]
    L --> M[Processa dados:\nmensal, filial, tipo]
    M --> N[Atualiza cache\nSupabase]
    N --> O[Retorna dados\natualizados]

    C --> P([Dashboard exibido])
    E --> P
    O --> P
    K --> P
```

---

## 9. Fluxo de Criação de Usuário (Admin)

```mermaid
flowchart TD
    A([Admin acessa\nGerenc. de Acesso]) --> B[Clica + Novo Usuário]
    B --> C[Preenche:\nnome, e-mail, perfil]
    C --> D[Sistema cria conta\ninativa]
    D --> E[Envia e-mail com\nlink de definição de senha]
    E --> F([Usuário recebe e-mail])
    F --> G[Clica no link\ndefine senha]
    G --> H[Conta ativada]
    H --> I([Usuário faz login])
```
