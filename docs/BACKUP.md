# Jarvis — Backup e Restauração

> Script real em produção: `scripts/backup.ps1` (PowerShell, roda no Windows Server). O antigo `scripts/backup.sh` (bash) não é usado — mantido apenas para referência histórica.

## O que é salvo

| Item | Método | Arquivo gerado | Retenção |
|---|---|---|---|
| `performance_reviews.fiscal_documents` | `pg_dump -Fc -Z9` (custom format) | `fiscal_documents_TIMESTAMP.dump` | 7 dias |
| Resto do banco `postgres` (exclui `fiscal_documents`) | `pg_dump -Fc -Z9` | `postgres_main_TIMESTAMP.dump` | 30 dias |
| Banco `evolution` (WhatsApp) | `pg_dump -Fc -Z9` | `evolution_db_TIMESTAMP.dump` | 30 dias |
| Volumes Docker (evolution, waha, hermes, storage, letsencrypt, acme) | `tar czf` via container `alpine` (mount `:ro`) | `vol_<nome>_TIMESTAMP.tar.gz` | 30 dias |
| `.env` + `volumes/api/kong.yml` (segredos, fora do git) | AES-256-CBC + PBKDF2-SHA256, ver seção "Disaster Recovery" | `secrets_TIMESTAMP.zip.enc` | 30 dias |

Local: `E:\claudecode\claudecode\backups\{TIMESTAMP}\` (TIMESTAMP = `yyyyMMdd_HHmmss`).

Cada dump é gerado dentro do container `jarvis-db-1` (`docker exec`) e copiado pro host via `docker cp` — evita corromper binário custom-format ao passar pelo pipe do PowerShell.

**Volumes fora do pg_dump (2026-08-13)**: `jarvis_evolution_data`, `jarvis_waha_data`, `jarvis_hermes_data`, `jarvis_storage_data`, `jarvis_letsencrypt_certs`, `jarvis_acme_data` são compactados via container `alpine` temporário montando o volume `:ro` — protege contra corrupção do `.vhdx` do WSL2 (já ocorreu em 2026), que apagaria esses dados junto (não cobertos por pg_dump pois não são bancos Postgres). `jarvis_ollama_data` fica **fora de propósito**: são modelos baixados, reproduzíveis, não dados únicos. Tamanho total medido em 2026-08-13: ~26MB (a maioria dos volumes tem poucos KB) — praticamente não pesa no backup diário.

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

### Volumes Docker (evolution, waha, hermes, storage, letsencrypt, acme)

```powershell
# Recriar o volume (se nao existir) e restaurar o conteudo
docker volume create jarvis_hermes_data
docker run --rm -v jarvis_hermes_data:/data -v E:\claudecode\claudecode\backups\TIMESTAMP:/backup alpine `
    sh -c "cd /data && tar xzf /backup/vol_hermes_TIMESTAMP.tar.gz"
```
Repetir por volume, trocando o nome. Container correspondente precisa estar parado durante a restauracao para evitar gravacao concorrente (`docker compose stop <servico>`, restaura, `docker compose start <servico>`).

---

## Monitoramento

```powershell
Get-ChildItem E:\claudecode\claudecode\backups | Sort-Object LastWriteTime -Descending | Select-Object -First 5
Get-Content E:\claudecode\claudecode\backups\backup.log -Tail 20
```

E-mail de confirmação (OK ou FALHA) enviado a cada execução — configurado em `scripts/.env.backup`.

---

## Disaster Recovery — recuperação completa em servidor novo (2026-08-14)

Cenário: servidor atual perdido (disco morto, `.vhdx` do WSL2 corrompido) e precisa recriar tudo do zero num Docker novo.

### O que é 100% recuperável

| Item | Fonte | Como |
|---|---|---|
| Código de todos os microsserviços, `docker-compose*.yml`, Dockerfiles | `git clone https://github.com/Victorramalho61/projetct_jarvis.git` (remoto GitHub) | `docker compose build` reconstrói as imagens custom; imagens de terceiros (`postgres`, `redis`, `waha`, `ollama` etc.) vêm de `docker pull` normal |
| Todas as tabelas do Postgres local (usuários/auth do core-service, `connected_accounts` do moneypenny, avaliações/auto-avaliações/plano de ação do performance-service, `fiscal_documents`, resto do schema `public`) | `fiscal_documents_*.dump` + `postgres_main_*.dump` | `pg_restore` (ver seção acima) — todos esses serviços apontam pro mesmo Postgres local (`SUPABASE_URL=http://10.140.0.220:54321`), não Supabase cloud, então um único restore cobre todos |
| Banco `evolution` (WhatsApp) | `evolution_db_*.dump` | `pg_restore` |
| Sessão/autenticação WhatsApp (WAHA), estado do Hermes, certificados Let's Encrypt | `vol_waha_*.tar.gz`, `vol_hermes_*.tar.gz`, `vol_letsencrypt_*.tar.gz`, `vol_acme_*.tar.gz` | extrair tar.gz no volume recriado (ver seção "Volumes Docker" acima) |

### O que NÃO é recuperável hoje — gap conhecido

Nenhum backup cobre segredos: `.env` (raiz e de cada serviço) está no `.gitignore` e fora do escopo do `backup.ps1`; `volumes/api/kong.yml` (roteamento do Kong) também está gitignored e sem backup.

Consequências concretas se o `.env` se perder junto com o servidor:

- **`CERT_ENCRYPTION_KEY` (Fernet, fiscal-service)**: os certificados A1 já criptografados no dump do Postgres ficam **permanentemente indecifráveis** sem essa chave — precisaria reemitir/reupload de certificado de cada empresa cliente.
- **`CARD_ENCRYPTION_KEY` (Fernet, cards-service)**: mesmo problema pros dados de cartão no cofre.
- **Tokens OAuth (`connected_accounts`, ex. Microsoft/OneDrive)**: o registro sobrevive no banco restaurado, mas sem `MICROSOFT_CLIENT_SECRET` (e demais API keys — D4Sign, Freshservice, Anthropic, WhatsApp, SMTP) as integrações não voltam a funcionar até reconfigurar manualmente cada uma.
- **`JWT_SECRET` / `POSTGRES_PASSWORD`**: sem perda de dado real (só invalida sessões ativas / senha local do Postgres), recriáveis à vontade.
- **`kong.yml`**: precisaria reconstruir o roteamento na mão a partir do `docker-compose.yml` (rotas seguem o padrão de "Roteamento rápido" do `CLAUDE.md`).

**Volume `jarvis_storage_data` fica quase vazio (~8KB) por design, não é perda de dado** — confirmado por busca em todo o backend/frontend: a aplicação nunca usa a Supabase Storage API (`storage-api` container sobe como parte do stack padrão do Supabase, mas nenhum serviço faz upload de arquivo nele).

**Implementado em 2026-08-14**: `backup.ps1` agora empacota `.env` + `volumes/api/kong.yml` num zip e cifra com AES-256-CBC (chave derivada via PBKDF2-SHA256, 100k iterações, salt aleatório) em `secrets_TIMESTAMP.zip.enc`. Formato do arquivo: `salt(16 bytes) + iv(16 bytes) + ciphertext`. O zip temporário sem cifra é apagado logo após a criptografia. O `.enc` entra na mesma pasta do backup diário (rotação de 30 dias) e também sobe pro OneDrive junto dos `.dump` (`upload_backup_onedrive.py` inclui `*.enc` no upload).

A passphrase fica em `SECRETS_BACKUP_PASSPHRASE`, dentro de `scripts\.env.backup` (mesmo arquivo das credenciais SMTP, gitignored). Se a variável não estiver definida, o backup segue normalmente e só loga um aviso pulando essa etapa (não derruba o backup principal).

**⚠️ Crítico**: `scripts\.env.backup` está no mesmo servidor que o `.env` que ele protege — se o servidor inteiro morrer, a passphrase morre junto e o `secrets_*.zip.enc` que chegou no OneDrive fica permanentemente indecifrável. **Uma cópia da passphrase precisa estar guardada fora do servidor (gerenciador de senhas do Victor)**, não só no `.env.backup` local. Isso ainda depende de ação manual — o script não tem como fazer isso sozinho.

**Restaurar** (depois de recuperar a passphrase de onde ela foi guardada):
```powershell
$passphrase = "<passphrase guardada no gerenciador de senhas>"
$bytes = [System.IO.File]::ReadAllBytes("backups\TIMESTAMP\secrets_TIMESTAMP.zip.enc")
$salt = $bytes[0..15]; $iv = $bytes[16..31]; $cipher = $bytes[32..($bytes.Length-1)]
$pbkdf2 = New-Object System.Security.Cryptography.Rfc2898DeriveBytes($passphrase, $salt, 100000, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
$aes = [System.Security.Cryptography.Aes]::Create()
$aes.Key = $pbkdf2.GetBytes(32); $aes.IV = $iv; $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
$plain = $aes.CreateDecryptor().TransformFinalBlock($cipher, 0, $cipher.Length)
[System.IO.File]::WriteAllBytes("secrets_restored.zip", $plain)
Expand-Archive secrets_restored.zip -DestinationPath . # gera .env e kong.yml
```

**Gap ainda aberto (não coberto por este fix)**: os `vol_*.tar.gz` (volumes Docker) ficam só no disco local, `upload_backup_onedrive.py` nunca subiu eles pro OneDrive — se o disco local morrer antes de alguém copiar essa pasta pra outro lugar, esses volumes se perdem junto. Fora do escopo pedido aqui; sinalizado pra decisão futura.

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
