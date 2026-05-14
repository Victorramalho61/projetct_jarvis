# Jarvis — Manual do Usuário

> Sistema interno Voetur/VTCLog · Acesso: `https://jarvis.voetur.com.br` (ou endereço interno)

---

## 1. Login

```
┌─────────────────────────────────────────────┐
│              🔐  Jarvis                      │
│         Sistema Interno Voetur               │
│                                             │
│   Usuário  [________________________]       │
│   Senha    [________________________]       │
│                                             │
│            [    Entrar    ]                 │
│                                             │
│        Esqueceu a senha? Clique aqui        │
└─────────────────────────────────────────────┘
```

- **Usuário**: e-mail ou login fornecido pelo TI
- **Senha**: definida no primeiro acesso (link enviado por e-mail)
- Conta bloqueada? Contato: TI via WhatsApp ou Freshservice

---

## 2. Tela Inicial — Menu Lateral

Após o login, o menu lateral mostra os módulos disponíveis para o seu perfil:

```
┌──────────┬───────────────────────────────────────────────────┐
│  JARVIS  │                                                   │
├──────────┤                                                   │
│ ● Início │   Bem-vindo, Victor                               │
│           │   Perfil: Administrador                          │
│ 📊 Monit. │                                                  │
│ 🎫 Helpde.│   ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│ 💰 Gastos │   │ Sistemas │  │ Chamados │  │ Gastos   │     │
│ 📬 Email  │   │   OK     │  │  12 ab.  │  │ Jan: R$X │     │
│ 🤖 Agente │   └──────────┘  └──────────┘  └──────────┘     │
│ 📋 Desem. │                                                  │
│           │                                                  │
│ [Sair]    │                                                  │
└──────────┴───────────────────────────────────────────────────┘
```

| Ícone | Módulo | Quem acessa |
|---|---|---|
| 📊 | Monitoramento | Todos |
| 🎫 | Freshservice (Helpdesk) | Todos |
| 💰 | Gastos TI | Admin / Gestores |
| 📬 | Moneypenny (E-mails) | Todos |
| 🤖 | Agentes IA | Admin |
| 📋 | Desempenho | RH, Gestores, Colaboradores |

---

## 3. Monitoramento

Acompanhamento em tempo real dos sistemas e serviços da empresa.

```
┌─ Monitoramento ──────────────────────────────────────────────┐
│                                                              │
│  ● ERP Benner          ✅ Online    Latência: 42ms           │
│  ● Freshservice        ✅ Online    Latência: 180ms          │
│  ● Evolution API       ✅ Online    Latência: 28ms           │
│  ● Portal Voetur       ✅ Online    Latência: 310ms          │
│  ● Servidor de E-mail  ⚠️  Lento    Latência: 1.2s           │
│                                                              │
│  Último check: há 3 minutos           [Forçar verificação]   │
└──────────────────────────────────────────────────────────────┘
```

**Legendas de status:**
- ✅ Online — sistema respondendo normalmente
- ⚠️ Degradado — lento ou resposta parcial
- ❌ Offline — sem resposta

Alertas são enviados automaticamente por e-mail quando um sistema cai.

---

## 4. Helpdesk — Freshservice

Dashboard de chamados com métricas de atendimento.

```
┌─ Helpdesk Analytics ─────────────────────────────────────────┐
│  Período: [Março 2026 ▼]   Grupo: [Todos ▼]                 │
│                                                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │  Resolvidos│ │ Tempo Méd. │ │ SLA Breach │ │   CSAT   │  │
│  │     248    │ │  4h 12min  │ │   8,3%     │ │  4.7/5   │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘  │
│                                                              │
│  Por grupo:                                                  │
│  TI          ████████████████  120 chamados  SLA: 5,1%      │
│  Financeiro  ████████          58 chamados   SLA: 12,4%     │
│  RH          ██████            40 chamados   SLA: 3,2%      │
│                                                              │
│  Top agentes:  João (42), Maria (38), Pedro (31)            │
└──────────────────────────────────────────────────────────────┘
```

**Dicionário:**
- **SLA Breach**: % de chamados resolvidos fora do prazo contratado
- **CSAT**: satisfação do usuário (1–5 estrelas)
- **Tempo Médio**: da abertura até a resolução

---

## 5. Gastos TI

Dashboard financeiro de despesas do departamento de TI consumidas do ERP Benner.

```
┌─ Gastos TI ──────────────────────────────────────────────────┐
│  Ano: [2026 ▼]   Filial: [Matriz ▼]   Tipo: [Todos ▼]       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐      │
│  │  Jan    Fev    Mar    Abr    Mai    Jun  ...        │      │
│  │  R$80k  R$75k  R$92k  R$88k  R$71k  —             │      │
│  │  ▇▇▇▇   ▇▇▇▇   ▇▇▇▇▇  ▇▇▇▇▇  ▇▇▇    .....         │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  Total acumulado: R$ 406.000      Forecast Jun: R$ 79.200   │
│                                                              │
│  Detalhamento por tipo:                                      │
│  Software/Licenças  45%  ■■■■■■■■■                          │
│  Hardware           30%  ■■■■■■                             │
│  Telecomunicações   15%  ■■■                                │
│  Serviços           10%  ■■                                 │
└──────────────────────────────────────────────────────────────┘
```

- **Forecast**: projeção para o mês atual baseada em histórico
- **Filial**: filtra por empresa do grupo (Voetur, VTC, VIP Cargas...)
- Dados lidos diretamente do ERP Benner (atualização diária às 06h)

---

## 6. VoeIA — Bot de Suporte WhatsApp

O VoeIA é o assistente de suporte da Voetur pelo WhatsApp. Usuários enviam mensagens para o número oficial e o bot abre chamados automaticamente no Freshservice.

### Como usar (usuário final)

```
Usuário WhatsApp:
  "Olá"

VoeIA:
  "Olá! Sou o VoeIA, assistente de suporte da Voetur.
   Para começar, informe seu e-mail corporativo:"

Usuário:
  "victor@voetur.com.br"

VoeIA:
  "Encontrei seu cadastro: Victor Ramalho - Voetur Turismo.
   Confirma? (S/N)"

Usuário:
  "S"

VoeIA:
  "Escolha o departamento:
   1 - TI
   2 - Financeiro
   3 - RH / Pessoal
   4 - Operações
   5 - Suprimentos
   0 - Sair"

Usuário:
  "1"

VoeIA:
  "TI — qual o assunto?
   1 - Computador / Periféricos
   2 - Sistema / Software
   3 - Acesso / Senha
   4 - Internet / Rede
   0 - ↩️ Voltar"

[usuário escolhe → descreve o problema → confirma → chamado aberto]

VoeIA:
  "✅ Chamado #4821 aberto com sucesso!
   Você receberá atualizações aqui pelo WhatsApp."
```

### Atualizações automáticas

Quando o chamado for atualizado no Freshservice, o VoeIA notifica automaticamente o usuário:

| Evento | Mensagem enviada |
|---|---|
| Atribuído a um agente | "Seu chamado #4821 foi atribuído a João Silva" |
| Resolvido | "Chamado #4821 foi resolvido! Ficou satisfeito? Avalie..." |
| Fechado | "Chamado #4821 foi fechado." |

---

## 7. Gestão de Desempenho

Módulo para ciclos de avaliação de desempenho, metas e competências.

---

### 7.1 Visão por perfil

| Perfil | O que vê | O que faz |
|---|---|---|
| **Colaborador** | Meus Objetivos, Minha Avaliação | Assina metas, preenche autoavaliação, toma ciência do resultado |
| **Supervisor / Coordenador** | + Avaliar Liderados | Cria metas, avalia equipe, assina avaliações |
| **Gestor** | + Avaliar Liderados | Cria metas, avalia, gerencia KPIs e PDI |
| **RH** | Todos (+ Ciclos + Dashboard) | Cria ciclos, calibra notas, fecha ciclo, exporta dados |
| **Admin** | Tudo | Gestão completa |

---

### 7.2 Aba: Meus Objetivos (Colaborador)

```
┌─ Meus Objetivos ─────────────────────────────────────────────┐
│                                                              │
│  Meta: Reduzir tempo de resposta de chamados                 │
│  Tipo: KPI │ Período: Jan–Jun 2026 │ Status: [Rascunho]     │
│  Meta: ≤ 4h │ Atual: 4h 35min │ Peso: 2                    │
│                                           [Assinar e Aceitar]│
│                                                              │
│  Meta: Concluir treinamento ITIL v4                         │
│  Tipo: Tarefa │ Período: Mar 2026 │ Status: [Aguard. assina] │
│                                           [Assinar e Aceitar]│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Assinar meta** = Momento 1 do ciclo. Confirma que você leu e aceita os objetivos definidos pelo seu gestor.

---

### 7.3 Aba: Minha Avaliação (Colaborador)

```
┌─ Minha Avaliação ────────────────────────────────────────────┐
│                                                              │
│  Ciclo: 1º Semestre 2026        Status: [Autoavaliação]     │
│                                                              │
│  Metas:        [  ?  /5]   Selecione sua nota ▼             │
│  Competências: [  ?  /5]   Selecione sua nota ▼             │
│  Comportamento:[  ?  /5]   Selecione sua nota ▼             │
│  Compliance:   [  ?  /5]   Selecione sua nota ▼             │
│                                                              │
│  Comentários: [_______________________________________]      │
│                                                              │
│                               [Salvar rascunho] [Enviar]    │
└──────────────────────────────────────────────────────────────┘
```

**Escala de notas:**
| Nota | Significado |
|---|---|
| 1 | Abaixo do esperado |
| 2 | Abaixo do esperado (parcial) |
| 3 | Dentro do esperado |
| 4 | Acima do esperado |
| 5 | Excede expectativas |

⚠️ **Regra de compliance**: Se a nota de Compliance for < 2, o score final será limitado a 2,5 independente das outras notas.

---

### 7.4 Aba: Avaliar Liderados (Gestor/Supervisor)

```
┌─ Avaliar Liderados ──────────────────────────────────────────┐
│  Ciclo: [1º Semestre 2026 ▼]                                 │
│                                                              │
│  Colaborador        Status              Ação                │
│  ─────────────────────────────────────────────────────────  │
│  Ana Souza          ✅ Autoaval. feita  [Avaliar]           │
│  Carlos Lima        ⏳ Aguard. autoav.  [Ver]               │
│  Paula Mendes       ✅ Autoaval. feita  [Avaliar]           │
│                                                              │
│  ──────────────────────────────────────────────────────────  │
│  [Criar Meta]                                                │
└──────────────────────────────────────────────────────────────┘
```

Ao clicar em **Avaliar**:
```
┌─ Avaliação: Ana Souza ───────────────────────────────────────┐
│  Ciclo 1S/2026                                               │
│                                                              │
│  Nota Metas:          [4 — Acima do esperado ▼]             │
│  Nota Competências:   [3 — Dentro do esperado ▼]            │
│  Nota Comportamento:  [4 — Acima do esperado ▼]             │
│  Nota Compliance:     [3 — Dentro do esperado ▼]            │
│                                                              │
│  Score calculado:     3,65 / 5,00                           │
│  Comentários: [_________________________________________]    │
│                                                              │
│  Assinatura:  [__________]        [Salvar] [Assinar e Enviar]│
└──────────────────────────────────────────────────────────────┘
```

Após assinar → colaborador recebe notificação para **tomar ciência** (Momento 2).

---

### 7.5 Aba: Ciclos (RH)

```
┌─ Ciclos de Avaliação ────────────────────────────────────────┐
│                                                              │
│  Novo Ciclo:                                                 │
│  Nome: [___________________] Início: [__/__/____]           │
│  Fim:  [__/__/____]                  [Criar Ciclo]          │
│                                                              │
│  ──────────────────────────────────────────────────────────  │
│  Ciclo                  Período           Status   Ação     │
│  1º Semestre 2026       Jan–Jun 2026      Rascunho [Abrir]  │
│  2º Semestre 2025       Jul–Dez 2025      Fechado  [Ver]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Status do ciclo:**
- **Rascunho** → RH configura o ciclo; ninguém vê ainda
- **Aberto** → Colaboradores recebem metas; autoavaliações habilitadas
- **Avaliação** → Gestores avaliam os liderados
- **Calibração** → RH revisa e ajusta notas
- **Fechado** → Ciclo encerrado; resultados disponíveis

---

### 7.6 Aba: Dashboard RH

```
┌─ Dashboard de Desempenho ────────────────────────────────────┐
│  Ciclo: [1º Semestre 2026 ▼]                                 │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  Total   │ │Concluídas│ │Bloqueadas│ │  Completude  │   │
│  │   120    │ │    45    │ │    3     │ │    37,5%     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                              │
│  Distribuição de scores:                                     │
│  1 (Abaixo)    ■■            5%                             │
│  2             ■■■■         12%                             │
│  3 (Esperado)  ■■■■■■■■■■   48%                             │
│  4             ■■■■■■■      30%                             │
│  5 (Excede)    ■            5%                              │
│                                                              │
│  Colaboradores aguardando ciência: 8                        │
│                                                              │
│  Calibração:                                                 │
│  Colaborador: [___________▼]  Score calibrado: [___]        │
│  Justificativa: [_________________________________]          │
│                              [Aplicar calibração]           │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Recuperação de Senha

```
┌─ Recuperar Senha ────────────────────────────────────────────┐
│                                                              │
│   E-mail: [________________________________]                 │
│                                                              │
│              [Enviar link de redefinição]                    │
│                                                              │
│   ← Voltar para o login                                     │
└──────────────────────────────────────────────────────────────┘
```

Você receberá um e-mail com link válido por **1 hora**. Clique no link, defina a nova senha e faça login normalmente.

---

## 9. Gerenciamento de Acesso (somente Admin)

```
┌─ Gerenciamento de Acesso ────────────────────────────────────┐
│                                                              │
│  [+ Novo Usuário]                [🔍 Buscar: ___________]   │
│                                                              │
│  Nome             E-mail              Perfil      Status    │
│  Victor Ramalho   v.ramalho@...       Admin       ✅ Ativo  │
│  Ana Souza        a.souza@...         Colaborador ✅ Ativo  │
│  Carlos Lima      c.lima@...          Gestor      ✅ Ativo  │
│  Paula Mendes     p.mendes@...        RH          ⛔ Inativo│
│                                       [Editar] [Ativar]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Perfis disponíveis:**

| Perfil | Módulos |
|---|---|
| `admin` | Acesso total |
| `user` | Monitoramento, Freshservice, Moneypenny |
| `rh` | Desempenho (ciclos, calibração, relatórios) |
| `gestor` | Desempenho (metas, avaliação, KPIs) |
| `coordenador` | Desempenho (metas, avaliação, PDI) |
| `supervisor` | Desempenho (metas, avaliação) |
| `colaborador` | Desempenho (metas próprias, autoavaliação) |

---

## 10. Dúvidas e Suporte

- **WhatsApp VoeIA**: envie mensagem para o número oficial do suporte Voetur
- **Freshservice**: `https://voetur1.freshservice.com`
- **TI**: victor.ramalho@voetur.com.br
