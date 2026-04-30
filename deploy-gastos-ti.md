# Briefing: Deploy — Módulo Gastos de TI

## O que foi implementado
Novo módulo de gestão de gastos de tecnologia no Jarvis. Todos os arquivos de código já estão em disco. Nada foi deployado ainda.

## O que você precisa fazer

### 1. Preencher credenciais do SQL Server no .env
Abrir `E:\claudecode\claudecode\.env` e preencher as 5 variáveis:
```
SQL_SERVER_HOST=      ← IP ou hostname do SQL Server do ERP
SQL_SERVER_PORT=1433  ← porta (padrão 1433)
SQL_SERVER_DB=        ← nome do banco de dados
SQL_SERVER_USER=      ← usuário
SQL_SERVER_PASSWORD=  ← senha
```
Pergunte ao Victor as credenciais antes de prosseguir.

### 2. Build e deploy do novo serviço
```bash
cd /e/claudecode/claudecode
docker compose build expenses-service
docker compose up -d --no-deps expenses-service
```

### 3. Rebuild do frontend (recharts foi adicionado ao package.json)
```bash
docker compose build frontend
docker compose up -d --no-deps frontend
```

### 4. Recarregar Kong para registrar a nova rota
```bash
docker compose restart kong
```

### 5. Verificar se tudo subiu
```bash
docker compose ps expenses-service frontend kong
docker compose logs --tail=40 expenses-service
```

## Testes de verificação
1. `curl -H "Authorization: Bearer <token>" "https://jarvis.voetur.com.br/api/expenses/dashboard?from=2026-01-01&to=2026-04-30"` → deve retornar JSON com `kpis`, `by_month`, `by_conta`, `rows`
2. Acessar `https://jarvis.voetur.com.br/admin/gastos` no browser → deve aparecer "Gastos TI" na sidebar e a página carregar com KPIs e gráficos

## Se o expenses-service não subir
- Verificar logs: `docker compose logs expenses-service`
- Causa mais comum: credenciais SQL Server erradas ou SQL Server inacessível da rede do Docker
- O serviço sobe mesmo sem SQL Server configurado (a rota retorna 500 só quando chamada)

## Projeto
Diretório: `E:\claudecode\claudecode\`
