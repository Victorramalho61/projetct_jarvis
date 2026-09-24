# Paginação — limite de 1000 linhas do PostgREST

**Problema.** O Supabase/PostgREST devolve no máximo **1000 linhas por consulta** (max-rows), e passar `.limit(2000)` não muda isso. Código supabase-py como `sb.table("x").select(...).execute().data` **trunca calado**. Com isso:
- KPIs, contagens por `len()`, exportações e envios de e-mail ficam incompletos;
- conjuntos de dedupe ("já existe?") ficam incompletos e geram **duplicatas**.

**Padrão da correção** (mesmo do rh-service, `rh-service/services/paginacao.py`):
- cada serviço tem a sua cópia de `services/paginacao.py::buscar_todos(fabrica_de_query)`, com páginas de 1000 e `order("id")` como desempate;
- o helper recebe uma **fábrica**, porque `.range()` do postgrest-py acumula parâmetros no builder;
- contagem por `len(resp.data)` → `count="exact"` + `.limit(0)`;
- `.in_()` com milhares de ids → chunks de 150 **e** paginação por chunk.

**Processo, um serviço por vez:**
1. backup;
2. correção;
3. teste num container avulso com a imagem nova contra os dados de produção (números antes × depois);
4. commit → CI → healthy;
5. atualizar esta página.

**Rollback:** `docker tag jarvis-<svc>:pre-paginacao` + `docker compose up -d --no-deps <svc>`, seguido de `git revert`.

**Backups** (2026-09-24, antes de qualquer mudança):
- tag git `pre-paginacao-2026-09-24`;
- imagens `jarvis-<svc>:pre-paginacao` dos 8 serviços;
- CSV em `E:\claudecode\backups\paginacao\`: `benner_erros`, `performance_*` (employees, reviews, indicator_scores, tokens, calibrations, acks, action_plans) e `exp_*`.

**Tamanho das tabelas em 2026-09-24:**

| Tabela | Linhas |
|---|---|
| fiscal_documents | 105k |
| freshservice_tickets | 64k |
| payfly_reservations | 35k |
| performance_indicator_scores | 22k |
| benner_erros | 7k |
| system_checks | 6,5k |
| payfly_media_posts | 4,5k |
| freshservice_project_tasks | 2,1k |
| performance_reviews | 2k |
| performance_employees | 1,1k |

Status: ⏳ a fazer · ✅ feito · ❌ não possível (motivo) · ➖ não precisa

| # | Serviço | Status | Observações / problemas |
|---|---|---|---|
| 0 | rh-service | ✅ 2026-09-24 | Referência do padrão (commit `1fa700b`). |
| 1 | cards-service | ✅ 2026-09-24 (`dfe8367`) | export `cards_acessos` paginado (teto 50 mil); contagem com `limit(0)`. |
| 2 | satisfacao-service | ✅ 2026-09-24 (`3eb97ea`, deploy manual) | 14 leituras paginadas; contagem de campanha via `count`; `sat_email_log` em chunks. |
| 3 | expenses-service | ⏳ | governança (`len`/`sum`), PayFly mídia (`limit(2000)`, `days*50`, `1500`), media_pipeline. |
| 4 | monitoring-service | ⏳ | benner_rpa KPIs/top/evolução, **dedupe do coletor** (duplicatas?), log_monitor `limit(2000)`, uptime. |
| 5 | freshservice-service | ⏳ | KPIs PayFly (`_tickets_in_range`, `_count_in` por `len`), tarefas de projeto. |
| 6 | fiscal-service | ⏳ | export CSV/ZIP, apuração, conferência (`fiscal_items` `.in_` sem chunk). |
| 7 | performance-service | ⏳ | dashboard, pendências, exports, list_employees, dedupe de CPF, envio de tokens, reset de ciclo, action_plans, notifications. |
| 8 | experiencia-service | ⏳ | listas, auditoria, export, empresas — junto com o projeto "Avaliação de Experiência v2". |
| — | moneypenny / support / financeiro | ➖ | Sem leitura grande (financeiro lê SQL Server direto). support: `limit` sem `le=` e o histórico de conversa, ambos baixo risco. |

## Registro por serviço
_(preenchido durante a execução)_

### 1. cards-service — ✅
- `routes/access_logs.py`: o export usava `.limit(5000)`, cortado em 1000. Agora usa `buscar_todos(..., max_linhas=50000)`. `_count_query` ganhou `limit(0)` (só contagem, sem baixar linhas).
- Teste: a tabela hoje tem só 3 acessos. Com página forçada de 1 linha, voltaram as 3, e `max_linhas` respeitado. Export 200 OK.
- Observado, fora do escopo e sem mudança: o CSV exportado sai com **BOM duplicado** (`to_csv` já grava o BOM e a rota ainda codifica em `utf-8-sig`). O Excel abre normalmente, mas a 1ª coluna pode vir com um caractere invisível.

### 2. satisfacao-service — ✅
- **O que mudou:**
  - `services/dashboard.py`: respostas e itens (dashboard + histórico);
  - `routes/admin.py`: `list_campanhas` (via `count="exact"`), clientes em `create_campanha`, iniciar, postergar, respostas, triagem, ms-forms-log, timeline (`sat_email_log` em chunks de 150);
  - `routes/webhook.py`: match do cliente do Forms;
  - `routes/cadastro.py`: clientes;
  - `services/scheduler.py`: reforço e cobrança.
- **Teste:** com página forçada de **2 linhas**, a imagem nova devolveu os **mesmos números** do container de produção em todos os endpoints.
- **Problema enfrentado — CI travado 30 min:** o `deploy.sh` tem um hook que faz auto-commit e push de `docs/` quando há alteração local. A edição desta página ainda não estava commitada e disparou o hook. O `git push` ficou esperando o Git Credential Manager, que não tem janela no serviço do runner. Resolvido assim:
  - run cancelado pela API do GitHub;
  - `deploy.sh` corrigido (commit `fc352ee`): push não interativo com timeout; se falhar, desfaz o commit; `merge --ff-only` no lugar de `reset --hard`, que apagava trabalho não commitado;
  - o satisfacao foi publicado manualmente com `docker compose up -d --build --no-deps`.
- **Lição:** nunca deixar alteração sem commit neste diretório enquanto um deploy roda (o runner usa o mesmo checkout).
