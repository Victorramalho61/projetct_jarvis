# Relatório mensal ACCIONA — Freshdesk Omni

Extração + análise mensal dos tickets da empresa ACCIONA no Freshdesk Omni, no
formato usado para envio à operação por e-mail. Este doc existe para que, em
uma sessão nova, baste pedir "gera o relatório do Acciona desse mês" e o
Claude Code repita o processo sem re-descobrir tudo do zero.

## Fonte de dados

- **Sistema**: Freshdesk (produto "Omni" da Freshworks). Domínio de login:
  `voeturomni.myfreshworks.com` — mas a **API usa o domínio**
  `https://voeturomni.freshdesk.com/api/v2`.
- **Autenticação**: Basic Auth com API key. Já configurada em
  `.env` → `FRESHDESK_API_KEY`.
- **Filtro de empresa**: campo customizado `cf_empresa`. Os valores aceitos
  são fixos (case-sensitive) — o Freshdesk retorna 400 com a lista completa se
  o nome estiver errado. Para a Acciona o valor é **`ACCIONA`** (maiúsculo).

## Script

`freshdesk_export_excel.py` (raiz do repo). Reaproveita as funções de busca de
`freshdesk_sync.py` (mesma raiz — script original que fazia sync para SQL
Server BI, hoje sem uso ativo porque a tabela `dbo.freshdesk_tickets` não
existe no banco `BI`; não tentar gravar lá sem antes confirmar com o Victor).

### Uso

```bash
python freshdesk_export_excel.py --empresa "ACCIONA" \
  --from 2026-08-01 --to 2026-08-31 \
  --out "C:\Users\victor.ramalho\Desktop\Relatorio Agosto 26 Acciona EMAIL.xlsx"
```

Ajustar `--from`/`--to` para o mês desejado e o nome do arquivo de saída
seguindo o padrão `Relatorio <Mês por extenso> <AA> Acciona EMAIL.xlsx`,
salvo sempre no Desktop do Victor.

### Por que dividido por semana

A Search API do Freshdesk tem um teto de **300 resultados por consulta**
(10 páginas × 30). Um mês inteiro de ACCIONA facilmente ultrapassa isso. O
script quebra o período em chunks de 7 dias (`_week_chunks`) e deduplica por
`id` no final — isso garante cobertura completa do mês mesmo em picos de
volume. Não usar chunk mensal direto.

### Tempo de execução

É **lento** — não é bug, é característica da API: para cada ticket
resolvido/fechado é preciso uma chamada individual
`GET /tickets/{id}?include=stats` (não há como pegar `resolved_at` /
`first_responded_at` em lote). Com ~400 tickets/mês, a extração completa leva
tipicamente **20–40 minutos**. Rodar em background e aguardar — não é sinal
de travamento enquanto a CPU do processo Python continuar subindo
(`Get-Process -Id <pid> | select CPU`).

## Formato de saída (colunas, nesta ordem exata)

| Coluna | Origem |
|---|---|
| ID do ticket | `id` |
| Assunto | `subject` |
| Tipo | custom field `cf_mercado` (Nacional / Internacional / Vip - Nacional / Vip - Internacional) |
| Agente | nome do agente responsável, resolvido via `responder_id` → `GET /agents` (lista completa, ~86 agentes, cabe em 1 página). `"No Agent"` quando não há responsável. |
| Hora da criação | `created_at`, convertido de UTC para BRT (**UTC-3**, sem DST) |
| Tempo até a primeira resposta (em horas) | `stats.first_responded_at - created_at`, formatado `HH:MM:SS` (pode passar de 24h) |
| Tempo de resolução (em horas) | `stats.resolved_at - created_at`, mesmo formato |
| Hora da resolução | `stats.resolved_at` em BRT |
| Hora do fechamento | `stats.closed_at` em BRT |
| Tipo de demanda | custom field `cf_tipo_de_demanda` (Solicitação / Informação / Reclamação / Comunicação de Fornecedor) |

Esse layout replica exatamente um relatório de referência que já era enviado
manualmente (`Relatorio Junho 26 Acciona EMAIL.xlsx`) — **não alterar a ordem
ou os nomes das colunas** sem confirmar com o Victor, porque quem recebe o
arquivo (operação) espera esse formato específico.

Detalhe de fuso: `created_at` etc. vêm em UTC da API
(`2026-06-01T10:35:09Z`); o arquivo mostra hora local Brasil
(`2026-06-01 07:35:09`) — por isso o `-3h` fixo no script (`_BRT_OFFSET`).

## Análise padrão das colunas F e G (tempo de resposta / resolução)

Sempre que o Victor pedir para "analisar linha a linha" as colunas de tempo,
os padrões abaixo já são conhecidos e se repetem mês a mês — não é
inconsistência dos dados:

1. **Coluna F (tempo até 1ª resposta) fica em branco na maioria das linhas**
   (na amostra de julho/26, ~79%). Não é zero — é ausência de métrica. O
   Freshdesk só grava `first_responded_at` quando o ticket é uma conversa
   iniciada pelo cliente com resposta do agente. Muitos tickets da ACCIONA são
   abertos pelo próprio agente como registro de reserva/cotação — não existe
   "cliente esperando resposta", logo o campo nunca é preenchido.

2. **Resoluções quase instantâneas (segundos) — geralmente ~20% das linhas.**
   Olhando o assunto, são notificações automáticas do sistema de reservas:
   *"Confirmación de Reserva"*, *"Cambio de Reserva"*, *"Solicitud de Viaje
   Denegada"*. Fecham sozinhas, sem trabalho humano. Coincide com "Tipo de
   demanda" vazio.

3. **Efeito fim de semana**: tickets criados sexta à tarde/fim de semana
   ficam parados até segunda (sem atendimento sáb/dom) — sábado e segunda
   sempre aparecem com a maior média de tempo de resolução no agrupamento por
   dia da semana.

4. **"Tipo de demanda" explica a cauda longa**: "Informação" e "Comunicação
   de Fornecedor" dependem de retorno de companhia aérea/hotel — fora do
   controle do agente, podem levar dias. "Solicitação" é o fluxo normal
   (resolve mais rápido).

5. **Médias por agente podem enganar com poucos tickets**: um agente com
   volume baixo (ex.: 15-20 tickets/mês) pode ter média alta puxada por 1-2
   casos extremos de "aguardando fornecedor" — checar sempre a mediana / os
   casos individuais antes de concluir que o agente é lento.

## Referência

- Arquivo original usado como gabarito de formato:
  `C:\Users\victor.ramalho\Desktop\Relatorio Junho 26 Acciona EMAIL.xlsx`
- Script: `freshdesk_export_excel.py` (raiz do repo)
- Script legado (sync → SQL Server, não usado): `freshdesk_sync.py` (raiz do repo)
