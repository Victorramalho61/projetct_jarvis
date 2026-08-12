# Jarvis — Backup e Restauração

> Script real em produção: `scripts/backup.ps1` (PowerShell, roda no Windows Server). O antigo `scripts/backup.sh` (bash) não é usado — mantido apenas para referência histórica.

## O que é salvo

| Item | Método | Arquivo gerado | Retenção |
|---|---|---|---|
| `performance_reviews.fiscal_documents` | `pg_dump -Fc -Z9` (custom format) | `fiscal_documents_TIMESTAMP.dump` | 7 dias |
| Resto do banco `postgres` (exclui `fiscal_documents`) | `pg_dump -Fc -Z9` | `postgres_main_TIMESTAMP.dump` | 30 dias |
| Banco `evolution` (WhatsApp) | `pg_dump -Fc -Z9` | `evolution_db_TIMESTAMP.dump` | 30 dias |

Local: `E:\claudecode\claudecode\backups\{TIMESTAMP}\` (TIMESTAMP = `yyyyMMdd_HHmmss`).

Cada dump é gerado dentro do container `jarvis-db-1` (`docker exec`) e copiado pro host via `docker cp` — evita corromper binário custom-format ao passar pelo pipe do PowerShell.

---

## Agendamento

Task Scheduler do Windows: `Jarvis-Docker-Startup`-like task roda `scripts/backup.ps1` diariamente às **01:00**. Ver/ajustar:
```powershell
Get-ScheduledTask -TaskName "*backup*"
```

Credenciais SMTP (notificação por e-mail ao final) em `scripts/.env.backup` (não versionado — copiar de `scripts/.env.backup.example`).

## Executar manualmente

```powershell
powershell -ExecutionPolicy Bypass -File "E:\claudecode\claudecode\scripts\backup.ps1"
```

Log: `E:\claudecode\claudecode\backups\backup.log`.

---

## Upload para OneDrive (2026-08-10)

Além da cópia local, todo backup bem-sucedido é enviado automaticamente pro OneDrive do Victor (`grupovoetur-my.sharepoint.com/personal/victor_ramalho_voetur_com_br`), via Microsoft Graph API (app do Moneypenny, escopo `Files.ReadWrite` — delegado, usa o token OAuth já conectado em `connected_accounts`).

**Estrutura no OneDrive:**
```
Documents/Backup/jarvis_dump_{YYYYMMDD}/       ← diário, retenção 30 dias (apaga pastas mais antigas)
Documents/Backup/jarvis_dump_mensal_{YYYYMM}/  ← cópia extra no dia 1 de cada mês, sem rotação automática
```

**Como funciona:** `scripts/backup.ps1` chama, após os 3 dumps locais concluírem:
```powershell
docker compose run --rm -v "<pasta_do_backup>:/backup:ro" moneypenny-service `
  python /app/scripts/upload_backup_onedrive.py /backup <TIMESTAMP>
```
Esse script (`moneypenny-service/scripts/upload_backup_onedrive.py`) faz upload resumível (sessão do Graph API, chunks de 10MB — necessário pra arquivos >4MB) dos 3 `.dump`, e no final varre `Backup/` no OneDrive apagando pastas `jarvis_dump_{YYYYMMDD}` com mais de 30 dias.

**Falha de OneDrive não derruba o backup local** — se o upload falhar, o e-mail de notificação avisa, mas o backup local (a cópia principal) já está garantido antes de tentar o upload.

**Pré-requisito:** conta Microsoft conectada em `connected_accounts` (provider=`microsoft`) com escopo `Files.ReadWrite` consentido. Se o token expirar/for revogado, reconectar via:
```
GET /api/moneypenny/auth/microsoft/url  →  abrir a URL retornada, logar, autorizar
```

**Nota PowerShell:** o script roda com `$ErrorActionPreference = "Stop"` global — chamadas a `docker compose` (que sempre escreve no stderr, mesmo com sucesso) precisam trocar temporariamente pra `"Continue"`, senão o PowerShell trata a saída normal do Docker como erro fatal.

---

## Limpeza automática do Docker (2026-08-12)

Todo `docker compose build` deixa camadas de build cache e imagens intermediárias — sem limpeza, o disco virtual do WSL2 só cresce (**nunca encolhe por si só**, mesmo apagando arquivos de dentro do container: `docker system prune` libera espaço *dentro* do disco virtual, mas o `.vhdx` no Windows só reflete isso depois de compactado manualmente).

`backup.ps1` agora roda, após cada backup local:
```powershell
docker builder prune -f   # cache de build, sem uso ativo
docker image prune -f     # imagens orfas (sem -a — nao remove imagens com tag ainda referenciada)
```

**Se o C: continuar encolhendo mesmo com essa limpeza rodando**, o disco virtual do WSL2 provavelmente precisa ser compactado (indisponibilidade breve, ~1-2 min):
```powershell
wsl --shutdown
# localizar o .vhdx em C:\Users\<usuario>\AppData\Local\Docker\wsl\... e compactar via diskpart:
#   diskpart > select vdisk file="<caminho>" > compact vdisk
```

---

## Restauração

### PostgreSQL (`postgres_main` ou `fiscal_documents`)

```powershell
# Copia o dump pro container
docker cp backups\TIMESTAMP\postgres_main_TIMESTAMP.dump jarvis-db-1:/tmp/restore.dump

# Restaura (--clean apaga objetos existentes antes de recriar; remova se for banco vazio)
docker exec jarvis-db-1 pg_restore -U postgres -d postgres --no-owner --no-acl --clean /tmp/restore.dump
```

### Testar restauração sem tocar produção (recomendado antes de qualquer restore real)

```powershell
docker run --rm -d --name restore-test -e POSTGRES_PASSWORD=test postgres:15
docker cp backups\TIMESTAMP\postgres_main_TIMESTAMP.dump restore-test:/tmp/restore.dump
docker exec restore-test createdb -U postgres restoretest
docker exec restore-test pg_restore -U postgres -d restoretest --no-owner --no-acl /tmp/restore.dump
docker exec restore-test psql -U postgres -d restoretest -c "select count(*) from performance_reviews;"
docker stop restore-test  # --rm já remove ao parar
```
Erros do tipo `role "service_role" does not exist` nas `CREATE POLICY` são esperados nesse teste isolado (Postgres genérico sem os roles do Supabase) — não indicam falha de dados. **Validado em 2026-08-10**: restauração de 389 `performance_reviews` confirmada íntegra, incluindo correções de avaliador feitas no mesmo dia.

### Evolution (WhatsApp)

```powershell
docker cp backups\TIMESTAMP\evolution_db_TIMESTAMP.dump jarvis-db-1:/tmp/evolution.dump
docker exec jarvis-db-1 pg_restore -U postgres -d evolution --no-owner --no-acl --clean /tmp/evolution.dump
```

### Do OneDrive

Baixar manualmente de `Documents/Backup/jarvis_dump_{YYYYMMDD}/` (ou `jarvis_dump_mensal_{YYYYMM}/`) e seguir os passos de restauração acima.

---

## Monitoramento

```powershell
Get-ChildItem E:\claudecode\claudecode\backups | Sort-Object LastWriteTime -Descending | Select-Object -First 5
Get-Content E:\claudecode\claudecode\backups\backup.log -Tail 20
```

E-mail de confirmação (OK ou FALHA) enviado a cada execução — configurado em `scripts/.env.backup`.

---

## Troubleshooting

**`docker exec jarvis-db-1` falha com "No such container"**
```powershell
docker ps --filter name=jarvis-db
```

**Sem espaço em disco**
```powershell
Get-PSDrive E
```

**Upload OneDrive falha com 401/403**
Token expirado ou escopo insuficiente — reconectar via `GET /api/moneypenny/auth/microsoft/url`.

**pg_dump avisa "circular foreign-key constraints"**
Warning esperado, não é erro — não impede o dump nem a restauração completa (`-Fc` sem `--data-only` lida com a ordem via `pg_restore`).
