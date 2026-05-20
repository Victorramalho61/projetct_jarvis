# Schema BI GRU — Documentacao Tecnica dos Bancos de Dados

> **Servidor:** `VOET-SVM141112\GRU_BI`  
> **Porta:** 1433  
> **Instancias:** AG_01 (dtbTransporte, dtbCTe2026) | AG_02 (HangFireWMS, VTCLOG, VTCLOG_EXT, WMSRX, WMSRX_EXT, WMSRX_EXT2)  
> **Usuario:** usr_bi_gru (somente leitura)  
> **Gerado em:** 2026-05-13  

---

## Indice

| # | Banco | Instancia | Tabelas | Views | Proposito Principal |
|---|-------|-----------|---------|-------|---------------------|
| 1 | [HangFireWMS](#1-hangfirewms) | AG_02 | 11 | 0 | Fila de background jobs do WMS |
| 2 | [VTCLOG](#2-vtclog) | AG_02 | 11 | 40 | WMS VTCLog — estoque/LPN/container GRU |
| 3 | [VTCLOG_EXT](#3-vtclog_ext) | AG_02 | 10 | 29 | WMS VTCLog extensao (filial RJ/campus extra) |
| 4 | [WMSRX](#4-wmsrx) | AG_02 | 713 | 119 | WMS principal GRU SP — pedidos, LPN, inventario |
| 5 | [WMSRX_EXT](#5-wmsrx_ext) | AG_02 | 707 | 119 | WMS extensao (schema espelho, filial alternativa) |
| 6 | [WMSRX_EXT2](#6-wmsrx_ext2) | AG_02 | 713 | 119 | WMS extensao 2 (campus adicional GRU) |
| 7 | [dtbTransporte](#7-dtbtransporte) | AG_01 | 1542 | 28 | TMS VTCLog — movimentos, CTe, MDFe, financeiro |
| 8 | [dtbCTe2026](#8-dtbcte2026) | AG_01 | 30 | 0 | Arquivo XML CTe e MDFe 2026 (particionado x5) |

---


## 1. HangFireWMS

**Proposito:** Repositorio de filas e jobs do framework Hangfire para processamento assincrono de tarefas do WMS (reprocessamento EDI, notificacoes, relatorios).

**Schema:** `HangFire` | **Tabelas:** 11 | **Views:** 0

### Visao Geral

| Tabela | Linhas | Descricao |
|--------|--------|-----------|
| `HangFire.AggregatedCounter` | 0 | Contadores agregados de execucoes |
| `HangFire.Counter` | 0 | Contadores simples de estado |
| `HangFire.Hash` | 0 | Pares chave-valor para dados auxiliares dos jobs |
| `HangFire.Job` | 0 | Registro principal de cada job (payload, estado, criacao) |
| `HangFire.JobParameter` | 0 | Parametros extras associados a cada job |
| `HangFire.JobQueue` | 0 | Fila de jobs aguardando execucao por worker |
| `HangFire.List` | 0 | Listas de valores auxiliares |
| `HangFire.Schema` | 1 | Versao do schema HangFire |
| `HangFire.Server` | 0 | Servidores Hangfire ativos |
| `HangFire.Set` | 0 | Conjuntos ordenados (ex: scheduled jobs) |
| `HangFire.State` | 0 | Historico de transicoes de estado de cada job |

### MER — Entidades e Atributos

#### `HangFire.AggregatedCounter`

Linhas: **0**  
PK: `Key`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Key` (PK) | nvarchar(100) | N |  |
| `Value` | bigint(19) | N |  |
| `ExpireAt` | datetime | S |  |

#### `HangFire.Counter`

Linhas: **0**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Key` | nvarchar(100) | N |  |
| `Value` | int(10) | N |  |
| `ExpireAt` | datetime | S |  |

#### `HangFire.Hash`

Linhas: **0**  
PK: `Key, Field`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Key` (PK) | nvarchar(100) | N |  |
| `Field` (PK) | nvarchar(100) | N |  |
| `Value` | nvarchar(MAX) | S |  |
| `ExpireAt` | datetime2 | S |  |

#### `HangFire.Job`

Linhas: **0**  
PK: `Id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Id` (PK) | bigint(19) | N |  |
| `StateId` | bigint(19) | S |  |
| `StateName` | nvarchar(20) | S |  |
| `InvocationData` | nvarchar(MAX) | N |  |
| `Arguments` | nvarchar(MAX) | N |  |
| `CreatedAt` | datetime | N |  |
| `ExpireAt` | datetime | S |  |

#### `HangFire.JobParameter`

Linhas: **0**  
PK: `JobId, Name`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `JobId` (PK) | bigint(19) | N |  |
| `Name` (PK) | nvarchar(40) | N |  |
| `Value` | nvarchar(MAX) | S |  |

Relacionamentos (FK):
- `JobId` -> `Job.Id`

#### `HangFire.JobQueue`

Linhas: **0**  
PK: `Queue, Id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Id` (PK) | int(10) | N |  |
| `JobId` | bigint(19) | N |  |
| `Queue` (PK) | nvarchar(50) | N |  |
| `FetchedAt` | datetime | S |  |

#### `HangFire.List`

Linhas: **0**  
PK: `Key, Id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Id` (PK) | bigint(19) | N |  |
| `Key` (PK) | nvarchar(100) | N |  |
| `Value` | nvarchar(MAX) | S |  |
| `ExpireAt` | datetime | S |  |

#### `HangFire.Schema`

Linhas: **1**  
PK: `Version`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Version` (PK) | int(10) | N |  |

#### `HangFire.Server`

Linhas: **0**  
PK: `Id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Id` (PK) | nvarchar(200) | N |  |
| `Data` | nvarchar(MAX) | S |  |
| `LastHeartbeat` | datetime | N |  |

#### `HangFire.Set`

Linhas: **0**  
PK: `Key, Value`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Key` (PK) | nvarchar(100) | N |  |
| `Score` | float(53) | N |  |
| `Value` (PK) | nvarchar(256) | N |  |
| `ExpireAt` | datetime | S |  |

#### `HangFire.State`

Linhas: **0**  
PK: `JobId, Id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `Id` (PK) | bigint(19) | N |  |
| `JobId` (PK) | bigint(19) | N |  |
| `Name` | nvarchar(20) | N |  |
| `Reason` | nvarchar(100) | S |  |
| `CreatedAt` | datetime | N |  |
| `Data` | nvarchar(MAX) | S |  |

Relacionamentos (FK):
- `JobId` -> `Job.Id`

### DER — Relacionamentos

    Job (1) --|< State (N)         [Job.Id -> State.JobId]
    Job (1) --|< JobParameter (N)  [Job.Id -> JobParameter.JobId]
    JobQueue -> Job                [JobQueue.JobId -> Job.Id]

### Regras de Negocio Inferidas

- `Job.StateName`: estado atual do job (Enqueued, Processing, Succeeded, Failed, Scheduled, Deleted)
- `State`: historico de transicoes com motivo de falha em JSON no campo `Data`
- Jobs com `ExpireAt != NULL` sao purgados pelo servidor Hangfire automaticamente
- `Schema` sempre tem 1 registro com a versao atual do banco HangFire

---

## 2. VTCLOG

**Proposito:** WMS VTCLog — banco principal de controle de estoque, LPN, containers e movimentacoes para a operacao GRU. Usado para consultas BI de estoque, inventario e rastreabilidade de volumes.

**Schema:** `dbo` | **Tabelas:** 11 | **Views:** 40

### Visao Geral — Tabelas

| Tabela | Linhas | Descricao |
|--------|--------|-----------|
| `dbo.balanca_pedido_volume` | 2.482.516 | Pesagem de volumes por pedido na balanca (2,4M registros) |
| `dbo.container` | 521.062 | Containers/LPN fisicos (521k) |
| `dbo.ContainerMovimentoVolume` | 318 | Movimentacao de volumes entre containers |
| `dbo.Deadlock_log` | 23.498 | Log de deadlocks SQL capturados (23k) |
| `dbo.Embalagem` | 20 | Tipos de embalagem disponiveis |
| `dbo.estoque` | 35.748 | Posicao de estoque atual por produto/lote/endereco |
| `dbo.estoque_vtclog` | 35.748 | Espelho/backup da tabela estoque |
| `dbo.Impressoras` | 6 | Cadastro de impressoras de etiqueta |
| `dbo.Inventario_Datalogger` | 80.664 | Leituras de inventario via datalogger |
| `dbo.lote_estoque_lpn_data` | 36.117.772 | Historico detalhado de saldo por lote/LPN (36M registros) |
| `dbo.sysdiagrams` | 0 | Diagrama SSMS (sistema) |

### Visao Geral — Views (40)

| View | Proposito Inferido |
|------|-------------------|
| `dbo.vw_EstoqueCHPxDelage` | Cruzamento estoque CHP x Delage |
| `dbo.vw_InventarioDatalogger` | Dados de inventario via datalogger |
| `dbo.vw_movimentacao_aberto` | Movimentacoes em aberto |
| `dbo.vw_Operacao_Logistica` | Dashboard operacional logistica |
| `dbo.vw_PedidoContainerVolumes` | Volumes por pedido e container |
| `dbo.vw_PedidoVolumeReembaladoProdutolotes` | Reembalagem com detalhes de produto/lote |
| `dbo.vw_PedidoVolumesReembalados` | Volumes reembalados por pedido |
| `dbo.vw_PedidoVolumesReembalados_230808` | Snapshot de volumes reembalados (ago/2023) |
| `dbo.vw_PosicoesMovimentacao` | Posicoes de movimentacao no estoque |
| `dbo.vw_ProdutosVinculados` | Produtos com vinculo de variantes |
| `dbo.vw_SemProdutoLotesProduzidos` | Lotes produzidos sem produto associado |
| `dbo.vw_usuarios` | Usuarios do WMS |
| `dbo.vw_VolumeLPN` | Dados de volumes e LPN |
| `dbo.vw_VolumeLPN_240528` | Snapshot volume/LPN (mai/2024) |
| `dbo.vw_VolumeLPN_EXT2` | Volume/LPN para extensao EXT2 |
| `dbo.vw_VolumesEmbalagens` | Volumes x tipos de embalagem |
| `dbo.vw_VolumesEmbalagens_221227` |  |
| `dbo.vwExcel_AcompanhamentoCadastroResumo` | Export Excel: acompanhamento de cadastros |
| `dbo.vwExcel_CadastroProdutos` | Export Excel: catalogo de produtos |
| `dbo.vwExcel_Estoque` | Export Excel: posicao de estoque atual |
| `dbo.vwExcel_Estoque_230306` | Export Excel: estoque snapshot mar/2023 |
| `dbo.vwExcel_Estoque_240405` | Export Excel: estoque snapshot abr/2024 |
| `dbo.vwExcel_Estoque_260121` | Export Excel: estoque snapshot jan/2026 |
| `dbo.vwExcel_Estoque_EXT2` | Export Excel: estoque campus EXT2 |
| `dbo.vwExcel_Estoque_rj` | Export Excel: estoque filial RJ |
| `dbo.vwExcel_EstoqueVCP` | Export Excel: estoque VCP |
| `dbo.vwExcel_inventarioajuste` | Export Excel: ajustes de inventario |
| `dbo.vwExcel_OcupacaoEstoqueDiarioVCP` | Export Excel: ocupacao de estoque diaria VCP |
| `dbo.vwExcel_pedido_volume_sintetico` | Export Excel: resumo de pedidos/volumes |
| `dbo.vwExcel_pedido_volume_sintetico_rj` | Export Excel: resumo pedidos RJ |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldo` | Indicador: saldo por endereco/produto/lote |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldo_250319` | Indicador: snapshot saldo mar/2025 |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldoLpn` | Indicador: saldo com LPN |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldoStage` | Indicador: saldo em staging area |
| `dbo.vwIndicador_Expedicao` | Indicador: medicoes de expedicao |
| `dbo.vwIndicador_Expedicao_231130` | Indicador: expedicao snapshot nov/2023 |
| `dbo.vwIndicador_Recebimento` | Indicador: medicoes de recebimento |
| `dbo.vwIndicador_Recebimento_240403` | Indicador: recebimento snapshot abr/2024 |
| `dbo.vwIndicador_Recebimento_teste` | View de teste recebimento |
| `dbo.vwIndicador_Recebimento_teste2` | View de teste recebimento v2 |

### MER — Entidades e Atributos

#### `dbo.balanca_pedido_volume`

Linhas: **2.482.516**  
PK: `id_balanca_pedido_volume`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_balanca_pedido_volume` (PK) | bigint(19) | N |  |
| `cod_pedido` | int(10) | N |  |
| `volume` | int(10) | N |  |
| `id_container` | int(10) | S |  |
| `cod_container` | int(10) | S |  |
| `dt_inclusao` | datetime | N |  |
| `numero_titulo` | nvarchar(20) | S |  |
| `cod_pedido_polo` | nvarchar(30) | S |  |
| `cod_pedido_documento` | uniqueidentifier | S |  |
| `tipo_volume` | nvarchar(40) | S |  |
| `cod_barra` | nvarchar(60) | N |  |
| `tp_integrado` | bit | N |  |
| `sku` | varchar(20) | S |  |
| `descricao` | varchar(80) | S |  |
| `lote` | varchar(50) | S |  |
| `sku_cliente` | varchar(20) | S |  |
| `tara` | numeric(18,3) | S |  |
| `kg_insumo` | numeric(18,3) | S |  |

#### `dbo.container`

Linhas: **521.062**  
PK: `id_container`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_container` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cd_lpn` | nvarchar(20) | S |  |
| `tp_container` | int(10) | S |  |
| `ds_container` | nvarchar(100) | S |  |
| `cd_datalogger` | nvarchar(30) | S |  |
| `tp_integrado` | bit | S |  |

#### `dbo.ContainerMovimentoVolume`

Linhas: **318**  
PK: `id_ContainerMovimentoVolume`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_ContainerMovimentoVolume` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cod_pedido` | int(10) | S |  |
| `volume` | int(10) | S |  |
| `cod_container_origem` | nvarchar(20) | N |  |
| `cod_container_destino` | nvarchar(20) | N |  |

#### `dbo.Deadlock_log`

Linhas: **23.498**  
PK: `serialkey`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `serialkey` (PK) | int(10) | N |  |
| `id_execucao` | int(10) | S |  |
| `adddate` | datetime | S |  |
| `session_id` | smallint(5) | S |  |
| `sql_text` | xml(MAX) | S |  |
| `sql_command` | xml(MAX) | S |  |
| `login_name` | nvarchar(128) | S |  |
| `original_login_name` | nvarchar(128) | S |  |
| `host_name` | nvarchar(128) | S |  |
| `program_name` | nvarchar(128) | S |  |
| `last_request_start_time` | datetime | S |  |
| `blocking_session_id` | int(10) | S |  |
| `wait_time_ms` | bigint(19) | S |  |
| `nested_level` | smallint(5) | S |  |
| `blocked_session_count` | int(10) | S |  |
| `open_transaction_count` | int(10) | S |  |
| `total_elapsed_time` | int(10) | S |  |
| `transaction_isolation_level` | varchar(50) | S |  |
| `deadlock_priority` | int(10) | S |  |
| `nt_user_name` | nvarchar(128) | S |  |
| `wait_info` | nvarchar(4000) | S |  |

#### `dbo.Embalagem`

Linhas: **20**  
PK: `id_embalagem`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_embalagem` (PK) | int(10) | N |  |
| `ds_embalagem` | nvarchar(100) | S |  |
| `tp_palete` | bit | S |  |
| `cm_altura` | int(10) | S |  |
| `cm_comprimento` | int(10) | S |  |
| `cm_largura` | int(10) | S |  |
| `kg_peso` | numeric(18,3) | S |  |
| `kg_insumo` | numeric(18,3) | S |  |

#### `dbo.estoque`

Linhas: **35.748**  
PK: `id_estoque`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_estoque` (PK) | bigint(19) | N |  |
| `dt_inclusao` | datetime | S |  |
| `nr_depositante` | int(10) | N |  |
| `ds_descricao` | nvarchar(200) | S |  |
| `cd_lote` | nvarchar(30) | N |  |
| `dt_fabricacao` | date | N |  |
| `dt_validade` | date | N |  |
| `nr_produtoportal` | int(10) | N |  |
| `nr_produtodelage` | int(10) | N |  |
| `cd_endereco` | nvarchar(20) | S |  |
| `cd_lpn` | nvarchar(20) | S |  |
| `qt_estoque` | decimal(22,5) | N |  |
| `ds_status` | nvarchar(10) | N |  |

#### `dbo.estoque_vtclog`

Linhas: **35.748**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_InventarioAtributos` | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cd_PosicaoCHP` | nvarchar(20) | S |  |
| `cd_PosicaoDelage` | nvarchar(20) | S |  |
| `cd_LPNDelage` | nvarchar(20) | S |  |
| `cd_PalletContagem` | nvarchar(30) | S |  |
| `cd_ProdutoContagem` | nvarchar(50) | S |  |
| `cd_LoteContagem` | nvarchar(50) | S |  |
| `SaldoOficial` | int(10) | S |  |
| `dt_FabricacaoContagem` | date | S |  |
| `dt_ValidadeContagem` | date | S |  |
| `nr_Produto_Portal` | int(10) | S |  |
| `nr_Produto_Delage` | nvarchar(60) | S |  |
| `STATUS` | varchar(9) | S |  |

#### `dbo.Impressoras`

Linhas: **6**  
PK: `id_Impressora`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Impressora` (PK) | int(10) | N |  |
| `ds_Impressora` | nvarchar(255) | N |  |
| `ip_Impressora` | nvarchar(15) | N |  |
| `nr_Porta` | int(10) | N |  |
| `tp_Status` | bit | N |  |

#### `dbo.Inventario_Datalogger`

Linhas: **80.664**  
PK: `id_Inventario_Datalogger`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Inventario_Datalogger` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cod_inventario` | int(10) | S |  |
| `id_lpn` | int(10) | S |  |
| `cd_DataLogger` | nvarchar(30) | S |  |

#### `dbo.lote_estoque_lpn_data`

Linhas: **36.117.772**  
PK: `id_lote_estoque_lpn_data`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_lote_estoque_lpn_data` (PK) | int(10) | N |  |
| `id_inclusao` | int(10) | N |  |
| `dt_inclusao` | date | N |  |
| `cod_operacao_logistica` | int(10) | N |  |
| `id_lote` | int(10) | N |  |
| `id_endereco` | int(10) | N |  |
| `id_lpn` | int(10) | N |  |
| `cd_lpn` | nvarchar(20) | S |  |
| `cod_pedido_entrada` | int(10) | S |  |
| `estoque` | money(19,4) | N |  |

#### `dbo.sysdiagrams`

Linhas: **0**  
PK: `diagram_id`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `name` | nvarchar(128) | N |  |
| `principal_id` | int(10) | N |  |
| `diagram_id` (PK) | int(10) | N |  |
| `version` | int(10) | S |  |
| `definition` | varbinary(MAX) | S |  |

### DER — Relacionamentos

Sem FKs formais declaradas (integridade por aplicacao). Relacionamentos logicos:

    lote_estoque_lpn_data.cod_pedido -> balanca_pedido_volume.cod_pedido
    lote_estoque_lpn_data.id_container -> container.id_container
    estoque.estoque_vtclog (espelho direto)

### Regras de Negocio Inferidas

- `lote_estoque_lpn_data` (36M linhas) e a tabela de fatos central — cada linha representa saldo de 1 lote em 1 LPN em 1 endereco em 1 momento
- `balanca_pedido_volume` registra o peso real de cada volume de pedido (integrado com balancas fisicas)
- `container` usa `cd_lpn` como codigo de LPN — campo principal de rastreabilidade
- Views `vwExcel_*` sao usadas diretamente por Power BI / Excel como fonte de dados
- Views `vwIndicador_*` alimentam dashboards operacionais em tempo real
- Views com sufixo de data (ex: `_230806`) sao snapshots historicos congelados

---

## 3. VTCLOG_EXT

**Proposito:** WMS VTCLog — extensao para filial/campus adicional (schema espelho do VTCLOG com volume menor, provavelmente filial RJ ou segundo campus GRU). Compartilha as mesmas 29 views analiticas do VTCLOG principal.

**Schema:** `dbo` (tabelas) / `vw` (view materializada) | **Tabelas:** 10 | **Views:** 29

### Visao Geral — Tabelas

| Tabela | Linhas | Descricao |
|--------|--------|-----------|
| `dbo.caixa_esteira_221130` | 17 | Caixas da esteira (snapshot nov/2022) |
| `dbo.container` | 138 | Containers/LPN fisicos (filial EXT) |
| `dbo.ContainerMovimentoVolume` | 13 | Movimentacao de volumes entre containers (EXT) |
| `dbo.Embalagem` | 11 | Tipos de embalagem (EXT) |
| `dbo.estoque` | 39.193 | Posicao de estoque atual (EXT — 39k registros) |
| `dbo.Impressoras` | 3 | Impressoras de etiqueta (EXT) |
| `dbo.Indicador_Expedicao` | 38 | Indicadores de expedicao EXT |
| `dbo.Indicador_Recebimento` | 63 | Indicadores de recebimento EXT |
| `dbo.Inventario_Datalogger` | 24 | Leituras de inventario datalogger EXT |
| `vw.produtoreferencia` | 5.056 | Referencia de produtos (schema vw) |

### Visao Geral — Views (29)

| View | Proposito Inferido |
|------|-------------------|
| `dbo.vw_EstoqueCHPxDelage` | Cruzamento estoque CHP x Delage EXT |
| `dbo.vw_InventarioDatalogger` | Inventario datalogger EXT |
| `dbo.vw_movimentacao_aberto` | Movimentacoes em aberto EXT |
| `dbo.vw_Operacao_Logistica` | Dashboard operacional EXT |
| `dbo.vw_PedidoContainerVolumes` | Volumes pedido/container EXT |
| `dbo.vw_PedidoVolumeReembaladoProdutolotes` | Reembalagem produto/lote EXT |
| `dbo.vw_PedidoVolumesReembalados` | Volumes reembalados EXT |
| `dbo.vw_PosicoesMovimentacao` | Posicoes movimentacao EXT |
| `dbo.vw_ProdutosVinculados` | Produtos vinculados EXT |
| `dbo.vw_usuarios` | Usuarios WMS EXT |
| `dbo.vw_VolumeLPN` | Volume/LPN EXT |
| `dbo.vw_VolumesEmbalagens` | Volumes x embalagens EXT |
| `dbo.vw_VolumesEmbalagens_221227` | View analitica EXT |
| `dbo.vwExcel_AcompanhamentoCadastroResumo` | View analitica EXT |
| `dbo.vwExcel_CadastroProdutos` | View analitica EXT |
| `dbo.vwExcel_Estoque` | Export Excel: estoque EXT |
| `dbo.vwExcel_ImpEstoqueCHPDelage` | View analitica EXT |
| `dbo.vwExcel_ProdutosLotes_CHPxDelage` | View analitica EXT |
| `dbo.vwExcel_ProdutosNaoIntegrados_CHPxPortal` | View analitica EXT |
| `dbo.vwExcel_VinculoCodDep_CHPxPortal` | View analitica EXT |
| `dbo.vwExcel_VinculoProdCli_PortalxCHP` | View analitica EXT |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldo` | Indicador saldo endereco/produto/lote EXT |
| `dbo.vwIndicador_EnderecoProdutoLoteSaldoLpn` | Indicador saldo com LPN EXT |
| `dbo.vwIndicador_Expedicao` | Indicador expedicao EXT |
| `dbo.vwIndicador_Recebimento` | View analitica EXT |
| `dbo.vwMetaBase_estoqueChpNaoCadastrado` | View analitica EXT |
| `dbo.vwMetaBase_ValidacaoFisicaSKU` | View analitica EXT |
| `dbo.vwMetaBase_VinculoProdutosSintetico` | View analitica EXT |
| `dbo.vwMetaBase_VinculoProdutosSintetico_comInativos` | View analitica EXT |

### MER — Entidades e Atributos

#### `dbo.caixa_esteira_221130`

Linhas: **17**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_caixa` | int(10) | N |  |
| `situacao` | tinyint(3) | N |  |
| `altura` | real(24) | N |  |
| `comprimento` | real(24) | N |  |
| `largura` | real(24) | N |  |
| `tamanho` | real(24) | S |  |
| `cod_distribuicao` | int(10) | N |  |
| `fator_empolamento` | money(19,4) | N |  |
| `descricao` | varchar(50) | S |  |
| `peso_maximo` | money(19,4) | S |  |
| `id_tipo` | int(10) | S |  |
| `peso_embalagem` | money(19,4) | S |  |
| `utiliza_no_pedido_agrupado` | bit | S |  |
| `eh_split` | bit | S |  |
| `id_def_tipo_volume_endereco` | smallint(5) | S |  |
| `peso_caixa` | money(19,4) | S |  |
| `tolerancia` | money(19,4) | S |  |
| `path` | varchar(255) | S |  |
| `id_def_grupo_caixa_esteira` | int(10) | S |  |
| `permite_HIV` | bit | N |  |
| `utiliza_na_caixa_volume_unico` | bit | N |  |

#### `dbo.container`

Linhas: **138**  
PK: `id_container`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_container` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cd_lpn` | nvarchar(20) | S |  |
| `tp_container` | int(10) | S |  |
| `ds_container` | nvarchar(100) | S |  |
| `cd_datalogger` | nvarchar(30) | S |  |
| `tp_integrado` | bit | S |  |

#### `dbo.ContainerMovimentoVolume`

Linhas: **13**  
PK: `id_ContainerMovimentoVolume`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_ContainerMovimentoVolume` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cod_pedido` | int(10) | S |  |
| `volume` | int(10) | S |  |
| `cod_container_origem` | nvarchar(20) | N |  |
| `cod_container_destino` | nvarchar(20) | N |  |

#### `dbo.Embalagem`

Linhas: **11**  
PK: `id_embalagem`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_embalagem` (PK) | int(10) | N |  |
| `ds_embalagem` | nvarchar(100) | S |  |
| `tp_palete` | bit | S |  |
| `cm_altura` | int(10) | S |  |
| `cm_comprimento` | int(10) | S |  |
| `cm_largura` | int(10) | S |  |

#### `dbo.estoque`

Linhas: **39.193**  
PK: `id_estoque`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_estoque` (PK) | bigint(19) | N |  |
| `dt_inclusao` | datetime | S |  |
| `nr_depositante` | int(10) | N |  |
| `ds_descricao` | nvarchar(200) | S |  |
| `cd_lote` | nvarchar(30) | N |  |
| `dt_fabricacao` | date | N |  |
| `dt_validade` | date | N |  |
| `nr_produtoportal` | int(10) | N |  |
| `nr_produtodelage` | int(10) | N |  |
| `cd_endereco` | nvarchar(20) | S |  |
| `cd_lpn` | nvarchar(20) | S |  |
| `qt_estoque` | decimal(22,5) | N |  |
| `ds_status` | nvarchar(10) | N |  |

#### `dbo.Impressoras`

Linhas: **3**  
PK: `id_Impressora`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Impressora` (PK) | int(10) | N |  |
| `ds_Impressora` | nvarchar(255) | N |  |
| `ip_Impressora` | nvarchar(15) | N |  |
| `nr_Porta` | int(10) | N |  |
| `tp_Status` | bit | N |  |

#### `dbo.Indicador_Expedicao`

Linhas: **38**  
PK: `id_Indicador_Expedicao`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Indicador_Expedicao` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `id_Sem` | uniqueidentifier | S |  |
| `Pedido_Cliente` | nvarchar(30) | S |  |
| `Pedido_WMS` | int(10) | S |  |
| `Data_Integracao` | datetime | S |  |
| `Data_Onda` | datetime | S |  |
| `Data_Separacao_Ini` | datetime | S |  |
| `Data_Separacao_Fim` | datetime | S |  |
| `Data_Finalizacao` | datetime | S |  |
| `Peso_Estimado` | real(24) | S |  |
| `Volumes_Estimados` | int(10) | S |  |
| `dt_Integracao` | datetime | S |  |
| `Data_Conferencia_Ini` | datetime | S |  |
| `Data_Conferencia_Fim` | datetime | S |  |

#### `dbo.Indicador_Recebimento`

Linhas: **63**  
PK: `id_Indicador_Recebimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Indicador_Recebimento` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `id_SrmDocumento` | uniqueidentifier | S |  |
| `Pedido_Polo` | nvarchar(30) | S |  |
| `Pedido_WMS` | int(10) | S |  |
| `Data_Conferencia_Ini` | datetime | S |  |
| `Data_Conferencia_Fim` | datetime | S |  |
| `Data_Armazenagem_Ini` | datetime | S |  |
| `Data_Armazenagem_Fim` | datetime | S |  |
| `dt_Integracao` | datetime | S |  |

#### `dbo.Inventario_Datalogger`

Linhas: **24**  
PK: `id_Inventario_Datalogger`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Inventario_Datalogger` (PK) | int(10) | N |  |
| `dt_inclusao` | datetime | S |  |
| `cod_inventario` | int(10) | S |  |
| `id_lpn` | int(10) | S |  |
| `cd_DataLogger` | nvarchar(30) | S |  |

#### `vw.produtoreferencia`

Linhas: **5.056**  
PK: `id_produtoreferencia`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_produtoreferencia` (PK) | bigint(19) | N |  |
| `dt_inclusao` | datetime | S |  |
| `id_produto` | nvarchar(200) | S |  |
| `nr_produto` | int(10) | S |  |
| `id_integracaoproduto` | int(10) | S |  |
| `cd_produtocliente` | nvarchar(30) | S |  |
| `cd_produto` | nvarchar(30) | S |  |
| `ds_produto` | nvarchar(200) | S |  |
| `ds_nomerazaosocial` | nvarchar(200) | S |  |
| `cd_lote` | nvarchar(30) | S |  |
| `cd_referencia` | nvarchar(30) | S |  |
| `ITEMCHARACTERISTIC1` | nvarchar(30) | S |  |
| `sku0` | nvarchar(30) | S |  |
| `sku1` | nvarchar(30) | S |  |
| `sku2` | nvarchar(30) | S |  |
| `sku3` | nvarchar(30) | S |  |
| `sku4` | nvarchar(30) | S |  |
| `sku5` | nvarchar(30) | S |  |
| `LOTTABLE01` | nvarchar(30) | S |  |
| `ITEMCHARACTERISTIC2` | nvarchar(30) | S |  |
| `qt_lotexcodcliente` | int(10) | S |  |
| `flag0` | int(10) | S |  |
| `flag1` | int(10) | S |  |
| `flag2` | int(10) | S |  |
| `flag3` | int(10) | S |  |
| `flag4` | int(10) | S |  |
| `flag5` | int(10) | S |  |

### DER — Relacionamentos

Sem FKs formais. Relacionamentos logicos identicos ao VTCLOG principal. Schema espelho com subconjunto de dados.

### Regras de Negocio Inferidas

- Schema estruturalmente identico ao VTCLOG com volume menor de dados
- `vw.produtoreferencia` indica schema separado `vw` para views materializadas
- Provavelmente replica dados de uma segunda operacao/campus (EXT = filial)
- As 29 views sao subconjunto das 40 views do VTCLOG (excluindo as especificas GRU/VCP)

---

## 4. WMSRX

**Proposito:** WMS principal da operacao GRU SP — sistema completo de gerenciamento de armazem. Contem toda logica de pedidos, picking, embalagem (LPN), estoque, movimentacao, inventario e integracao EDI. E o banco mais volumoso e critico do ambiente BI GRU.

**Schema:** `dbo` (principal) / `DPSP\disbbyweb` (schema de usuario especifico) | **Tabelas:** 713 | **Views:** 119

### Visao Geral — Top 26 Tabelas por Volume

| Tabela | Linhas | Grupo |
|--------|--------|-------|
| `dbo.lote_estoque_LPN_movimento` | 8.772.186 | LPN/Container |
| `dbo.pedido_item_volume` | 6.823.798 | Pedidos |
| `dbo.pedido_item_volume_lote` | 6.818.264 | Pedidos |
| `dbo.pedido_volume` | 6.708.881 | Pedidos |
| `dbo.pedido_volume_finalizacao_checkout` | 6.351.233 | Pedidos |
| `dbo.pedido_volume_reimpressao` | 5.277.106 | Pedidos |
| `dbo.log_erro_edi` | 1.933.328 | Log/EDI |
| `dbo.movimentacao_item_lote` | 1.750.863 | Movimentacao |
| `dbo.pedido_item_lote_endereco` | 1.014.073 | Pedidos |
| `dbo.pedido_item` | 914.828 | Pedidos |
| `dbo.LPN` | 831.201 | LPN/Container |
| `dbo.pedido` | 605.111 | Pedidos |
| `dbo.pedido_volume_retorno` | 534.380 | Pedidos |
| `dbo.container` | 525.423 | LPN/Container |
| `dbo.movimentacao_item` | 404.863 | Movimentacao |
| `dbo.movimentacao` | 388.788 | Movimentacao |
| `dbo.log_impressao_etiqueta` | 374.886 | Log |
| `dbo.inventario_item_conf_LPN` | 303.867 | Inventario |
| `dbo.pedido_item_volume_conf` | 288.406 | Pedidos |
| `dbo.Inventario_Mov` | 264.995 | Inventario |
| `dbo.pedido_volume_conf` | 234.520 | Pedidos |
| `dbo.inventario_item_conf_lpn_serie_numero` | 211.617 | Inventario |
| `dbo.endereco` | 146.456 | Armazem |
| `dbo.AspNetUserClaims` | 144.380 | Usuarios |
| `dbo.pedido_titulo` | 142.092 | Pedidos/Financeiro |
| `dbo.titulo` | 139.040 | Financeiro |

### Grupos de Tabelas por Prefixo (713 total)

| Prefixo | Qtd | Descricao do Grupo |
|---------|-----|-------------------|
| `def_` | 202 | Definicoes/configuracoes do WMS (parametros, tipos, regras) |
| `param_` | 76 | Parametros de operacao e integracao |
| `AspNet` | 55 | ASP.NET Identity (usuarios, roles, claims, tokens) |
| `pedido_` | 47 | Ciclo completo de pedidos (cabecalho, itens, volumes, lotes) |
| `produto_` | 32 | Catalogo de produtos, referencias, lotes |
| `log_` | 33 | Logs operacionais (EDI, impressao, erros) |
| `inventario_` | 23 | Inventario (conferencia, movimento, LPN) |
| `lote_` | 21 | Lotes de produto (estoque, LPN, validade) |
| `entidade_` | 18 | Entidades do sistema (clientes, fornecedores) |
| `endereco_` | 17 | Enderecos de estoque (posicoes no armazem) |
| `grupo_` | 13 | Grupos de produto/operacao |
| `caixa_` | 13 | Tipos de caixa/embalagem (esteira sorter) |
| `ordem_` | 12 | Ordens de servico e producao |
| `temp_` | 10 | Tabelas temporarias |
| `lpn_` | 9 | LPN (License Plate Number) — rastreabilidade |
| `material_` | 8 | Materiais e insumos |
| `log_` | 6 | Logs complementares |
| `edi_` | 6 | Integracao EDI com clientes |
| `entrada_` | 5 | Entradas de mercadoria/recebimento |
| `funcionario_` | 5 | Cadastro e configuracao de funcionarios |
| `decanting_` | 5 | Operacao de decanting (fracionamento) |
| `painel_` | 5 | Paineis operacionais/monitores |
| Outros | ~50 | Tabelas diversas (agrupamento, arvore, edi, etc) |

### Views (119)

119 views que incluem subconjunto das mesmas vwExcel_* e vwIndicador_* do VTCLOG, mais views proprias do WMSRX para relatorios de picking, expedicao e integracao.

### MER — Tabelas Chave (detalhadas)

#### `dbo.pedido`

Linhas: **605.111**  
PK: `cod_pedido`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_pedido` (PK) | int(10) | N |  |
| `cod_prenota` | int(10) | S |  |
| `cod_entidade` | int(10) | N |  |
| `operacao` | smallint(5) | N |  |
| `cod_situacao` | int(10) | N |  |
| `cod_pendencia` | tinyint(3) | S |  |
| `digitacao` | smalldatetime | N |  |
| `termino_digitacao` | smalldatetime | S |  |
| `data_liberacao` | smalldatetime | S |  |
| `prenota` | smalldatetime | S |  |
| `encerramento_PN` | smalldatetime | S |  |
| `faturamento` | smalldatetime | S |  |
| `quem_liberou` | varchar(30) | S |  |
| `quem_digitou` | varchar(30) | S |  |
| `cod_origem_ped` | tinyint(3) | N |  |
| `cod_pedido_polo` | varchar(30) | S |  |
| `volumes` | int(10) | S |  |
| `valor_total` | money(19,4) | S |  |
| `cod_operacao_logistica` | int(10) | N |  |
| `obs_PN` | varchar(MAX) | S |  |
| `cod_entrada_caminhao` | int(10) | S |  |
| `data_exportacao` | datetime | S |  |
| `valor_mercadoria` | money(19,4) | S |  |
| `peso` | real(24) | S |  |
| `cod_suboperacao` | smallint(5) | S |  |
| `id_def_motivo_subOperacao` | smallint(5) | S |  |
| `dataExportacaoTMS` | smalldatetime | S |  |
| `id_cancelamento` | int(10) | S |  |
| `data_solicitacao_cancelamento` | datetime | S |  |
| `data_confirmacao_cancelamento` | datetime | S |  |
| `cod_situacao_ant` | int(10) | S |  |
| `cod_prenota_cancelada` | int(10) | S |  |
| `data_finalizacao_prenota` | smalldatetime | S |  |
| `cod_status_exportacao` | int(10) | S |  |
| `cod_onda` | int(10) | S |  |
| `data_limite_separacao` | datetime | S |  |
| `cod_transportadora` | int(10) | S |  |
| `prazo_maximo` | smalldatetime | S |  |
| `cod_forma_captacao` | int(10) | S |  |
| `cod_ciclo` | int(10) | S |  |
| `cod_setor` | varchar(10) | S |  |
| `data_saida_transp` | smalldatetime | S |  |
| `integra_separacao_automatizada` | bit | S |  |
| `obs_liberacao` | varchar(300) | S |  |
| `id_tipo_atendimento_pedido` | int(10) | S |  |
| `urgente` | bit | S |  |
| `cod_modalidade` | int(10) | S |  |
| `prioridade` | bit | N |  |
| `cod_curva` | int(10) | S |  |
| `id_contrato` | int(10) | S |  |
| `data_liberacao_picking` | datetime | S |  |
| `fatura` | bit | S |  |
| `data_conferencia_nf` | datetime | S |  |
| `quem_conferiu_nf` | varchar(50) | S |  |
| `dias_entrega` | int(10) | S |  |
| `quantidade_volume_termico` | int(10) | S |  |
| `id_endereco_intermediario` | int(10) | S |  |
| `sequencia_caminho` | varchar(6) | S |  |
| `temperatura` | money(19,4) | S |  |
| `id_turno_entrega` | int(10) | S |  |
| `recebedor` | varchar(100) | S |  |
| `id_circuito_doca` | int(10) | S |  |
| `id_regiao_entrega` | int(10) | S |  |
| `prazo_maximo_carregamento` | smalldatetime | S |  |
| `imprime_fatura` | bit | N |  |
| `cae` | bit | N |  |
| `data_recusa` | datetime | S |  |
| `motivo_recusa` | varchar(100) | S |  |
| `operativa` | int(10) | S |  |
| `circuito_doca` | bit | S |  |
| `cod_canal` | int(10) | S |  |
| `cod_letra` | int(10) | S |  |
| `canal_setor` | varchar(50) | S |  |
| `cobranca` | bit | S |  |
| `cod_pedido_cliente` | varchar(50) | S |  |
| `cod_pedido_documento` | varchar(50) | S |  |
| `convenio` | varchar(50) | S |  |
| `data_liberacao_carregamento` | smalldatetime | S |  |
| `faixa_entrega` | varchar(50) | S |  |
| `forma_pagamento` | varchar(100) | S |  |
| `numero_cai` | varchar(50) | S |  |
| `obs_documento` | varchar(500) | S |  |
| `pedido_ext` | varchar(50) | S |  |
| `resolucao` | varchar(200) | S |  |
| `telefone_recebedor` | varchar(50) | S |  |
| `usuario_documento` | varchar(50) | S |  |
| `vencimento_cai` | smalldatetime | S |  |
| `cod_tipo_venda` | int(10) | S |  |
| `cod_destinatario` | int(10) | S |  |
| `obs_inventario` | varchar(255) | S |  |
| `etiqueta_licitacao` | bit | N |  |
| `cod_dest_substituto` | int(10) | S |  |
| `data_impressao_documento` | smalldatetime | S |  |
| `id_tipo_Armazenamento` | int(10) | S |  |

Relacionamentos (FK):
- `cod_ciclo` -> `def_ciclo_pedido.cod_ciclo`
- `cod_curva` -> `def_curva.cod_curva`
- `cod_entidade` -> `entidade.cod_entidade`
- `cod_forma_captacao` -> `def_forma_captacao.cod_forma_captacao`
- `cod_modalidade` -> `def_modalidade_pedido.cod_modalidade`
- `cod_onda` -> `onda.cod_onda`
- `cod_operacao_logistica` -> `operacao_logistica.cod_operacao_logistica`
- `cod_origem_ped` -> `def_origem_ped.cod_origem_ped`
- `cod_pendencia` -> `def_pendencia.cod_pendencia`
- `cod_setor` -> `setor_venda.cod_setor`
- `cod_situacao` -> `def_situacao.cod_situacao`
- `cod_situacao_ant` -> `def_situacao.cod_situacao`
- `cod_status_exportacao` -> `def_status_exportacao.cod_status_exportacao`
- `cod_suboperacao` -> `def_suboperacao.cod_suboperacao`
- `cod_tipo_venda` -> `def_tipo_venda.cod_tipo_venda`
- `id_cancelamento` -> `def_cancelamento.id_cancelamento`
- `id_circuito_doca` -> `def_circuito_doca.id_circuito_doca`
- `id_contrato` -> `contrato.id_contrato`
- `id_def_motivo_subOperacao` -> `def_motivo_subOperacao.id_def_motivo_subOperacao`
- `id_endereco_intermediario` -> `endereco.id_endereco`
- `id_regiao_entrega` -> `def_regiao_entrega.id_regiao_entrega`
- `id_tipo_atendimento_pedido` -> `def_tipo_atendimento_pedido.id_tipo_atendimento_pedido`
- `id_turno_entrega` -> `def_turno_entrega.id_turno_entrega`
- `operacao` -> `def_operacao.operacao`
- `operativa` -> `def_operativa.cod_operativa`

#### `dbo.pedido_item`

Linhas: **914.828**  
PK: `cod_pedido, cod_produto`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_pedido` (PK) | int(10) | N |  |
| `cod_produto` (PK) | int(10) | N |  |
| `quantidade` | money(19,4) | N |  |
| `separado` | money(19,4) | N |  |
| `cod_motivo` | int(10) | S |  |
| `numero_item` | int(10) | S |  |
| `quem_cortou` | varchar(30) | S |  |
| `obs` | varchar(255) | S |  |
| `ordem_conf` | int(10) | S |  |
| `validade_minima` | int(10) | S |  |
| `cod_produto_KIT` | int(10) | S |  |
| `estimativa_corte_qtd` | money(19,4) | S |  |
| `estimativa_corte_data` | datetime | S |  |
| `corta_kit_total` | bit | S |  |
| `erro_alocacao` | bit | S |  |
| `medida_padrao` | money(19,4) | S |  |
| `quantidade_variavel` | money(19,4) | S |  |
| `separado_variavel` | money(19,4) | S |  |
| `id_pedido_item_multivolume` | int(10) | S |  |
| `origem` | bit | S |  |
| `destino` | bit | S |  |
| `tipo_armazenamento` | int(10) | S |  |
| `tirar_cod_barras` | bit | S |  |
| `obs_item_inventario` | varchar(255) | S |  |

Relacionamentos (FK):
- `cod_motivo` -> `def_motivo_item.cod_motivo`
- `cod_pedido` -> `pedido.cod_pedido`
- `cod_produto` -> `produto.cod_produto`
- `id_pedido_item_multivolume` -> `pedido_item_multivolume.id_pedido_item_multivolume`
- `tipo_armazenamento` -> `def_tipo_armazenamento_especial.cod_tipo_armazenamento_especial`

#### `dbo.pedido_volume`

Linhas: **6.708.881**  
PK: `cod_pedido, Volume`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_pedido` (PK) | int(10) | N |  |
| `Volume` (PK) | int(10) | N |  |
| `Inicio` | datetime | S |  |
| `Encerramento` | datetime | S |  |
| `Tipo_caixa` | int(10) | S |  |
| `checkout` | bit | N |  |
| `cod_caixa_retornavel` | varchar(30) | S |  |
| `data_retorno_caixa` | datetime | S |  |
| `quem_retornou_caixa` | varchar(30) | S |  |
| `data_volume_embarcado` | datetime | S |  |
| `espelho` | int(10) | S |  |
| `quem_embarcou` | varchar(50) | S |  |
| `cod_prenota_rel` | int(10) | S |  |
| `volume_rel` | int(10) | S |  |
| `nao_confere_cf` | bit | S |  |
| `data_volume_nao_embarcado` | datetime | S |  |
| `reimpressao` | int(10) | S |  |
| `usuario_impressao_embarque` | varchar(50) | S |  |
| `data_impressao_embarque` | smalldatetime | S |  |
| `cod_container` | int(10) | S |  |
| `cod_pedido_rel` | int(10) | S |  |
| `quem_reimprimiu` | varchar(30) | S |  |
| `quem_liberou_bloqueio` | varchar(50) | S |  |
| `data_liberacao_bloqueio` | smalldatetime | S |  |
| `quem_gerou` | varchar(50) | S |  |
| `conferencia` | datetime | S |  |
| `data_cadastro` | datetime | S |  |
| `quem_criou` | varchar(30) | S |  |
| `tipo_pallet` | smallint(5) | S |  |
| `tipo_lpn` | smallint(5) | S |  |
| `id_lpn` | int(10) | S |  |
| `id_endereco_colmeia` | int(10) | S |  |
| `eh_split` | bit | S |  |
| `data_encerramento_split` | datetime | S |  |
| `data_inicio_split` | datetime | S |  |
| `visualiza_lote_rf` | bit | N |  |
| `quem_associou_lpn` | varchar(50) | S |  |
| `operador_container` | int(10) | S |  |
| `data_container` | datetime | S |  |
| `id_def_motivo_checkout` | int(10) | S |  |
| `visualiza_lote_separado_rf` | bit | S |  |
| `RFID` | varchar(30) | S |  |
| `define_identificador` | bit | N |  |
| `endereco_div` | varchar(50) | S |  |
| `id_endereco_packing` | int(10) | S |  |
| `data_inicio_packing` | datetime | S |  |
| `data_encerramento_packing` | datetime | S |  |
| `quantidade_envios` | int(10) | S |  |
| `data_liberacao_endereco_transitorio` | datetime | S |  |
| `peso_caixa` | money(19,4) | S |  |
| `data_finalizacao` | datetime | S |  |
| `quem_finalizou` | varchar(50) | S |  |
| `tipo_caixa_secundaria` | int(10) | S |  |
| `peso_caixa_secundaria` | int(10) | S |  |
| `volume_extra` | bit | S |  |
| `data_reenvio_integracao` | datetime | S |  |
| `quem_reenviou_integracao` | int(10) | S |  |
| `msg_erro_integracao` | varchar(500) | S |  |
| `data_finalizacao_em_massa` | datetime | S |  |
| `quem_finalizou_em_massa` | varchar(50) | S |  |
| `data_exportacao_sorter` | datetime2 | S |  |
| `pedido_armazenagem_knapp` | int(10) | S |  |
| `permite_armazenagem_automatizada` | bit | N |  |
| `cod_operador_packing` | int(10) | S |  |
| `peso` | real(24) | S |  |
| `altura` | real(24) | S |  |
| `largura` | real(24) | S |  |
| `comprimento` | real(24) | S |  |
| `id_endereco_separacao_transitorio` | int(10) | S |  |
| `id_onda_volume` | int(10) | S |  |
| `sequencia` | int(10) | S |  |
| `cod_liberacao_volume` | int(10) | S |  |
| `volumetria` | real(24) | S |  |
| `lpn_transito` | int(10) | S |  |
| `id_consolidacao` | int(10) | S |  |
| `data_consolidacao` | smalldatetime | S |  |
| `quem_consolidou` | int(10) | S |  |
| `id_endereco_consolidacao` | int(10) | S |  |
| `checkout_rasteabilidade` | bit | N |  |
| `id_param_endereco_div` | int(10) | S |  |
| `troca_caixa` | bit | S |  |
| `id_endereco_expedicao` | int(10) | S |  |
| `autoriza_movimentacao` | bit | N |  |

Relacionamentos (FK):
- `cod_container` -> `container.cod_container`
- `cod_liberacao_volume` -> `liberacao_volume.cod_liberacao_volume`
- `cod_operador_packing` -> `entidade.cod_entidade`
- `cod_pedido` -> `pedido.cod_pedido`
- `cod_pedido_rel` -> `pedido.cod_pedido`
- `id_consolidacao` -> `consolidacao.id_consolidacao`
- `id_def_motivo_checkout` -> `def_motivo_checkout.id_def_motivo_checkout`
- `id_endereco_colmeia` -> `endereco.id_endereco`
- `id_endereco_expedicao` -> `endereco.id_endereco`
- `id_lpn` -> `LPN.id_LPN`
- `id_onda_volume` -> `onda_volume.id_onda_volume`
- `id_param_endereco_div` -> `param_endereco_div.id_param_endereco_div`
- `pedido_armazenagem_knapp` -> `pedido.cod_pedido`
- `quem_reenviou_integracao` -> `entidade.cod_entidade`
- `tipo_pallet` -> `def_tipo_volume_endereco.id_tipo_volume_endereco`

#### `dbo.pedido_item_volume`

Linhas: **6.823.798**  
PK: `id_pedido_item_volume`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_pedido_item_volume` (PK) | int(10) | N |  |
| `id_pedido_item_lote_endereco` | int(10) | N |  |
| `volume` | int(10) | N |  |
| `id_lote` | int(10) | N |  |
| `id_lote_dest` | int(10) | N |  |
| `id_endereco_origem` | int(10) | N |  |
| `id_endereco_dest` | int(10) | N |  |
| `quantidade` | money(19,4) | N |  |
| `movimento` | int(10) | S |  |
| `cod_operador` | int(10) | S |  |
| `cod_operador_checkout` | int(10) | S |  |
| `conferido` | smallint(5) | S |  |
| `data_separacao` | datetime | S |  |
| `data_InicioCheckout` | datetime | S |  |
| `data_FimCheckout` | datetime | S |  |
| `Dif_CheckOut` | money(19,4) | S |  |
| `cod_separador` | int(10) | S |  |
| `falta` | bit | S |  |
| `lote_log` | varchar(50) | S |  |
| `data_cadastro` | datetime | S |  |
| `quantidade_conferencia` | int(10) | S |  |
| `id_lpn` | int(10) | S |  |
| `id_endereco_box` | int(10) | S |  |
| `emb_compra` | money(19,4) | S |  |
| `quantidade_colmeia` | money(19,4) | S |  |
| `data_vinculo_container` | datetime | S |  |
| `id_endereco_separacao_transitorio` | int(10) | S |  |
| `data_liberacao_endereco_transitorio` | datetime | S |  |
| `cod_entidade_liberacao` | int(10) | S |  |
| `cod_entidade_vinculo_container` | int(10) | S |  |
| `peso_item` | money(19,4) | S |  |
| `quantidade_variavel` | money(19,4) | S |  |
| `estimativa_falta` | money(19,4) | S |  |
| `autoriza_movimentacao` | bit | N |  |
| `usuario_movimentacao` | nvarchar(50) | S |  |

Relacionamentos (FK):
- `cod_entidade_liberacao` -> `entidade.cod_entidade`
- `cod_entidade_vinculo_container` -> `entidade.cod_entidade`
- `cod_separador` -> `entidade.cod_entidade`
- `id_endereco_box` -> `endereco.id_endereco`
- `id_lpn` -> `LPN.id_LPN`
- `id_pedido_item_lote_endereco` -> `pedido_item_lote_endereco.id_pedido_item_lote_endereco`

#### `dbo.LPN`

Linhas: **831.201**  
PK: `id_LPN`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_LPN` (PK) | int(10) | N |  |
| `numero` | varchar(20) | S |  |
| `data_cadastro` | smalldatetime | N |  |
| `cod_usuario` | int(10) | N |  |
| `cod_operacao_logistica` | int(10) | S |  |
| `id_endereco` | int(10) | S |  |
| `id_LPN_pai` | int(10) | S |  |
| `id_def_tipo_lpn` | int(10) | N |  |
| `id_def_situacao_lpn` | int(10) | N |  |
| `id_caixa` | int(10) | S |  |
| `id_contrato` | int(10) | S |  |
| `numero_slot` | int(10) | S |  |
| `cod_entidade` | int(10) | S |  |
| `cod_rota` | varchar(7) | S |  |

Relacionamentos (FK):
- `cod_entidade` -> `entidade.cod_entidade`
- `cod_operacao_logistica` -> `operacao_logistica.cod_operacao_logistica`
- `cod_rota` -> `rota.cod_rota`
- `cod_usuario` -> `entidade.cod_entidade`
- `id_caixa` -> `caixa_esteira.id_caixa`
- `id_contrato` -> `contrato.id_contrato`
- `id_def_situacao_lpn` -> `def_situacao_lpn.id_def_situacao_lpn`
- `id_def_tipo_lpn` -> `def_tipo_lpn.id_def_tipo_lpn`
- `id_endereco` -> `endereco.id_endereco`
- `id_LPN_pai` -> `LPN.id_LPN`

#### `dbo.lote_estoque_LPN_movimento`

Linhas: **8.772.186**  
PK: `id_lote_estoque_LPN_movimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_lote_estoque_LPN_movimento` (PK) | int(10) | N |  |
| `cod_produto` | int(10) | S |  |
| `id_pedido_item_volume` | int(10) | S |  |
| `id_pedido_item_lote_endereco` | int(10) | S |  |
| `id_mov` | int(10) | S |  |
| `id_LPN_origem` | int(10) | S |  |
| `id_LPN_destino` | int(10) | S |  |
| `id_endereco_origem` | int(10) | S |  |
| `id_endereco_destino` | int(10) | S |  |
| `id_lote_origem` | int(10) | S |  |
| `id_lote_destino` | int(10) | S |  |
| `validade_lote_destino` | smalldatetime | S |  |
| `id_acao` | int(10) | S |  |
| `qtd_movimento` | money(19,4) | S |  |
| `estoque_lote_origem_antes` | money(19,4) | S |  |
| `estoque_lote_origem_depois` | money(19,4) | S |  |
| `estoque_lote_destino_antes` | money(19,4) | S |  |
| `estoque_lote_destino_depois` | money(19,4) | S |  |
| `estoque_lote_ender_origem_antes` | money(19,4) | S |  |
| `estoque_lote_ender_origem_depois` | money(19,4) | S |  |
| `estoque_lote_ender_destino_antes` | money(19,4) | S |  |
| `estoque_lote_ender_destino_depois` | money(19,4) | S |  |
| `estoque_lpn_origem_antes` | money(19,4) | S |  |
| `estoque_lpn_origem_depois` | money(19,4) | S |  |
| `estoque_lpn_destino_antes` | money(19,4) | S |  |
| `estoque_lpn_destino_depois` | money(19,4) | S |  |
| `estoque_total_antes` | money(19,4) | S |  |
| `estoque_total_depois` | money(19,4) | S |  |
| `data_movimento` | datetime | S |  |
| `responsavel` | varchar(50) | S |  |
| `cod_operacao_logistica` | int(10) | S |  |
| `aplicacao` | varchar(100) | S |  |

Relacionamentos (FK):
- `cod_operacao_logistica` -> `operacao_logistica.cod_operacao_logistica`
- `cod_produto` -> `produto.cod_produto`
- `id_acao` -> `def_acao.id_acao`

#### `dbo.movimentacao`

Linhas: **388.788**  
PK: `cod_movimentacao`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_movimentacao` (PK) | int(10) | N |  |
| `cod_pedido_armazenamento` | int(10) | S |  |
| `cod_pedido_entrada` | int(10) | S |  |
| `data_movimentacao` | smalldatetime | N |  |
| `data_exportacao` | smalldatetime | S |  |
| `data_cadastro` | smalldatetime | N |  |
| `cod_operacao_logistica` | int(10) | N |  |
| `usuario` | varchar(50) | N |  |
| `cod_pedido_cancelamento` | int(10) | S |  |
| `cod_motivo` | int(10) | S |  |

Relacionamentos (FK):
- `cod_motivo` -> `def_motivo_movimentacao.cod_motivo`
- `cod_operacao_logistica` -> `operacao_logistica.cod_operacao_logistica`
- `cod_pedido_entrada` -> `pedido.cod_pedido`

#### `dbo.movimentacao_item`

Linhas: **404.863**  
PK: `cod_movimentacao, cod_produto`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_movimentacao` (PK) | int(10) | N |  |
| `cod_produto` (PK) | int(10) | N |  |
| `quantidade` | money(19,4) | N |  |

Relacionamentos (FK):
- `cod_movimentacao` -> `movimentacao.cod_movimentacao`
- `cod_produto` -> `produto.cod_produto`

#### `dbo.movimentacao_item_lote`

Linhas: **1.750.863**  
PK: `cod_movimentacao_item_lote`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_movimentacao_item_lote` (PK) | int(10) | N |  |
| `cod_movimentacao` | int(10) | N |  |
| `cod_produto` | int(10) | N |  |
| `quantidade` | money(19,4) | N |  |
| `id_lote_origem` | int(10) | N |  |
| `id_lote_dest` | int(10) | S |  |
| `id_lote_classificacao_origem` | int(10) | S |  |
| `id_lote_classificacao_dest` | int(10) | S |  |

Relacionamentos (FK):
- `cod_movimentacao` -> `movimentacao_item.cod_movimentacao`
- `cod_produto` -> `movimentacao_item.cod_produto`
- `id_lote_classificacao_dest` -> `def_lote_classificacao.id_lote_classificacao`
- `id_lote_classificacao_origem` -> `def_lote_classificacao.id_lote_classificacao`
- `id_lote_dest` -> `lote.id_lote`
- `id_lote_origem` -> `lote.id_lote`

#### `dbo.endereco`

Linhas: **146.456**  
PK: `id_endereco`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_endereco` (PK) | int(10) | N |  |
| `id_def` | int(10) | N |  |
| `nivel` | int(10) | N |  |
| `endereco` | varchar(50) | N |  |
| `id_pai` | int(10) | S |  |
| `qtd_caixa` | int(10) | S |  |
| `endereco_completo` | varchar(50) | S |  |
| `id_lote_classificacao` | int(10) | N |  |
| `permite_inventario` | smallint(5) | N |  |
| `id_tipo_volume` | smallint(5) | S |  |
| `id_tipo_acesso_endereco` | smallint(5) | S |  |
| `id_tipo_Armazenamento` | smallint(5) | S |  |
| `endereco_completo_3D` | varchar(100) | S |  |
| `id_endereco_completo` | varchar(100) | S |  |
| `endereco_completo_pai` | varchar(100) | S |  |
| `refugo` | bit | S |  |
| `id_def_endereco_setor` | int(10) | S |  |
| `cod_situacao_endereco` | int(10) | S |  |
| `GetEnderecoPaiNivel` | int(10) | S |  |
| `id_endereco_div` | int(10) | S |  |
| `id_endereco_detalha_nivel` | int(10) | S |  |
| `id_endereco_agrupamento_kpi` | int(10) | S |  |
| `exibe_doca_kpi_recebimento` | bit | N |  |
| `permite_consolidacao` | bit | N |  |
| `permite_misturar_lote` | bit | N |  |
| `id_def_armazem` | int(10) | S |  |
| `permite_misturar_produto` | bit | N |  |

Relacionamentos (FK):
- `cod_situacao_endereco` -> `def_situacao_endereco.cod_situacao_endereco`
- `id_def` -> `def_endereco.id_def`
- `id_def_endereco_setor` -> `def_endereco_setor.id_def_endereco_setor`
- `id_endereco_agrupamento_kpi` -> `def_endereco_agrupamento_kpi.id_endereco_agrupamento_kpi`
- `id_endereco_detalha_nivel` -> `endereco.id_endereco`
- `id_endereco_div` -> `endereco.id_endereco`
- `id_lote_classificacao` -> `def_lote_classificacao.id_lote_classificacao`
- `id_pai` -> `endereco.id_endereco`
- `id_tipo_acesso_endereco` -> `def_tipo_acesso_endereco.id_tipo_acesso_endereco`
- `id_tipo_Armazenamento` -> `def_tipo_armazenamento_endereco.id_tipo_armazenamento_endereco`
- `id_tipo_volume` -> `def_tipo_volume_endereco.id_tipo_volume_endereco`
- `nivel` -> `def_endereco.nivel`

#### `dbo.container`

Linhas: **525.423**  
PK: `cod_container`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_container` (PK) | int(10) | N |  |
| `cod_situacao` | int(10) | S |  |
| `separador` | varchar(30) | S |  |
| `data_criacao` | datetime | S |  |
| `qtd_etiquetas` | int(10) | S |  |
| `numero_caixa` | varchar(100) | S |  |
| `tipo_caixa` | int(10) | S |  |
| `id_LPN` | int(10) | S |  |
| `data_exportacao` | smalldatetime | S |  |

Relacionamentos (FK):
- `cod_situacao` -> `def_situacao_container.cod_situacao_container`
- `id_LPN` -> `LPN.id_LPN`
- `tipo_caixa` -> `def_tipo_volume_cubagem.id_tipo`

#### `dbo.titulo`

Linhas: **139.040**  
PK: `cod_titulo`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_titulo` (PK) | int(10) | N |  |
| `numero_titulo` | varchar(20) | S |  |
| `serie_nf` | varchar(3) | S |  |
| `cod_titulo_polo` | varchar(30) | S |  |
| `cod_entidade` | int(10) | S |  |
| `volumes` | int(10) | S |  |
| `peso` | money(19,4) | S |  |
| `valor_total` | money(19,4) | S |  |
| `data_cadastro` | smalldatetime | S |  |
| `valor_mercadoria` | money(19,4) | S |  |
| `operacao` | int(10) | S |  |
| `chave_acesso` | varchar(50) | S |  |

Relacionamentos (FK):
- `cod_entidade` -> `entidade.cod_entidade`

#### `dbo.pedido_titulo`

Linhas: **142.092**  
PK: `cod_pedido, cod_titulo`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `cod_pedido` (PK) | int(10) | N |  |
| `cod_titulo` (PK) | int(10) | N |  |

Relacionamentos (FK):
- `cod_pedido` -> `pedido.cod_pedido`
- `cod_titulo` -> `titulo.cod_titulo`

#### `dbo.inventario_item_conf_LPN`

Linhas: **303.867**  
PK: `id_inventario_item_conf_LPN`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_inventario_item_conf_LPN` (PK) | int(10) | N |  |
| `cod_inventario_item_conf` | int(10) | N |  |
| `id_def_tipo_volume_endereco` | smallint(5) | S |  |
| `id_LPN` | int(10) | N |  |
| `estoque` | money(19,4) | N |  |
| `conferido` | money(19,4) | S |  |
| `data_cadastro` | smalldatetime | N |  |
| `id_LPN_destino` | int(10) | S |  |
| `snapshot` | money(19,4) | S |  |
| `stock_correction` | money(19,4) | S |  |
| `conferido_variavel` | money(19,4) | S |  |
| `principal` | bit | N |  |
| `data_encerramento_lpn` | smalldatetime | S |  |

Relacionamentos (FK):
- `cod_inventario_item_conf` -> `inventario_item_conf.cod_inventario_item_conf`
- `id_def_tipo_volume_endereco` -> `def_tipo_volume_endereco.id_tipo_volume_endereco`
- `id_LPN` -> `LPN.id_LPN`

#### `dbo.log_impressao_etiqueta`

Linhas: **374.886**  
PK: `id_log_impressao_etiqueta`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_log_impressao_etiqueta` (PK) | int(10) | N |  |
| `id_tipo_etiqueta` | int(10) | N |  |
| `tabela_relacionada` | varchar(30) | N |  |
| `cod_relacionado` | varchar(30) | N |  |
| `quantidade` | int(10) | N |  |
| `data_impressao` | datetime | N |  |
| `quem_imprimiu` | varchar(30) | N |  |
| `volume` | int(10) | N |  |

Relacionamentos (FK):
- `id_tipo_etiqueta` -> `def_tipo_etiqueta.id_def_tipo_etiqueta`

### DER — Relacionamentos Principais

O WMSRX tem 905 FKs declaradas. Hierarquia central:

    pedido (1) --|< pedido_item (N)             [pedido.cod_pedido -> pedido_item.cod_pedido]
    pedido_item (1) --|< pedido_item_volume (N) [pedido_item.* -> pedido_item_volume.*]
    pedido_volume (1) --|< pedido_item_volume (N)
    LPN (1) --|< lote_estoque_LPN_movimento (N) [LPN.id_LPN -> lote_estoque_LPN_movimento.id_LPN]
    movimentacao (1) --|< movimentacao_item (N)
    movimentacao_item (1) --|< movimentacao_item_lote (N)

### Regras de Negocio Inferidas

- `def_*` (202 tabelas) sao tabelas de configuracao do WMS — alteradas apenas por administradores
- `LPN` (License Plate Number) e a unidade central de rastreabilidade: cada caixa tem 1 LPN
- `lote_estoque_LPN_movimento` e a tabela de fatos mais volumosa (8,7M) — historico de saldos por LPN
- `pedido_volume_finalizacao_checkout` (6,3M) registra o checkout de cada volume expedido
- `AspNet*` tabelas gerenciam autenticacao dos operadores do WMS (Identity Framework)
- `log_erro_edi` (1,9M) indica alto volume de rejeicoes/erros na integracao EDI
- Tabelas `*_conf` representam etapas de conferencia no fluxo de saida

---

## 5. WMSRX_EXT

**Proposito:** Schema espelho do WMSRX para uma filial/campus alternativo. Estrutura identica ao WMSRX (707 tabelas, -6 em relacao ao WMSRX principal). Contém os mesmos grupos de tabelas e 119 views.

**Schema:** `dbo` | **Tabelas:** 707 | **Views:** 119 | **FKs:** 905

### Diferenca em relacao ao WMSRX

| Metrica | WMSRX | WMSRX_EXT | Delta |
|---------|-------|-----------|-------|
| Tabelas | 713 | 707 | -6 tabelas |
| Colunas | 5.674 | 5.622 | -52 colunas |
| PKs | 643 | 641 | -2 PKs |
| FKs | 905 | 905 | identico |
| Views | 119 | 119 | identico |

### Estrutura

Identica ao WMSRX — consulte a secao [4. WMSRX](#4-wmsrx) para MER e DER completos.

### Regras de Negocio Inferidas

- Provavelmente representa uma segunda operacao GRU ou operacao de um cliente especifico
- As 6 tabelas ausentes indicam que algumas funcionalidades nao foram ativadas nesta instancia
- Volume de dados pode diferir — consultar diretamente o banco para row counts atuais

---

## 6. WMSRX_EXT2

**Proposito:** Terceiro campus/operacao do WMS GRU. Estrutura identica ao WMSRX principal (713 tabelas — mesmo numero que WMSRX, mais que WMSRX_EXT).

**Schema:** `dbo` | **Tabelas:** 713 | **Views:** 119 | **FKs:** 905

### Diferenca em relacao ao WMSRX

| Metrica | WMSRX | WMSRX_EXT2 | Delta |
|---------|-------|------------|-------|
| Tabelas | 713 | 713 | identico |
| Colunas | 5.674 | 5.674 | identico |
| PKs | 643 | 643 | identico |
| FKs | 905 | 905 | identico |
| Views | 119 | 119 | identico |

### Estrutura

100% identica ao WMSRX — consulte a secao [4. WMSRX](#4-wmsrx) para MER e DER completos.

### Regras de Negocio Inferidas

- WMSRX_EXT2 e um clone exato do WMSRX (versao mais recente que o EXT)
- Provavelmente representa o terceiro campus GRU ou uma operacao espelho para DR (disaster recovery)
- View `vw_VolumeLPN_EXT2` no VTCLOG referencia explicitamente este banco

---

## 7. dtbTransporte

**Proposito:** TMS (Transport Management System) VTCLog — banco central do sistema de transporte rodoviario. Contem todo o ciclo de vida de movimentos (coletas/entregas), CTe, MDFe, ocorrencias, dimensoes de carga, rastreamento, financeiro de frete e integracao com SEFAZ.

**Schema:** `dbo` | **Tabelas:** 1.542 | **Views:** 28 | **FKs:** 676

### Visao Geral — Top 30 Tabelas por Volume

| Tabela | Linhas | Grupo |
|--------|--------|-------|
| `dbo.tbdMovimentoProdutoNota` | 33.116.054 | Movimento/NF |
| `dbo.tbdTarefaAgendadaLog` | 1.177.149 | Sistema |
| `dbo.tbdOcorrenciaNota` | 1.125.612 | Ocorrencias |
| `dbo.tbdMovimentoComprovante` | 1.100.009 | Comprovantes |
| `dbo.tbdMovimentoHistorico` | 972.540 | Historico |
| `dbo.tb3402OcorrenciaNota` | 922.622 | Ocorrencias ANTT |
| `dbo.tbdDimensao` | 922.006 | Dimensoes/Frete |
| `dbo.tbdLoteCTeOcorrencia` | 813.167 | CTe/Lote |
| `dbo.LOG_LOGRADOURO` | 778.929 | Log/CEP |
| `dbo.tbdMovimentoNotaFiscal` | 763.897 | Movimento/NF |
| `dbo.tbdUltimaOcorrenciaNota` | 682.169 | Ocorrencias |
| `dbo.LOG_CEP` | 660.621 | Log/CEP |
| `dbo.tbdCTeMovimentoPdf` | 604.280 | CTe/PDF |
| `dbo.tbdMovimentoComentario` | 570.650 | Movimento |
| `dbo.tbdMovimentoSeguro` | 570.650 | Financeiro |
| `dbo.tbdMovimentoDespesaManifesto` | 570.650 | Manifesto |
| `dbo.tbdMovimentoDados` | 570.649 | Movimento |
| `dbo.tbdMovimentoDestinatario` | 570.649 | Movimento |
| `dbo.tbdMovimento` | 570.649 | Movimento (fato central) |
| `dbo.tbdFechamentoCliente` | 558.827 | Financeiro |
| `dbo.tbdMapeamentoComprovantes` | 533.752 | Comprovantes |
| `dbo.tbdOcorrenciaMovimento` | 494.590 | Ocorrencias |
| `dbo.tbdMovimentoFinanceiro` | 471.096 | Financeiro |
| `dbo.tbdManifestoMovimento` | 463.324 | Manifesto |
| `dbo.tbdMovimentoCTeOcorrencia` | 451.627 | CTe |
| `dbo.tbdLoteCTeMovimento` | 431.974 | CTe/Lote |
| `dbo.tbdNumeracaoCTe` | 426.733 | CTe |
| `dbo.tbdDimensaoColeta` | 422.850 | Dimensoes/Coleta |
| `dbo.tbdTrackingOrders` | 384.544 | Rastreamento |
| `dbo.tbdLoteCTe` | 346.124 | CTe/Lote |

### Grupos de Tabelas por Prefixo (1.542 total)

| Prefixo | Qtd | Descricao do Grupo |
|---------|-----|-------------------|
| `tbd` | 1.490 | Tabelas de dados (tbd = 'table data') — todo o dominio do TMS |
| `LOG_` | 17 | Logs do sistema (CEP, logradouro, integracao, erros) |
| `tb3` | 14 | Tabelas de integracao ANTT/RNTRC (norma 3402) |
| `temp*` | ~10 | Tabelas temporarias de processamento |
| Outros | ~11 | sysdiagrams, Deadlock_log, fatpo, dtpro, teste, etc |

### Views (28)

| View | Proposito Inferido |
|------|-------------------|
| `dbo.AcompanhamentoRJ` | View analitica TMS |
| `dbo.K_FATURAMENTO_VTC` | View analitica TMS |
| `dbo.vw_AcompanhamentoRJ` | View analitica TMS |
| `dbo.vw_Excel_EntregaAgente` | View analitica TMS |
| `dbo.vw_GNREConsulta` | View analitica TMS |
| `dbo.vw_ManifestoPercurso` | View analitica TMS |
| `dbo.vw_pedidosentregacomprovante` | View analitica TMS |
| `dbo.vw_pedidosentregapendente` | View analitica TMS |
| `dbo.vw_PessoaRelacionamentos` | View analitica TMS |
| `dbo.vw_TabelaPrecoPivot` | View analitica TMS |
| `dbo.vw_TrackingBlau` | View analitica TMS |
| `dbo.vw_ultima_ocorrencia` | View analitica TMS |
| `dbo.vwAgentes` | View analitica TMS |
| `dbo.vwClientePrivado` | View analitica TMS |
| `dbo.vwColetaPrazo` | View analitica TMS |
| `dbo.vwControleAUTFront` | View analitica TMS |
| `dbo.vwControleManifesto` | View analitica TMS |
| `dbo.vwControleViagens` | View analitica TMS |
| `dbo.vwDINAMICO` | View analitica TMS |
| `dbo.vwEntregaPrazo` | View analitica TMS |
| `dbo.vwExcel_AcompanhamentoAwb` | View analitica TMS |
| `dbo.vwIndicadorTorreFaturamentoNfs` | View analitica TMS |
| `dbo.vwIndicadorTorreFaturamentoNfsMinuta` | View analitica TMS |
| `dbo.vwRelacaoAWB` | View analitica TMS |
| `dbo.vwRelacaoBBraun` | View analitica TMS |
| `dbo.vwRelacaoMov` | View analitica TMS |
| `dbo.vwRelacaoMovimento` | View analitica TMS |
| `dbo.vwTransporteMS` | View analitica TMS |

### MER — Tabelas Chave (detalhadas)

#### `dbo.tbdMovimento`

Linhas: **570.649**  
PK: `id_Movimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` (PK) | int(10) | N |  |
| `id_Transportadora` | int(10) | S |  |
| `id_Cliente` | int(10) | S |  |
| `id_TransportadoraServico` | int(10) | S |  |
| `qt_prazoentrega` | char(6) | S |  |
| `id_Cidade` | int(10) | S |  |
| `nr_NotaFiscal` | char(255) | S |  |
| `ds_Cliente` | char(80) | S |  |
| `ds_Endereco` | varchar(70) | S |  |
| `ds_Bairro` | varchar(60) | S |  |
| `ds_Telefone` | varchar(30) | S |  |
| `ds_Ramal` | char(20) | S |  |
| `ds_Atencao` | varchar(30) | S |  |
| `ds_Setor` | varchar(30) | S |  |
| `vl_NotaFiscal` | decimal(36,4) | S |  |
| `cd_CGCCPF` | char(14) | S |  |
| `vl_Dimensao1` | decimal(12,4) | S |  |
| `kg_Mercadoria` | decimal(12,4) | S |  |
| `vl_Frete` | decimal(16,4) | S |  |
| `vl_Dimensao2` | decimal(12,4) | S |  |
| `tp_Frete` | char(1) | S |  |
| `vl_Dimensao3` | decimal(12,4) | S |  |
| `id_PedidoColeta` | int(10) | S |  |
| `qt_Volume` | int(10) | S |  |
| `vl_ExcedenteColeta` | decimal(12,4) | S |  |
| `dt_PrevisaoEntrega` | datetime | S |  |
| `ds_Receptor` | varchar(50) | S |  |
| `vl_ExcedenteEntrega` | decimal(12,4) | S |  |
| `vl_Coleta` | decimal(12,4) | S |  |
| `vl_Entrega` | decimal(12,4) | S |  |
| `nr_DocumentoReceptor` | char(15) | S |  |
| `vl_Peso` | decimal(12,4) | S |  |
| `dt_Recepcao` | datetime | S |  |
| `hr_Recepcao` | char(5) | S |  |
| `nr_Voo` | char(10) | S |  |
| `dt_Voo` | datetime | S |  |
| `nr_AWB` | char(20) | S |  |
| `id_Agente` | int(10) | S |  |
| `vl_TaxasDiversas` | decimal(12,4) | S |  |
| `vl_Redespacho` | decimal(12,4) | S |  |
| `hr_Partida` | char(5) | S |  |
| `pc_Desconto` | decimal(8,4) | S |  |
| `hr_Chegada` | char(5) | S |  |
| `tp_Desconto` | char(1) | S |  |
| `pc_Acrescimo` | decimal(8,4) | S |  |
| `tp_Aprovado` | char(1) | S |  |
| `tp_Acrescimo` | char(1) | S |  |
| `vl_Suframa` | decimal(12,4) | S |  |
| `vl_Pedagio` | decimal(12,4) | S |  |
| `vl_ADValorem` | decimal(16,4) | S |  |
| `vl_TDA` | decimal(12,4) | S |  |
| `hr_PrevisaoEntrega` | char(5) | S |  |
| `vl_FreteAereo` | decimal(12,4) | S |  |
| `pc_Comissao` | decimal(8,4) | S |  |
| `tp_TransferidoEmail` | char(1) | S |  |
| `tp_TransferidoDados` | char(1) | S |  |
| `ds_Aprovador` | varchar(50) | S |  |
| `dt_Coleta` | datetime | S |  |
| `hr_coleta` | char(6) | S |  |
| `ds_Coletor` | varchar(80) | S |  |
| `nr_DocumentoColetor` | varchar(30) | S |  |
| `cd_Placa` | char(8) | S |  |
| `cd_Servico` | char(10) | S |  |
| `vl_Desconto` | decimal(12,4) | S |  |
| `vl_Acrescimo` | decimal(12,4) | S |  |
| `id_CiaAerea` | int(10) | S |  |
| `tp_CAPAgente` | char(1) | S |  |
| `tp_CAPCiaAerea` | char(1) | S |  |
| `id_Remetente` | int(10) | S |  |
| `tp_Movimento` | char(1) | S |  |
| `qt_Kilometro` | int(10) | S |  |
| `tp_CarCliente` | char(1) | S |  |
| `tp_CarAgente` | char(1) | S |  |
| `ds_Remetente` | varchar(80) | S |  |
| `id_Seguradora` | int(10) | S |  |
| `id_Fiscal` | int(10) | S |  |
| `id_AgenteEmissor` | int(10) | S |  |
| `cd_IE` | char(20) | S |  |
| `ds_Embalagem` | varchar(30) | S |  |
| `cd_Cep` | char(8) | S |  |
| `cd_Estado` | char(2) | S |  |
| `kg_MercadoriaReal` | decimal(12,4) | S |  |
| `cm_Entrega` | varchar(255) | S |  |
| `cm_Coleta` | varchar(255) | S |  |
| `hr_Movimento` | char(5) | S |  |
| `ds_Usuario` | varchar(50) | S |  |
| `tp_RetiraMercadoria` | char(1) | S |  |
| `tp_PagaFrete` | char(1) | S |  |
| `dt_Movimento` | datetime | S |  |
| `id_Destinatario` | int(10) | S |  |
| `id_ClienteFaturamento` | int(10) | S |  |
| `cm_Movimento` | varchar(255) | S |  |
| `cm_Recepcao` | varchar(100) | S |  |
| `ds_Transportadora` | varchar(40) | S |  |
| `ds_Agente` | varchar(80) | S |  |
| `ds_CiaAerea` | varchar(80) | S |  |
| `tp_CalculaFreteAereo` | char(1) | S |  |
| `id_Servico` | int(10) | S |  |
| `tp_TaxaMinimaCiaAerea` | char(1) | S |  |
| `nr_Minuta` | char(20) | S |  |
| `tp_CAPAgenteEmissor` | char(1) | S |  |
| `vl_AgenteEmissor` | decimal(12,4) | S |  |
| `cd_NFFatura` | char(20) | S |  |
| `dt_VencimentoTitulo` | datetime | S |  |
| `id_TabelaPrecoCiaAerea` | int(10) | S |  |
| `id_CidadeDestinatario` | int(10) | S |  |
| `vl_EntregaAgente` | decimal(12,4) | S |  |
| `tp_DescontoCiaAerea` | char(1) | S |  |
| `dt_Atualizacao` | datetime | S |  |
| `ds_UsuarioAtualizacao` | varchar(50) | S |  |
| `ds_NaturezaMercadoria` | varchar(30) | S |  |
| `tp_TaxaMinimaTransportadora` | char(1) | S |  |
| `tp_ContaCorrente` | char(1) | S |  |
| `tp_ImpressoRelacaoCarga` | char(1) | S |  |
| `id_TransportadoraTerrestre` | int(10) | S |  |
| `ds_TransportadoraTerrestre` | varchar(40) | S |  |
| `id_TabelaTransportadora` | int(10) | S |  |
| `tp_Categoria` | char(1) | S |  |
| `id_AgenteColeta` | int(10) | S |  |
| `vl_AgenteColeta` | decimal(12,4) | S |  |
| `id_Coletor` | int(10) | S |  |
| `ds_AgenteColeta` | varchar(80) | S |  |
| `tp_Documento` | char(1) | S |  |
| `tp_CAPAgenteColeta` | char(1) | S |  |
| `vl_FreteAereoAWB` | decimal(12,4) | S |  |
| `qt_ImpressaoAWB` | int(10) | S |  |
| `ds_Solicitante` | varchar(30) | S |  |
| `vl_FreteAereoDescontado` | decimal(12,4) | S |  |
| `id_Veiculo` | int(10) | S |  |
| `id_Motorista` | int(10) | S |  |
| `tp_CidadeCalculo` | char(1) | S |  |
| `tp_Faturado` | char(1) | S |  |
| `id_Consignatario` | int(10) | S |  |
| `tp_AtualizarWeb` | char(1) | S |  |
| `id_FormaPagamento` | int(10) | S |  |
| `id_TabelaPrecoCorreio` | int(10) | S |  |
| `dt_Pagamento` | datetime | S |  |
| `kg_CiaAerea` | decimal(12,4) | S |  |
| `id_Embalagem` | int(10) | S |  |
| `cm_MovimentoMinuta` | varchar(255) | S |  |
| `dt_Aviso` | datetime | S |  |
| `hr_Aviso` | char(5) | S |  |
| `ds_NomeAviso` | varchar(50) | S |  |
| `cm_Aviso` | varchar(50) | S |  |
| `tp_FechamentoAgente` | char(1) | S |  |
| `ds_RazaoSocial` | varchar(80) | S |  |
| `qt_VolumeImpressaoAWB` | int(10) | S |  |
| `vl_EntregaObrigatoria` | decimal(12,4) | S |  |
| `nr_Conhecimento` | char(20) | S |  |
| `pc_Aliquota` | decimal(8,4) | S |  |
| `id_Campanha` | int(10) | S |  |
| `ds_Contato` | varchar(60) | S |  |
| `tp_Cobranca` | char(1) | S |  |
| `vl_Tarifa` | decimal(8,4) | S |  |
| `id_ServicoAereo` | int(10) | S |  |
| `cd_ServicoAereo` | char(5) | S |  |
| `id_TipoAgenteEntrega` | int(10) | S |  |
| `id_TipoAgenteColeta` | int(10) | S |  |
| `qt_KilometroColeta` | int(10) | S |  |
| `vl_ExcedentePeso` | decimal(12,4) | S |  |
| `vl_Emergencia` | decimal(12,4) | S |  |
| `vl_PesoParcial` | decimal(12,4) | S |  |
| `vl_ISS` | decimal(16,4) | S |  |
| `pc_ISS` | decimal(8,4) | S |  |
| `vl_BreakEven` | decimal(12,4) | S |  |
| `vl_TarifaAerea` | decimal(12,4) | S |  |
| `vl_TaxasPagarAWB` | decimal(12,4) | S |  |
| `vl_TaxasReceberAWB` | decimal(12,4) | S |  |
| `id_CidadeOrigem` | int(10) | S |  |
| `id_Manifesto` | int(10) | S |  |
| `qt_VolumesLidos` | int(10) | S |  |
| `id_ItemPedidoColeta` | int(10) | S |  |
| `id_AgenteDespacho` | int(10) | S |  |
| `qt_KilometroDespacho` | int(10) | S |  |
| `id_TipoDespacho` | int(10) | S |  |
| `vl_AgenteDespacho` | decimal(12,4) | S |  |
| `tp_CAPAgenteDespacho` | char(1) | S |  |
| `id_AgenteRedespacho` | int(10) | S |  |
| `qt_KilometroRedespacho` | int(10) | S |  |
| `id_TipoRedespacho` | int(10) | S |  |
| `vl_AgenteRedespacho` | decimal(12,4) | S |  |
| `tp_CAPAgenteRedespacho` | char(1) | S |  |
| `qt_KilometroMovimento` | int(10) | S |  |
| `dt_PrazoEntrega` | datetime | S |  |
| `hr_PrazoEntrega` | char(5) | S |  |
| `kg_OutraCategoria` | decimal(12,4) | S |  |
| `pc_ICMS` | decimal(8,4) | S |  |
| `vl_ICMS` | decimal(16,4) | S |  |
| `vl_SETCAT` | decimal(12,4) | S |  |
| `vl_ITR` | decimal(12,4) | S |  |
| `vl_Ademe` | decimal(16,4) | S |  |
| `vl_Despacho` | decimal(12,4) | S |  |
| `nr_ConhecimentoTransportadora` | char(20) | S |  |
| `id_Status` | int(10) | S |  |
| `cd_Emergencia` | varchar(50) | S |  |
| `id_ManifestoDespacho` | int(10) | S |  |
| `id_ManifestoRetirada` | int(10) | S |  |
| `id_ManifestoRedespacho` | int(10) | S |  |
| `id_ManifestoEntrega` | int(10) | S |  |
| `dt_Despacho` | datetime | S |  |
| `dt_Retirada` | datetime | S |  |
| `dt_Redespacho` | datetime | S |  |
| `tp_Redespacho` | char(1) | S |  |
| `id_TransportadoraRedespacho` | int(10) | S |  |
| `id_TG30` | int(10) | S |  |
| `id_RelacaoCarga` | int(10) | S |  |
| `id_ManifestoViagem` | int(10) | S |  |
| `dt_Viagem` | datetime | S |  |
| `id_RemetenteCentroCusto` | int(10) | S |  |
| `id_TipoMovimento` | int(10) | S |  |
| `nr_Referencia` | char(15) | S |  |
| `ds_GrauParentesco` | varchar(40) | S |  |
| `dt_Cadastro` | datetime | S |  |
| `ds_UsuarioCadastro` | varchar(50) | S |  |
| `qt_ImpressaoMinuta` | int(10) | S |  |
| `qt_ImpressaoConhecimento` | int(10) | S |  |
| `qt_ImpressaoEtiquetaRemetente` | int(10) | S |  |
| `qt_ImpressaoEtiquetaCiaAerea` | int(10) | S |  |
| `tp_NotaFiscalServico` | char(1) | S |  |
| `nr_Formulario` | char(20) | S |  |
| `hr_ChegadaCliente` | char(5) | S |  |
| `hr_SaidaCliente` | char(5) | S |  |
| `tp_TaxaMinimaCliente` | char(1) | S |  |
| `nr_ColetaManual` | char(10) | S |  |
| `vl_DespesaManifesto` | decimal(12,4) | S |  |
| `dt_ImpressaoConhecimento` | datetime | S |  |
| `hr_ImpressaoConhecimento` | char(5) | S |  |
| `vl_FreteCliente` | decimal(12,4) | S |  |
| `vl_FreteReal` | decimal(12,4) | S |  |
| `vl_FreteRedespacho` | decimal(12,4) | S |  |
| `nr_ConhecimentoRedespacho` | char(15) | S |  |
| `tp_EnviarEDI` | char(1) | S |  |
| `tp_Emergencia` | char(1) | S |  |
| `tp_GeradoSintegra` | char(1) | S |  |
| `id_MovimentoReferencia` | int(10) | S |  |
| `tp_Cancelado` | char(1) | S |  |
| `vl_TTD` | decimal(12,4) | S |  |
| `vl_TarifaCalculada` | decimal(12,4) | S |  |
| `tp_DocumentoRecebido` | char(1) | S |  |
| `id_CodigoNFServico` | int(10) | S |  |
| `ds_EnderecoEntrega` | varchar(80) | S |  |
| `id_CidadeEntrega` | int(10) | S |  |
| `pc_Insentivo` | decimal(8,4) | S |  |
| `tp_EnviarEDIEmbarque` | char(1) | S |  |
| `id_CiaAerea2` | int(10) | S |  |
| `id_TransportadoraTerrestre2` | int(10) | S |  |
| `nr_AWB2` | char(20) | S |  |
| `vl_FreteAereo2` | decimal(12,4) | S |  |
| `vl_FreteAWB2` | decimal(12,4) | S |  |
| `vl_TaxasPagarAWB2` | decimal(12,4) | S |  |
| `vl_TaxasReceberAWB2` | decimal(12,4) | S |  |
| `nr_PedidoMetodo` | char(15) | S |  |
| `ds_ACPedidoMetodo` | varchar(50) | S |  |
| `tp_Gravado` | char(1) | S |  |
| `ds_Unitizador` | varchar(200) | S |  |
| `dt_agendamento` | datetime | S |  |
| `cd_CEPEntrega` | char(8) | S |  |
| `tp_AverbadoATM` | char(1) | S |  |
| `tp_CanceladoATM` | char(1) | S |  |
| `id_TabelaPrecoAgenteColeta` | int(10) | S |  |
| `id_TabelaPrecoAgenteEntrega` | int(10) | S |  |
| `id_TabelaPrecoRedespacho` | int(10) | S |  |
| `cm_AgenteColeta` | varchar(200) | S |  |
| `cm_AgenteEntrega` | varchar(200) | S |  |
| `nr_PedidoCliente` | varchar(255) | S |  |
| `vl_Outros` | decimal(15,4) | S |  |
| `cd_CGF` | varchar(20) | S |  |
| `tp_AverbadoPortoSeguro` | char(1) | S |  |
| `tp_IntegradoClaro` | varchar(1) | S |  |
| `ds_UltimoRetornoClaro` | varchar(300) | S |  |
| `tp_IntegradoClaroEnvioXML` | varchar(1) | S |  |
| `ds_UltimoRetornoClaroEnvioXML` | varchar(300) | S |  |
| `tp_EnviarInfraero` | char(1) | S |  |
| `tp_ICMSManual` | char(1) | S |  |
| `pc_ICMSCalculado` | decimal(8,4) | S |  |
| `tp_EnvioEDIInterno` | char(1) | S |  |
| `tp_IntegradoiTrack` | char(1) | S |  |
| `ds_UltimoRetornoiTrack` | varchar(200) | S |  |
| `tp_PrazoEntregaManual` | char(1) | S |  |
| `tp_ProcessamentoIniciado` | char(1) | S |  |
| `tp_FreteRapido` | char(1) | S |  |
| `tp_Gerado` | char(1) | S |  |
| `tp_EnviarEDIContabilProvisao` | char(1) | S |  |
| `tp_EnviarAverb` | char(1) | S |  |
| `tp_EnviarEDICTeNFsWalmart` | char(1) | S |  |
| `id_UsuarioCadastro` | int(10) | S |  |
| `cd_SerieCTRC` | char(3) | S |  |
| `ds_Protocolointegracao` | varchar(20) | S |  |
| `tp_ProtocoloIntegracao` | varchar(2) | S |  |
| `dt_protocolointegracao` | datetime | S |  |
| `id_Carreta` | int(10) | S |  |
| `dt_InclusaoWeightPortal` | datetime | S |  |
| `id_BennerFnDocumentos` | int(10) | S |  |
| `id_BennerHandleMovCancelamento` | int(10) | S |  |
| `vl_NotaFiscalAnterior` | decimal(18) | S |  |
| `id_MovimentoAtualizacao` | int(10) | S |  |
| `id_Stm` | uniqueidentifier | S |  |
| `vl_NotaCliente` | decimal(16,4) | S |  |
| `vl_FretePortal` | decimal(16,4) | S |  |
| `pc_DescontoPedagio` | decimal(16,4) | S |  |
| `dt_autorizacao` | datetime | S |  |
| `pc_IBS` | decimal(16,4) | S |  |
| `vl_IBS` | decimal(16,4) | S |  |
| `tp_WebcolNFS` | char(1) | S |  |
| `pc_CBS` | decimal(16,4) | S |  |
| `vl_CBS` | decimal(16,4) | S |  |
| `vl_BaseCalculoIBSCBS` | decimal(16,4) | S |  |
| `id_SituacaoTributariaIBS` | int(10) | S |  |
| `id_SituacaoTributariaCBS` | int(10) | S |  |
| `ds_Armazem` | varchar(20) | S |  |
| `dt_agendamentoPortal` | date | S |  |
| `cd_SituacaoTributariaIBSCBS` | char(3) | S |  |
| `cd_ClassTribIBSCBS` | char(6) | S |  |

Relacionamentos (FK):
- `id_TipoMovimento` -> `tbdTipoMovimento.id_TipoMovimento`
- `id_TipoMovimento` -> `tbdTipoMovimento.id_TipoMovimento`

#### `dbo.tbdMovimentoDados`

Linhas: **570.649**  
PK: `id_Movimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` (PK) | int(10) | N |  |
| `dt_ChegadaAgente` | datetime | S |  |
| `dt_SaidaAgente` | datetime | S |  |
| `ds_UsuarioEntrega` | varchar(30) | S |  |
| `dt_DigitacaoEntrega` | datetime | S |  |
| `cd_LocalidadeEDI` | char(10) | S |  |
| `tp_ConferidoManifesto` | char(1) | S |  |
| `id_AvaliacaoEntrega` | int(10) | S |  |
| `id_Usuario` | int(10) | S |  |
| `tp_AWB` | char(1) | S |  |
| `tp_ImpressoComprovante` | char(1) | S |  |
| `tp_ImpressoMinuta` | char(1) | S |  |
| `tp_Preferencial` | char(1) | S |  |
| `id_NaturezaMercadoria` | int(10) | S |  |
| `dt_DocumentoRecebido` | datetime | S |  |
| `ds_EmailAutomatico` | varchar(50) | S |  |
| `id_LocalEntregaPreAlert` | int(10) | S |  |
| `id_TransportadoraPreferencial` | int(10) | S |  |
| `id_AgenteEmissor2` | int(10) | S |  |
| `id_ClienteImpressao` | int(10) | S |  |
| `id_LoteSuframa` | int(10) | S |  |
| `pc_FretePesoAgenteColeta` | decimal(8,4) | S |  |
| `pc_FretePesoAgenteEntrega` | decimal(8,4) | S |  |
| `tp_EnviarAverbacao` | char(1) | S |  |
| `vl_MinimoAgenteColeta` | decimal(12,4) | S |  |
| `vl_MinimoAgenteEntrega` | decimal(12,4) | S |  |
| `ds_ArquivoEDI` | varchar(50) | S |  |
| `id_MovimentoSislogNet` | int(10) | S |  |
| `tp_GeradoAgente` | char(1) | S |  |
| `vl_BaseCalculo` | decimal(15,4) | S |  |
| `pc_BaseCalculoIntermodal` | decimal(8,4) | S |  |
| `id_SerieConhecimento` | int(10) | S |  |
| `cd_CFOP` | char(5) | S |  |
| `vl_BaseCalculoImposto` | decimal(15,4) | S |  |
| `ds_UsuarioImpressao` | varchar(50) | S |  |
| `tp_ViaEdi` | char(1) | S |  |
| `tp_RecebBase` | char(1) | S |  |
| `ds_UsuarioImpressaoMinuta` | varchar(50) | S |  |
| `dt_ImpressaoMinuta` | datetime | S |  |
| `hr_ImpressaoMinuta` | char(5) | S |  |
| `vl_TarifaCheia` | decimal(15,4) | S |  |
| `tp_PrimeiroVoo` | char(1) | S |  |
| `tp_ColetaExclusiva` | char(1) | S |  |
| `tp_EntregaExclusiva` | char(1) | S |  |
| `id_TipoColeta` | int(10) | S |  |
| `cd_PreFaturaDanzas` | varchar(20) | S |  |
| `tp_PercentualEntregaAgente` | char(1) | S |  |
| `tp_PercentualColetaAgente` | char(1) | S |  |
| `id_TabelaPrecoCalculado` | int(10) | S |  |
| `id_UltimaOcorrencia` | int(10) | S |  |
| `id_UltimoManifesto` | int(10) | S |  |
| `id_ClienteSislogNet` | int(10) | S |  |
| `cd_CFOPImpresso` | char(10) | S |  |
| `id_ImportacaoEDI` | int(10) | S |  |
| `id_ImportacaoEDIFatura` | int(10) | S |  |
| `vl_FretePreFatura` | decimal(15,4) | S |  |
| `tp_MultiModal` | char(1) | S |  |
| `ds_UsuarioBaixaComprovante` | varchar(50) | S |  |
| `pc_ImpostoSimplesNacional` | decimal(8,4) | S |  |
| `id_ConsolidacaoMovimento` | int(10) | S |  |
| `tp_LiberadoImpressao` | char(1) | S |  |
| `id_LoteCTe` | int(10) | S |  |
| `tp_EmissaoCTeAutorizada` | char(1) | S |  |
| `dt_ImpressaoCTe` | datetime | S |  |
| `nr_ProtocoloCTe` | varchar(20) | S |  |
| `id_RegiaoCEP` | int(10) | S |  |
| `id_RotaManifesto` | int(10) | S |  |
| `tp_EmailRemetente` | char(1) | S |  |
| `tp_EmailDestinatario` | char(1) | S |  |
| `tp_EmailContabilidade` | char(1) | S |  |
| `cd_ImpostoCTe` | char(2) | S |  |
| `dt_EnvioProtocoloCliente` | datetime | S |  |
| `nr_ProtocoloCliente` | varchar(16) | S |  |
| `tp_ProcessamentoCTe` | char(1) | S |  |
| `id_LocalEntrega` | int(10) | S |  |
| `ds_ProtCTe` | varchar(8000) | S |  |
| `ds_procCancCTe` | varchar(8000) | S |  |
| `ds_enderecofaturamento2` | varchar(70) | S |  |
| `nr_EnderecoFaturamento` | char(10) | S |  |
| `id_TipoLogradouro` | int(10) | S |  |
| `tp_LiberadoCorrecaoCTe` | char(1) | S |  |
| `id_MovimentoOriginal` | int(10) | S |  |
| `id_Expedidor` | int(10) | S |  |
| `tp_EmailClienteFaturamento` | char(1) | S |  |
| `tp_EmailExpedidor` | char(1) | S |  |
| `tp_EmailConsignatario` | char(1) | S |  |
| `ds_StatusTam` | varchar(200) | S |  |
| `id_ClienteFaturadoAlterado` | int(10) | S |  |
| `hr_DocumentoRecebido` | char(8) | S |  |
| `cd_Deposito` | char(10) | S |  |
| `tp_SpedEnviado` | char(1) | S |  |
| `ds_ComplementoDestinatario` | varchar(150) | S |  |
| `tp_Cubadora` | char(1) | S |  |
| `ds_NotaOrdenada` | varchar(3000) | S |  |
| `dt_BaixaTitulo` | datetime | S |  |
| `id_Bancario` | int(10) | S |  |
| `id_TipoServicoCTe` | int(10) | S |  |
| `tp_Denegada` | char(1) | S |  |
| `tp_EnviadoNFePrefeituraABRASF` | char(1) | S |  |
| `ds_DescricaoServicoNFe` | varchar(200) | S |  |
| `cd_ItemListaServico` | varchar(25) | S |  |
| `tp_EnviadoDigitalizacao` | char(1) | S |  |
| `dt_Digitalizacao` | datetime | S |  |
| `id_TipoVeiculo` | int(10) | S |  |
| `tp_DocumentoDigitalizado` | char(1) | S |  |
| `id_ServicoISS` | int(10) | S |  |
| `tp_Escaneado` | char(1) | S |  |
| `ds_LinhaEDI` | varchar(4000) | S |  |
| `tp_DocumentoEscaneado` | char(1) | S |  |
| `id_CapaLoteEletronica` | int(10) | S |  |
| `ds_Cliente` | varchar(14) | S |  |
| `cd_Transportadora` | char(3) | S |  |
| `cd_CGCCPFTransportadora` | varchar(14) | S |  |
| `tp_freteUrbanoDHL` | char(1) | S |  |
| `tp_CargaRecebida` | char(1) | S |  |
| `tp_VolumeLido` | char(1) | S |  |
| `dt_Agendamento` | datetime | S |  |
| `hr_Agendamento` | char(5) | S |  |
| `tp_ModalidadeFrete` | char(1) | S |  |
| `tp_FreteUrbano` | char(1) | S |  |
| `id_UltimaOcorrenciaNota` | int(10) | S |  |
| `tp_EnviadoNFePrefeitura` | char(1) | S |  |
| `tp_StatusPendencia` | char(1) | S |  |
| `dt_FinalizacaoPerformance` | datetime | S |  |
| `hr_FinalizacaoPerformance` | char(5) | S |  |
| `id_ResponsavelSeguro` | int(10) | S |  |
| `id_EmissorAnterior` | int(10) | S |  |
| `id_TipoDocumentoAnterior` | int(10) | S |  |
| `id_PercursoContratadoAnterior` | int(10) | S |  |
| `dt_Anulacao` | datetime | S |  |
| `id_TipoDocumentoSubstituto` | int(10) | S |  |
| `cd_CNPJSubstituto` | varchar(20) | S |  |
| `nr_DocumentoSubstituto` | varchar(50) | S |  |
| `cd_SerieSubstituto` | char(5) | S |  |
| `cd_ModeloNFSubstituto` | char(5) | S |  |
| `vl_NotaFiscalSubstituto` | decimal(15,4) | S |  |
| `dt_EmissaoNFSubstituto` | datetime | S |  |
| `tp_DocumentoNF` | char(1) | S |  |
| `vl_TotalFrete` | decimal(15,4) | S |  |
| `tp_Lotacao` | char(1) | S |  |
| `id_CartaCorrecaoEletronica` | int(10) | S |  |
| `tp_CCeAutorizada` | char(1) | S |  |
| `tp_EmailRemetenteCCe` | char(1) | S |  |
| `tp_EmailDestinatarioCCe` | char(1) | S |  |
| `tp_EmailContabilidadeCCe` | char(1) | S |  |
| `tp_EmailClienteFaturamentoCCe` | char(1) | S |  |
| `tp_EmailExpedidorCCe` | char(1) | S |  |
| `tp_EmailConsignatarioCCe` | char(1) | S |  |
| `nr_ProtocoloATM` | varchar(50) | S |  |
| `vl_DescontoPreFatura` | decimal(15,4) | S |  |
| `id_PreManifesto` | int(10) | S |  |
| `cm_LogicaPrazoEntrega` | varchar(255) | S |  |
| `ds_ChaveCTeAnulacao` | varchar(60) | S |  |
| `ds_ChaveNFeAnulacao` | varchar(60) | S |  |
| `nr_NFAnulado` | int(10) | S |  |
| `cd_SerieNFAnulado` | char(3) | S |  |
| `ds_ModeloNFAnulado` | char(2) | S |  |
| `vl_NFAnulado` | decimal(15,4) | S |  |
| `dt_EmissaoNFAnulado` | datetime | S |  |
| `ds_Latitude` | varchar(15) | S |  |
| `ds_Longitude` | varchar(15) | S |  |
| `tp_MovimentoLiberado` | char(1) | S |  |
| `dt_MovimentoLiberado` | datetime | S |  |
| `ds_UsuarioLiberacaoMovimento` | varchar(80) | S |  |
| `dt_AverbacaoATM` | datetime | S |  |
| `dt_AverbadoPortoSeguro` | datetime | S |  |
| `nr_ProtocoloPortoSeguro` | varchar(100) | S |  |
| `id_EDIAverbacaoPortoSeguro` | int(10) | S |  |
| `ds_ChaveCTeMultimodalCliente` | varchar(44) | S |  |
| `nr_Averbacao` | varchar(50) | S |  |
| `tp_CTeGlobalizado` | char(1) | S |  |
| `id_EDIAverbacaoELT` | int(10) | S |  |
| `cm_CTeGlobalizado` | varchar(255) | S |  |
| `tp_AlterarFaturado` | char(1) | S |  |
| `tp_TratamentoCliente` | char(1) | S |  |
| `cm_TratamentoCliente` | varchar(1000) | S |  |
| `dt_TratamentoCliente` | datetime | S |  |
| `ds_UsuarioTratamentoCliente` | varchar(50) | S |  |
| `id_TransportadoraAtual` | int(10) | S |  |
| `nr_IndIEToma` | varchar(2) | S |  |
| `ds_SubDiretorioCTE` | varchar(50) | S |  |
| `tp_UpsTransportesEnviado` | char(1) | S |  |
| `tp_UpsClienteEnviado` | char(1) | S |  |
| `nr_Protocolo` | varchar(6) | S |  |
| `tp_GeradoXMLCCeNDD` | char(1) | S |  |
| `tp_EmailAgenteColeta` | char(1) | S |  |
| `tp_EmailAgenteEntrega` | char(1) | S |  |
| `cd_VerificacaoNFSe` | varchar(20) | S |  |
| `tp_AlpargatasEnviado` | char(1) | S |  |
| `tp_ToutboxEnviado` | char(1) | S |  |
| `id_LoteGNRE` | int(10) | S |  |
| `tp_EnviadoConfirmaFacil` | char(1) | S |  |
| `tp_CTeSimplificado` | char(1) | S |  |
| `cm_CTeSimplificado` | varchar(255) | S |  |

#### `dbo.tbdMovimentoDestinatario`

Linhas: **570.649**  
PK: `id_Movimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` (PK) | int(10) | N |  |
| `cd_CGCCPF` | char(14) | S |  |
| `ds_Pessoa` | varchar(80) | S |  |
| `ds_RazaoSocial` | varchar(80) | S |  |
| `ds_Endereco` | varchar(70) | S |  |
| `ds_Bairro` | varchar(60) | S |  |
| `nr_Telefone` | varchar(30) | S |  |
| `cd_IE` | char(20) | S |  |
| `cd_CEP` | char(8) | S |  |
| `ds_Contato` | varchar(60) | S |  |
| `cd_IM` | char(20) | S |  |
| `nr_Fax` | varchar(30) | S |  |
| `ds_EnderecoEntrega` | varchar(70) | S |  |
| `id_CidadeEntrega` | int(10) | S |  |
| `nr_Celular` | varchar(30) | S |  |
| `cd_Email` | varchar(50) | S |  |
| `cm_Destinatario` | varchar(255) | S |  |
| `id_CidadeDestinatario` | int(10) | S |  |
| `tp_NaoContribuinte` | char(1) | S |  |
| `cd_Cliente` | char(20) | S |  |
| `id_Destinatario` | int(10) | S |  |
| `nr_Suframa` | char(20) | S |  |
| `tp_InsentivoZonaFranca` | char(1) | S |  |
| `cd_CEPEntrega` | char(8) | S |  |
| `id_LocalEntrega` | int(10) | S |  |
| `ds_BairroEntrega` | varchar(30) | S |  |
| `id_TipoLogradouro` | int(10) | S |  |
| `nr_EnderecoFaturamento` | char(10) | S |  |
| `ds_enderecofaturamento2` | varchar(70) | S |  |
| `ds_ComplementoDestinatario` | varchar(150) | S |  |
| `cd_CGF` | varchar(20) | S |  |

#### `dbo.tbdMovimentoNotaFiscal`

Linhas: **763.897**  
PK: `id_MovimentoNotaFiscal`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_MovimentoNotaFiscal` (PK) | int(10) | N |  |
| `id_Movimento` | int(10) | S |  |
| `id_Sequencia` | int(10) | S |  |
| `id_Cliente` | int(10) | S |  |
| `id_ItemPedidoColetaNF` | int(10) | S |  |
| `id_Remetente` | int(10) | S |  |
| `cd_NotaFiscal` | char(15) | S |  |
| `cd_Serie` | char(5) | S |  |
| `ds_Modelo` | char(8) | S |  |
| `vl_NotaFiscal` | decimal(36,4) | S |  |
| `dt_Emissao` | datetime | S |  |
| `id_ServicoNotaFiscal` | int(10) | S |  |
| `tp_Pagador` | char(1) | S |  |
| `dt_Entrega` | datetime | S |  |
| `hr_Entrega` | char(5) | S |  |
| `vl_Receber` | decimal(12,4) | S |  |
| `id_Fornecedor` | int(10) | S |  |
| `vl_Fornecedor` | decimal(12,4) | S |  |
| `id_Embalador` | int(10) | S |  |
| `vl_Embalador` | decimal(12,4) | S |  |
| `cd_ServicoNotaFiscal` | varchar(100) | S |  |
| `qt_Volume` | int(10) | S |  |
| `id_NaturezaMercadoria` | int(10) | S |  |
| `kg_Mercadoria` | decimal(16,4) | S |  |
| `vl_Produto` | decimal(16,4) | S |  |
| `vl_IPI` | decimal(12,4) | S |  |
| `vl_ICMS` | decimal(16,4) | S |  |
| `dt_EntregaReal` | datetime | S |  |
| `hr_EntregaReal` | char(5) | S |  |
| `ds_QuemRecebeu` | varchar(50) | S |  |
| `nr_Documento` | char(20) | S |  |
| `ds_GrauParentesco` | varchar(30) | S |  |
| `cm_Entrega` | varchar(255) | S |  |
| `ds_Produto` | varchar(50) | S |  |
| `id_ItemTransmissao` | int(10) | S |  |
| `id_RemetenteMapa` | int(10) | S |  |
| `ds_RemetenteMapa` | varchar(50) | S |  |
| `id_DestinatarioMapa` | int(10) | S |  |
| `ds_DestinatarioMapa` | varchar(50) | S |  |
| `qt_Pecas` | int(10) | S |  |
| `id_CentroCusto` | int(10) | S |  |
| `nr_PedidoCliente` | char(20) | S |  |
| `vl_FatorCubagem` | decimal(12,4) | S |  |
| `ds_ModeloNota` | char(10) | S |  |
| `tp_LogisticaReversaFinalizada` | char(1) | S |  |
| `nr_Order` | varchar(30) | S |  |
| `nr_Serial` | varchar(30) | S |  |
| `dt_DocumentoRecebido` | datetime | S |  |
| `ds_UsuarioBaixaComprovante` | varchar(50) | S |  |
| `ds_ChaveNFe` | varchar(80) | S |  |
| `id_MovimentoEDI` | int(10) | S |  |
| `id_TipoDocumento` | int(10) | S |  |
| `tp_BaixadoManifesto` | char(1) | S |  |
| `vl_MetroCubico` | decimal(15,4) | S |  |
| `tp_DocumentoEscaneado` | char(1) | S |  |
| `nr_NotaFiscalInteiro` | bigint(19) | S |  |
| `NR_PROTOCOLO` | int(10) | S |  |
| `cd_Mod` | int(10) | S |  |
| `tp_IntegradoiTrack` | char(1) | S |  |
| `ds_UltimoRetornoiTrack` | varchar(200) | S |  |
| `id_iTrack` | int(10) | S |  |
| `tp_IntegradoiTrackEntrega` | varchar(1) | S |  |
| `ds_UltimoRetornoiTrackEntrega` | varchar(200) | S |  |
| `id_iTrackEntrega` | int(10) | S |  |
| `tp_IntegradoiTrackDetalhes` | char(1) | S |  |
| `ds_ChaveDACe` | varchar(44) | S |  |

#### `dbo.tbdMovimentoProdutoNota`

Linhas: **33.116.054**  
PK: `id_MovimentoProdutoNota`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_MovimentoProdutoNota` (PK) | int(10) | N |  |
| `id_Movimento` | int(10) | S |  |
| `qt_Produto` | int(10) | S |  |
| `cd_NotaFiscal` | varchar(15) | S |  |
| `ds_Produto` | varchar(255) | S |  |
| `cd_Produto` | varchar(15) | S |  |
| `cd_NCM` | varchar(20) | S |  |
| `cd_Unidade` | varchar(20) | S |  |
| `vl_Unitario` | decimal(16,4) | S |  |
| `vl_Total` | decimal(16,4) | S |  |

#### `dbo.tbdOcorrenciaNota`

Linhas: **1.125.612**  
PK: `id_OcorrenciaNota`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_OcorrenciaNota` (PK) | int(10) | N |  |
| `id_Movimento` | int(10) | S |  |
| `nr_NotaFiscal` | char(20) | S |  |
| `id_Ocorrencia` | int(10) | S |  |
| `ds_Ocorrencia` | varchar(255) | S |  |
| `dt_PrazoFechamento` | datetime | S |  |
| `hr_PrazoFechamento` | char(5) | S |  |
| `ds_UsuarioAbertura` | varchar(30) | S |  |
| `dt_Abertura` | datetime | S |  |
| `hr_Abertura` | char(5) | S |  |
| `ds_UsuarioAlteracao` | varchar(30) | S |  |
| `dt_Alteracao` | datetime | S |  |
| `hr_Alteracao` | char(5) | S |  |
| `id_Manifesto` | int(10) | S |  |
| `tp_Gerencia` | char(1) | S |  |
| `id_OcorrenciaGerencia` | int(10) | S |  |
| `id_MovimentoGerado` | int(10) | S |  |
| `tp_Manifesto` | char(1) | S |  |
| `tp_Ocorrencia` | char(1) | S |  |
| `dt_Fechamento` | datetime | S |  |
| `hr_Fechamento` | char(5) | S |  |
| `cm_Fechamento` | varchar(255) | S |  |
| `ds_UsuarioFechamento` | varchar(30) | S |  |
| `id_Financeiro` | int(10) | S |  |
| `id_ProtocoloEntrega` | int(10) | S |  |
| `tp_Automatico` | char(1) | S |  |
| `tp_EnviarEDI` | char(1) | S |  |
| `tp_EnviarEDIOcorrencia` | char(1) | S |  |
| `id_FechamentoCiaAerea` | int(10) | S |  |
| `id_FechamentoTransportadora` | int(10) | S |  |
| `tp_StatusSac` | char(1) | S |  |
| `id_RomaneioAgente` | int(10) | S |  |
| `id_LocalCodigoBarra` | int(10) | S |  |
| `dt_Agendamento` | datetime | S |  |
| `hr_Agendamento` | char(5) | S |  |
| `tp_NaoPermiteNovaOcorrencia` | char(1) | S |  |
| `TP_ENVIAREDIWALMART` | char(1) | S |  |
| `nr_SRO` | varchar(30) | S |  |
| `tp_MagazineLuizaEnviado` | char(1) | S |  |
| `tp_IntegradoClaro` | varchar(1) | S |  |
| `ds_UltimoRetornoClaro` | varchar(300) | S |  |
| `tp_EnviadoWS` | char(1) | S |  |
| `tp_IntegradoGKO` | char(1) | S |  |
| `ds_ProtocoloGKO` | varchar(100) | S |  |
| `tp_IntegradoiTrack` | varchar(1) | S |  |
| `ds_UltimoRetornoiTrack` | varchar(200) | S |  |
| `tp_EnviadoBomiAPI` | char(1) | S |  |
| `tp_IntegradoCastrol` | char(1) | S |  |
| `tp_EnviadoCastrol` | char(1) | S |  |
| `ds_UltimoRetornoCastrol` | varchar(500) | S |  |
| `tp_FreteRapido` | char(1) | S |  |
| `tp_EverlogEnviado` | varchar(1) | S |  |
| `ds_Arquivo` | varchar(30) | S |  |
| `id_OcorrenciaGerada` | int(10) | S |  |
| `ds_Protocolointegracao` | varchar(20) | S |  |
| `tp_ProtocoloIntegracao` | varchar(2) | S |  |
| `dt_protocolointegracao` | datetime | S |  |
| `dt_IntegracaoServMobile` | datetime | S |  |
| `tp_IntelipostEnviado` | char(1) | S |  |
| `tp_IntelipostComprovante` | char(1) | S |  |
| `nr_AlpargatasRef` | varchar(20) | S |  |
| `tp_AlpargatasEnviado` | char(1) | S |  |
| `tp_FreteRapidoV2Enviado` | char(1) | S |  |
| `tp_ToutboxEnviado` | char(1) | S |  |
| `tp_Esales` | char(1) | S |  |
| `id_OcorrenciaStatus` | int(10) | S |  |
| `tp_EnviadoConfirmaFacil` | char(1) | S |  |
| `tp_integrado` | bit | N |  |
| `dt_IntegracaoNTT` | datetime | S |  |
| `cm_IntegracaoNTT` | text(2147483647) | S |  |

#### `dbo.tbdUltimaOcorrenciaNota`

Linhas: **682.169**  
PK: `id_UltimaOcorrenciaNota`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_UltimaOcorrenciaNota` (PK) | int(10) | N |  |
| `id_Ocorrencia` | int(10) | S |  |
| `id_OcorrenciaNota` | int(10) | S |  |
| `id_Movimento` | int(10) | S |  |
| `nr_NotaFiscal` | varchar(20) | S |  |

#### `dbo.tbdLoteCTe`

Linhas: **346.124**  
PK: `id_LoteCTe`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_LoteCTe` (PK) | int(10) | N |  |
| `dt_Lote` | datetime | S |  |
| `hr_Lote` | char(5) | S |  |
| `ds_Usuario` | varchar(50) | S |  |
| `nr_ReciboSEFAZ` | varchar(20) | S |  |
| `tp_RetonoSEFAZ` | char(1) | S |  |
| `tp_Enviado` | char(1) | S |  |
| `id_UsuarioLote` | int(10) | S |  |
| `id_Empresa` | int(10) | S |  |
| `tp_Ambiente` | char(1) | S |  |
| `id_EstadoSEFAZ` | int(10) | S |  |
| `id_EstadoEmpresa` | int(10) | S |  |
| `nr_VersaoCTe` | char(10) | S |  |
| `nr_CodigoErro` | int(10) | S |  |
| `ds_ResultadoWS` | varchar(3000) | S |  |
| `id_UsuarioEnvioTemp` | int(10) | S |  |
| `nr_CodigoErroRetorno` | int(10) | S |  |
| `ds_ResultadoWSRetorno` | varchar(3000) | S |  |
| `tp_LoteExcluido` | char(1) | S |  |
| `ds_UsuarioExclusao` | varchar(50) | S |  |
| `dt_Exclusao` | datetime | S |  |
| `hr_Exclusao` | char(5) | S |  |
| `cm_Exclusao` | varchar(255) | S |  |
| `dt_RetornoSEFAZ` | datetime | S |  |
| `hr_RetornoSEFAZ` | char(5) | S |  |
| `dt_ReciboSEFAZ` | datetime | S |  |
| `hr_ReciboSEFAZ` | char(5) | S |  |
| `tp_EmissaoCTe` | char(1) | S |  |
| `cm_JustificativaContingencia` | varchar(255) | S |  |
| `id_Cliente` | int(10) | S |  |
| `ds_SubDiretorioCTE` | varchar(50) | S |  |

#### `dbo.tbdLoteCTeMovimento`

Linhas: **431.974**  
PK: `id_LoteCTeMovimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_LoteCTeMovimento` (PK) | int(10) | N |  |
| `id_LoteCTe` | int(10) | S |  |
| `id_Movimento` | int(10) | S |  |
| `nr_ProtocoloCTe` | varchar(20) | S |  |
| `ds_ChaveCTe` | varchar(50) | S |  |
| `ds_DigestValue` | varchar(40) | S |  |
| `nr_CodigoRetorno` | int(10) | S |  |
| `ds_MensagemRetorno` | varchar(500) | S |  |
| `tp_EmissaoAutorizada` | char(1) | S |  |
| `tp_CTeCancelado` | char(1) | S |  |
| `id_UsuarioCancelamento` | int(10) | S |  |
| `ds_UsuarioCancelamento` | varchar(50) | S |  |
| `dt_Cancelamento` | datetime | S |  |
| `hr_Cancelamento` | char(5) | S |  |
| `nr_CTeCancelado` | char(10) | S |  |
| `cm_Cancelamento` | varchar(255) | S |  |
| `nr_ProtocoloCancelamento` | varchar(20) | S |  |
| `nr_CodigoCancelamento` | int(10) | S |  |
| `ds_MensagemCancelamento` | varchar(500) | S |  |
| `ds_CodigoBarraContigenciaCTe` | varchar(50) | S |  |
| `id_bennerfndocumentos` | int(10) | S |  |
| `id_BennerHandleMovCancelamento` | int(10) | S |  |
| `tp_Pdf` | char(1) | S |  |
| `id_bennerfndocumentosVoe2` | int(10) | S |  |
| `id_BennerHandleMovCancelamentoVoe2` | int(10) | S |  |

#### `dbo.tbdManifestoMovimento`

Linhas: **463.324**  
PK: `id_ManifestoMovimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_ManifestoMovimento` (PK) | int(10) | N |  |
| `id_Manifesto` | int(10) | S |  |
| `id_Cliente` | int(10) | S |  |
| `id_Movimento` | int(10) | S |  |
| `id_PedidoColeta` | int(10) | S |  |
| `ds_Tipo` | char(20) | S |  |
| `id_StatusAnterior` | int(10) | S |  |
| `id_Status` | int(10) | S |  |
| `id_Ocorrencia` | int(10) | S |  |
| `dt_Servico` | datetime | S |  |
| `hr_Chegada` | char(5) | S |  |
| `hr_Saida` | char(5) | S |  |
| `vl_DespesaManifesto` | decimal(12,4) | S |  |
| `ds_Campo` | varchar(30) | S |  |
| `qt_Servico` | int(10) | S |  |
| `vl_Unitario` | decimal(12,4) | S |  |
| `id_Regiao` | int(10) | S |  |
| `tp_EntregaEspecial` | char(1) | S |  |
| `ds_UsuarioCarregamento` | varchar(50) | S |  |
| `ds_UsuarioDescarregamento` | varchar(50) | S |  |
| `qt_VolumeCarregamento` | int(10) | S |  |
| `qt_VolumeDescarregamento` | int(10) | S |  |
| `tp_EtiquetaCarregamento` | char(1) | S |  |
| `tp_EtiquetaDescarregamento` | char(1) | S |  |
| `tp_ManualCarregamento` | char(1) | S |  |
| `tp_ManualDescarregamento` | char(1) | S |  |
| `tp_Conferido` | char(1) | S |  |
| `nr_Ordem` | int(10) | S |  |
| `cm_Ocorrencia` | varchar(3000) | S |  |
| `tp_Registro` | char(1) | S |  |
| `dt_Recepcao` | datetime | S |  |
| `hr_Recepcao` | char(5) | S |  |
| `ds_Receptor` | varchar(50) | S |  |
| `nr_DocumentoReceptor` | varchar(15) | S |  |
| `ds_GrauParentesco` | varchar(25) | S |  |
| `cm_Entrega` | varchar(255) | S |  |
| `dt_ChegadaCliente` | datetime | S |  |
| `hr_ChegadaCliente` | char(5) | S |  |
| `dt_SaidaCliente` | datetime | S |  |
| `hr_SaidaCliente` | char(5) | S |  |
| `dt_ServicoSaida` | datetime | S |  |
| `qt_Distancia` | decimal(15,4) | S |  |
| `nr_OrdemOriginal` | int(10) | S |  |
| `ds_EnderecoPesquisado` | varchar(500) | S |  |
| `tp_IntegradoiTrack` | char(1) | S |  |
| `ds_UltimoRetornoiTrack` | varchar(200) | S |  |
| `id_iTrack` | int(10) | S |  |
| `tp_Transferencia` | char(1) | S |  |
| `tp_Entrega` | char(1) | S |  |
| `ds_LogIntegracaoMobile` | varchar(MAX) | S |  |
| `nr_LatitudeServico` | int(10) | S |  |
| `nr_LongitudeServico` | int(10) | S |  |
| `nr_LatitudeOcorrencia` | int(10) | S |  |
| `nr_LongitudeOcorrencia` | int(10) | S |  |
| `vl_Receita` | decimal(15,4) | S |  |
| `vl_Imposto` | decimal(15,4) | S |  |

#### `dbo.tbdMovimentoFinanceiro`

Linhas: **471.096**  
PK: `id_MovimentoFinanceiro`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_MovimentoFinanceiro` (PK) | int(10) | N |  |
| `id_Movimento` | int(10) | N |  |
| `id_Financeiro` | int(10) | N |  |
| `tp_Fechamento` | char(3) | N |  |
| `nr_OrdemSelecao` | int(10) | S |  |
| `id_Manifesto` | int(10) | S |  |
| `id_bennerfndocumentos` | int(10) | S |  |

#### `dbo.tbdFechamentoCliente`

Linhas: **558.827**  
PK: `id_Movimento`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` (PK) | int(10) | N |  |
| `id_Cliente` | int(10) | S |  |
| `id_Faturado` | int(10) | S |  |
| `vl_Faturado` | decimal(12,4) | S |  |
| `tp_Finalizado` | char(1) | S |  |
| `dt_Fechamento` | datetime | S |  |
| `ds_Grupo` | char(20) | S |  |
| `tp_Frete` | char(1) | S |  |
| `dt_AnulacaoCobranca` | datetime | S |  |

#### `dbo.tbdDimensao`

Linhas: **922.006**  
PK: `id_Dimensao`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Dimensao` (PK) | int(10) | N |  |
| `id_Movimento` | int(10) | S |  |
| `id_Cliente` | int(10) | S |  |
| `qt_Volume` | int(10) | S |  |
| `vl_Dimensao1` | decimal(8,4) | S |  |
| `vl_Dimensao2` | decimal(8,4) | S |  |
| `vl_Dimensao3` | decimal(8,4) | S |  |
| `kg_Mercadoria` | decimal(12,4) | S |  |
| `kg_PesoTaxado` | decimal(12,4) | S |  |
| `kg_PesoCubado` | decimal(12,4) | S |  |
| `id_FilialOrigem` | int(10) | S |  |
| `id_MovimentoFilial` | int(10) | S |  |
| `kg_PesoTaxadoOutra` | decimal(12,4) | S |  |
| `kg_PesoCubadoOutra` | decimal(12,4) | S |  |
| `qt_Lote` | int(10) | S |  |
| `kg_MercadoriaRealUnica` | decimal(12,4) | S |  |
| `cd_NotaFiscal` | char(10) | S |  |
| `vl_MetroCubico` | decimal(15,4) | S |  |
| `tp_GeloSeco` | char(1) | S |  |
| `tp_GeloGel` | char(1) | S |  |
| `tp_TempAmbiente` | char(1) | S |  |

#### `dbo.tbdTrackingOrders`

Linhas: **384.544**  
PK: `id_TrackingOrder`  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_TrackingOrder` (PK) | uniqueidentifier | N |  |
| `id_TrackingOrderType` | uniqueidentifier | N |  |
| `dt_Ocorrencia` | datetime | N |  |
| `ds_Observacoes` | nvarchar(MAX) | S |  |
| `id_Movimento` | int(10) | S |  |
| `id_PedidoColeta` | int(10) | S |  |

### DER — Relacionamentos Principais

O dtbTransporte tem 676 FKs declaradas. Hierarquia central:

    tbdMovimento (1) --|< tbdMovimentoDados (1:1)        [chave = idMovimento]
    tbdMovimento (1) --|< tbdMovimentoDestinatario (1:1) [chave = idMovimento]
    tbdMovimento (1) --|< tbdMovimentoNotaFiscal (N)     [1 mov = N notas]
    tbdMovimentoNotaFiscal (1) --|< tbdMovimentoProdutoNota (N) [1 NF = N produtos]
    tbdMovimento (1) --|< tbdOcorrenciaNota (N)          [1 mov = N ocorrencias]
    tbdMovimento (1) --|< tbdMovimentoHistorico (N)      [historico de status]
    tbdLoteCTe (1) --|< tbdLoteCTeMovimento (N)          [lote = N movimentos]
    tbdLoteCTe (1) --|< tbdNumeracaoCTe (N)              [numeracao sequencial CTe]
    tbdLoteCTe (1) --|< tbdManifestoMovimento (N)
    tbdMovimento (1) --|< tbdMovimentoFinanceiro (1:1)   [dados financeiros do frete]
    tbdMovimento (1) --|< tbdFechamentoCliente (N)       [fechamentos mensais]
    tbdDimensao -> tbdMovimento                          [dimensoes de carga por movimento]

### Regras de Negocio Inferidas

- `tbdMovimento` (570k) e a tabela de fatos central — cada linha e 1 entrega/coleta
- `tbdMovimentoProdutoNota` (33M) e a tabela mais volumosa — lista todos os SKUs de todas as NFs
- `tbdUltimaOcorrenciaNota` (682k) e uma tabela de snapshot da ultima ocorrencia por nota (evita GROUP BY em tempo real)
- `tb3*` (14 tabelas) sao especificas para relatorio ANTT norma 3402 (obrigatorio para transportadoras)
- `LOG_CEP` (660k) e `LOG_LOGRADOURO` (778k) sao logs de consultas de CEP ao CORREIOS
- `tbdTarefaAgendadaLog` (1,1M) registra execucoes de tarefas agendadas do TMS
- `tbdCTeMovimentoPdf` (604k) armazena PDFs de CTe em formato binario/referencia
- `tbdTrackingOrders` (384k) integra rastreamento com marketplaces (B2W, VIA, etc)
- `tbdFechamentoCliente` (558k) controla faturamento e fechamento mensal por cliente

---

## 8. dtbCTe2026

**Proposito:** Arquivo de documentos fiscais XML — CTe (Conhecimento de Transporte eletronico) e MDFe (Manifesto Eletronico de Documentos Fiscais) para o ano 2026. Tabelas particionadas em 5 shards fisicos (sufixo 01 a 05) para distribuicao de carga.

**Schema:** `dbo` | **Tabelas:** 30 (6 tipos x 5 shards) | **Views:** 0 | **PKs:** 0 (integridade por aplicacao)

### Estrutura de Particoes

| Tipo de Documento | Shards | Linhas Totais | Descricao |
|-------------------|--------|---------------|-----------|
| tbdCTeXMLMovimento | 01-05 | 95.687 | XML completo do CTe de cada movimento |
| tbdCTeXMLLoteRetorno | 01-05 | 40.578 | XML de retorno do SEFAZ por lote de envio |
| tbdCTeXMLMovimentoCanc | 01-05 | 575 | XML de CTe cancelados |
| tbdCTeXMLCartaCorrecao | 01-05 | 37 | XML de Cartas de Correcao (CC-e) |
| tbdMDFeXMLManifesto | 01-05 | 2.697 | XML de MDF-e emitidos |
| tbdMDFeXMLManifestoEncerrado | 01-05 | 4.623 | XML de MDF-e encerrados |

### Distribuicao por Shard

| Shard | tbdCTeXMLMovimento | tbdCTeXMLLoteRetorno | tbdCTeXMLMovimentoCanc | tbdMDFeXMLManifesto | tbdMDFeXMLManifestoEncerrado |
|-------|-------------------|---------------------|----------------------|--------------------|-----------------------------|
| 01 | 21.949 | 9.701 | 102 | 732 | 1.118 |
| 02 | 21.007 | 8.346 | 155 | 520 | 948 |
| 03 | 24.447 | 10.383 | 131 | 662 | 1.197 |
| 04 | 20.026 | 9.172 | 109 | 569 | 997 |
| 05 | 8.258 | 2.976 | 78 | 214 | 363 |

### MER — Estrutura das Tabelas

Todos os tipos seguem a mesma estrutura de colunas. Documentando o shard 01 de cada tipo como referencia:

#### `dbo.tbdCTeXMLMovimento01`

Linhas: **21.949**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` | int(10) | S |  |
| `ds_XML` | varchar(MAX) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

#### `dbo.tbdCTeXMLLoteRetorno01`

Linhas: **9.701**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Lote` | int(10) | S |  |
| `ds_XML` | varchar(MAX) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

#### `dbo.tbdCTeXMLMovimentoCanc01`

Linhas: **102**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` | int(10) | S |  |
| `ds_XML` | text(2147483647) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

#### `dbo.tbdCTeXMLCartaCorrecao01`

Linhas: **6**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Movimento` | int(10) | S |  |
| `ds_XML` | text(2147483647) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

#### `dbo.tbdMDFeXMLManifesto01`

Linhas: **732**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Manifesto` | int(10) | S |  |
| `id_Estado` | int(10) | S |  |
| `ds_XML` | varchar(MAX) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

#### `dbo.tbdMDFeXMLManifestoEncerrado01`

Linhas: **1.118**  

| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| `id_Manifesto` | int(10) | S |  |
| `id_Estado` | int(10) | S |  |
| `ds_XML` | varchar(MAX) | S |  |
| `dt_XML` | datetime | S |  |
| `ds_Inclusao` | varchar(100) | S |  |
| `ds_Alteracao` | varchar(100) | S |  |

### DER — Relacionamentos

Sem FKs declaradas. Relacionamento logico com dtbTransporte:

    dtbCTe2026.tbdCTeXMLMovimento.* -> dtbTransporte.tbdLoteCTeMovimento.idMovimento
    dtbCTe2026.tbdCTeXMLLoteRetorno.* -> dtbTransporte.tbdLoteCTe.idLote
    dtbCTe2026.tbdMDFeXMLManifesto.* -> dtbTransporte.tbdManifestoMovimento.idManifesto

### Regras de Negocio Inferidas

- Banco criado anualmente (`2026` no nome) — provavelmente existe dtbCTe2025, dtbCTe2024, etc
- Particionamento 01-05 distribui carga de escrita entre 5 particoes ativas
- Armazena XML bruto completo (provavelmente em campo `xml` ou `varbinary`) para reprocessamento e auditoria fiscal
- Sem PKs: insercao rapida sem overhead de indices clustered (write-heavy)
- `tbdCTeXMLMovimentoCanc`: cancelamentos representam ~0,6% dos CTe emitidos (saudavel)
- `tbdCTeXMLCartaCorrecao`: muito baixo volume indica poucas correcoes (qualidade de emissao boa)
- MDFe encerrado > MDFe aberto indica boa higiene operacional (manifestos fechados apos entrega)

---

---

## Apendice A — Visao Consolidada de Volume

| Banco | Tabelas | Views | Colunas | FKs | Registros Estimados |
|-------|---------|-------|---------|-----|---------------------|
| HangFireWMS | 11 | 0 | 42 | 2 | < 1.000 (inativo) |
| VTCLOG | 11 | 40 | 592 | 0 | ~39M (lote_estoque_lpn_data domina) |
| VTCLOG_EXT | 10 | 29 | 421 | 0 | ~44M |
| WMSRX | 713 | 119 | 5.674 | 905 | ~45M+ (pedido_item_volume domina) |
| WMSRX_EXT | 707 | 119 | 5.622 | 905 | Similar ao WMSRX |
| WMSRX_EXT2 | 713 | 119 | 5.674 | 905 | Identico ao WMSRX |
| dtbTransporte | 1.542 | 28 | 23.019 | 676 | ~50M+ (tbdMovimentoProdutoNota domina) |
| dtbCTe2026 | 30 | 0 | 160 | 0 | ~145k CTe + ~7k MDFe (ano corrente) |
| **Total** | **3.747** | **454** | **41.204** | **3.393** | **~200M+** |

---

## Apendice B — Glossario de Termos

| Termo | Significado |
|-------|-------------|
| **WMS** | Warehouse Management System — sistema de gerenciamento de armazem (WMSRX, VTCLOG) |
| **TMS** | Transport Management System — sistema de gestao de transporte (dtbTransporte) |
| **LPN** | License Plate Number — etiqueta unica por caixa/pallet para rastreabilidade |
| **CTe** | Conhecimento de Transporte eletronico — documento fiscal obrigatorio por SEFAZ |
| **MDFe** | Manifesto de Documentos Fiscais Eletronico — agrupa CTes por viagem/veiculo |
| **EDI** | Electronic Data Interchange — integracao eletronica com clientes (pedidos/notas) |
| **NF** | Nota Fiscal — documento fiscal de entrada/saida de mercadoria |
| **CC-e** | Carta de Correcao eletronica — correcao de campo nao-critico do CTe |
| **Picking** | Separacao fisica de itens do estoque para atender pedidos |
| **Sorter** | Esteira automatizada de classificacao de volumes por destino |
| **GRU** | Aeroporto Internacional de Guarulhos — localizacao da operacao logistica |
| **EXT** | Extensao — banco espelho para filial/campus secundario |
| **def_** | Prefixo de tabelas de definicao/configuracao no WMS |
| **tbd** | 'Table Data' — prefixo padrao VTCLog para tabelas de dados no TMS |
| **tb3** | Tabelas de integracao ANTT (norma 3402 para transportadoras) |
| **ANTT** | Agencia Nacional de Transportes Terrestres |
| **SEFAZ** | Secretaria da Fazenda — autoridade emissora/validadora de CTe e MDFe |

---

## Apendice C — Padroes de Nomenclatura

### WMSRX (WMS)

- **`def_`**: tabelas de configuracao (parâmetros, tipos, regras de negocio)
- **`param_`**: parametros operacionais por cliente/operacao
- **`pedido_`**: tudo relacionado ao ciclo de pedidos
- **`lote_`**: controle de lotes de produtos (shelf life, rastreabilidade)
- **`lpn_`**: License Plate Number (embalagem unitaria)
- **`endereco_`**: posicoes fisicas no armazem (rua, andar, posicao)
- **`log_`**: logs operacionais e de integracao
- **`AspNet`**: framework de identidade ASP.NET (operadores do WMS)
- **`_conf`**: sufixo indica tabela de conferencia (checkout de saida)
- **Sufixo data** (ex: `_230808`): snapshot congelado de data especifica

### dtbTransporte (TMS)

- **`tbd`**: prefixo padrao (1.490 tabelas) — todo o dominio do TMS
- **`tb3`**: tabelas ANTT (norma 3402)
- **`LOG_`**: logs de consultas externas (CEP, logradouro)
- **`tbdMovimento*`**: cluster de tabelas do movimento (entrega/coleta)
- **`tbdLoteCTe*`**: cluster de tabelas de lotes de CTe
- **`tbdMDFe*`**: cluster de tabelas de MDF-e
- **`tbdDimensao*`**: dimensoes fisicas de carga para calculo de frete

### dtbCTe2026

- **`tbd[Tipo]XML[SubTipo][NN]`**: XML fiscal + tipo + shard 01-05
- Pattern: `tbdCTeXMLMovimento01` = CTe > XML > Movimento > Shard 1

---

## Apendice D — Guia de Queries BI Recomendadas

### Estoque atual por produto/lote (VTCLOG)

    SELECT * FROM VTCLOG.dbo.vwExcel_Estoque WITH (NOLOCK)

### Movimentos WMS em tempo real (WMSRX)

    SELECT p.cod_pedido, p.dt_inclusao, pi.cod_produto, pv.numero_volume
    FROM WMSRX.dbo.pedido p WITH (NOLOCK)
    JOIN WMSRX.dbo.pedido_item pi WITH (NOLOCK) ON pi.cod_pedido = p.cod_pedido
    JOIN WMSRX.dbo.pedido_volume pv WITH (NOLOCK) ON pv.cod_pedido = p.cod_pedido
    WHERE p.dt_inclusao >= CAST(GETDATE() AS DATE)

### Volume expedido por dia (WMSRX)

    SELECT CAST(dt_checkout AS DATE) AS dia, COUNT(*) AS volumes
    FROM WMSRX.dbo.pedido_volume_finalizacao_checkout WITH (NOLOCK)
    WHERE dt_checkout >= DATEADD(DAY,-30,GETDATE())
    GROUP BY CAST(dt_checkout AS DATE)
    ORDER BY dia

### Ocorrencias de entrega por data (dtbTransporte)

    SELECT o.cdOcorrencia, o.dsOcorrencia, COUNT(*) AS qtd
    FROM dtbTransporte.dbo.tbdOcorrenciaNota o WITH (NOLOCK)
    WHERE o.dtOcorrencia >= DATEADD(DAY,-7,GETDATE())
    GROUP BY o.cdOcorrencia, o.dsOcorrencia
    ORDER BY qtd DESC

### CTe emitidos no mes (dtbCTe2026)

    SELECT COUNT(*) AS cte_emitidos
    FROM dtbCTe2026.dbo.tbdCTeXMLMovimento01 WITH (NOLOCK)
    -- Repetir para shards 02-05 e somar

---

*Documentacao gerada automaticamente em 2026-05-13 via consulta direta ao SQL Server VOET-SVM141112\\GRU_BI,1433 usando usuario somente-leitura usr_bi_gru.*

