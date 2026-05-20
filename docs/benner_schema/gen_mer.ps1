# gen_mer.ps1 — Generate MER and DER documentation for Benner ERP
# Run with: powershell -File gen_mer.ps1

$outDir = "E:\claudecode\claudecode\docs\benner_schema"
$colsCorpFile = "$outDir\BennerSistemaCorporativo_columns.csv"
$fksCorpFile  = "$outDir\BennerSistemaCorporativo_fks.csv"
$colsRhFile   = "$outDir\BennerRh_columns.csv"
$fksRhFile    = "$outDir\BennerRh_fks.csv"

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Starting MER/DER generation..."

# ─────────────────────────────────────────────
# HELPER: Get module prefix from table name
# ─────────────────────────────────────────────
function Get-Prefix([string]$tbl) {
    $pos = $tbl.IndexOf('_')
    if ($pos -le 0) { return 'OTHER' }
    return $tbl.Substring(0, $pos).ToUpper()
}

# ─────────────────────────────────────────────
# HELPER: Parse CSV data into tables dict
# ─────────────────────────────────────────────
function Parse-Columns([string]$filePath) {
    $tables  = [System.Collections.Generic.Dictionary[string,object]]::new()
    $order   = [System.Collections.Generic.List[string]]::new()
    $sr = [System.IO.StreamReader]::new($filePath, $true)
    $null = $sr.ReadLine()
    while (-not $sr.EndOfStream) {
        $line = $sr.ReadLine()
        $parts = $line -split ','
        if ($parts.Count -lt 8) { continue }
        $parts = $parts | ForEach-Object { ($_ -replace '^"','') -replace '"$','' }
        $tbl = $parts[1]
        $col = "$($parts[2])|$($parts[3])|$($parts[4])|$($parts[5])|$($parts[6])|$($parts[7])|$(if ($parts.Count -gt 8) { $parts[8] } else { '' })"
        if (-not $tables.ContainsKey($tbl)) {
            $tables[$tbl] = [System.Collections.Generic.List[string]]::new()
            $order.Add($tbl)
        }
        ($tables[$tbl]).Add($col)
    }
    $sr.Close()
    return @{ Tables = $tables; Order = $order }
}

function Parse-FKs([string]$filePath) {
    # Returns: dict[ParentTable -> list of "FK_NAME|ParentCol|RefTable|RefCol"]
    # Also builds RefTable -> list for counting inbound FKs
    $byParent = [System.Collections.Generic.Dictionary[string,object]]::new()
    $byRef    = [System.Collections.Generic.Dictionary[string,object]]::new()
    $sr = [System.IO.StreamReader]::new($filePath, $true)
    $null = $sr.ReadLine()
    while (-not $sr.EndOfStream) {
        $line = $sr.ReadLine()
        $parts = $line -split ','
        if ($parts.Count -lt 7) { continue }
        $parts = $parts | ForEach-Object { ($_ -replace '^"','') -replace '"$','' }
        $fkName   = $parts[0]
        $parentTb = $parts[2]
        $parentCo = $parts[3]
        $refTb    = $parts[5]
        $refCo    = $parts[6]
        $entry    = "$fkName|$parentCo|$refTb|$refCo"
        if (-not $byParent.ContainsKey($parentTb)) {
            $byParent[$parentTb] = [System.Collections.Generic.List[string]]::new()
        }
        ($byParent[$parentTb]).Add($entry)
        if (-not $byRef.ContainsKey($refTb)) {
            $byRef[$refTb] = [System.Collections.Generic.List[string]]::new()
        }
        ($byRef[$refTb]).Add($entry)
    }
    $sr.Close()
    return @{ ByParent = $byParent; ByRef = $byRef }
}

# ─────────────────────────────────────────────
# MODULE DESCRIPTIONS
# ─────────────────────────────────────────────
$corpModuleDesc = @{
    'BB'    = 'BennerBase — base do sistema de agência de viagens'
    'TR'    = 'Turismo — módulo principal de viagens e turismo'
    'ED'    = 'Educação — módulo educacional'
    'GN'    = 'Geral — tabelas compartilhadas'
    'K'     = 'Kernel — núcleo do sistema'
    'FN'    = 'Financeiro — módulo financeiro'
    'Z'     = 'Sistema — tabelas internas'
    'CT'    = 'Contabilidade — módulo contábil'
    'SB'    = 'SubContabilidade'
    'SEI'   = 'SEI — Sistema Eletrônico de Informações'
    'MF'    = 'Módulo Fiscal'
    'EDCF'  = 'EDC Fiscal'
    'PD'    = 'Pedido'
    'IE'    = 'Importação/Exportação'
    'CP'    = 'Compras'
    'CM'    = 'Comercial'
    'REINF' = 'REINF — obrigação fiscal'
    'PR'    = 'Projetos'
    'CN'    = 'Contratos'
    'OP'    = 'Operacional'
    'LC'    = 'Lançamentos'
    'AT'    = 'Ativo Fixo'
    'LA'    = 'Laudos/Análise'
    'TU'    = 'Turismo Utilitário'
    'CRM'   = 'CRM'
    'AE'    = 'Adiantamentos/Eventos'
    'FILIAIS' = 'Filiais (tabela raiz)'
    'OTHER' = 'Outros / sem prefixo de módulo'
}

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Loading BennerSistemaCorporativo columns..."
$corpData = Parse-Columns $colsCorpFile
$corpTables = $corpData.Tables
$corpOrder  = $corpData.Order
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Corp: $($corpTables.Count) tables"

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Loading BennerSistemaCorporativo FKs..."
$corpFKData = Parse-FKs $fksCorpFile
$corpFKByParent = $corpFKData.ByParent
$corpFKByRef    = $corpFKData.ByRef
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Corp FKs: $($corpFKByParent.Count) tables with outgoing FKs"

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Loading BennerRh columns..."
$rhData = Parse-Columns $colsRhFile
$rhTables = $rhData.Tables
$rhOrder  = $rhData.Order
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] RH: $($rhTables.Count) tables"

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Loading BennerRh FKs..."
$rhFKData = Parse-FKs $fksRhFile
$rhFKByParent = $rhFKData.ByParent
$rhFKByRef    = $rhFKData.ByRef
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] RH FKs: $($rhFKByParent.Count) tables with outgoing FKs"

# ─────────────────────────────────────────────
# HELPER: Write MER for a database
# ─────────────────────────────────────────────
function Write-MER([string]$outFile, [string]$dbName, $tables, $order, $fkByParent, $moduleDesc) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Writing $outFile ..."
    $sw = [System.IO.StreamWriter]::new($outFile, $false, [System.Text.Encoding]::UTF8)

    $sw.WriteLine("# MER — $dbName")
    $sw.WriteLine("")
    $sw.WriteLine("> Documento gerado automaticamente a partir do schema do banco de dados.")
    $sw.WriteLine("> Data de geração: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
    $sw.WriteLine("")

    # Group tables by module prefix
    $byModule = [System.Collections.Generic.Dictionary[string,object]]::new()
    $moduleOrder = [System.Collections.Generic.List[string]]::new()
    foreach ($tbl in $order) {
        $prefix = Get-Prefix $tbl
        if (-not $byModule.ContainsKey($prefix)) {
            $byModule[$prefix] = [System.Collections.Generic.List[string]]::new()
            $moduleOrder.Add($prefix)
        }
        ($byModule[$prefix]).Add($tbl)
    }

    # Count FKs per module
    $modFKCount = @{}
    foreach ($prefix in $moduleOrder) {
        $cnt = 0
        foreach ($tbl in ($byModule[$prefix])) {
            if ($fkByParent.ContainsKey($tbl)) {
                $cnt += ($fkByParent[$tbl]).Count
            }
        }
        $modFKCount[$prefix] = $cnt
    }

    # Overview table
    $sw.WriteLine("## Visão Geral")
    $sw.WriteLine("")
    $sw.WriteLine("| Módulo | Descrição | Tabelas | FKs (saída) |")
    $sw.WriteLine("|--------|-----------|---------|-------------|")
    foreach ($prefix in ($moduleOrder | Sort-Object)) {
        $desc = if ($moduleDesc.ContainsKey($prefix)) { $moduleDesc[$prefix] } else { $prefix }
        $tblCount = ($byModule[$prefix]).Count
        $fkCnt    = $modFKCount[$prefix]
        $sw.WriteLine("| $prefix | $desc | $tblCount | $fkCnt |")
    }
    $sw.WriteLine("")

    # Per-module sections
    foreach ($prefix in $moduleOrder) {
        $desc = if ($moduleDesc.ContainsKey($prefix)) { $moduleDesc[$prefix] } else { "$prefix — módulo $prefix" }
        $sw.WriteLine("---")
        $sw.WriteLine("")
        $sw.WriteLine("## Módulo $prefix — $desc")
        $sw.WriteLine("")

        foreach ($tbl in ($byModule[$prefix])) {
            $sw.WriteLine("### $tbl")
            $sw.WriteLine("")
            $sw.WriteLine("| Coluna | Tipo | Tamanho | Nulo | PK |")
            $sw.WriteLine("|--------|------|---------|------|----|")

            $cols = $tables[$tbl]
            foreach ($colStr in $cols) {
                $f = $colStr -split '\|'
                # f[0]=Column f[1]=Type f[2]=MaxLen f[3]=Nullable f[4]=Default f[5]=Pos f[6]=PK
                $colName  = $f[0]
                $colType  = $f[1]
                $maxLen   = if ($f[2]) { $f[2] } else { '-' }
                $nullable = if ($f[3] -eq 'YES') { 'Sim' } else { 'Não' }
                $pk       = if ($f[6] -eq 'PK') { 'PK' } else { '' }
                $sw.WriteLine("| $colName | $colType | $maxLen | $nullable | $pk |")
            }
            $sw.WriteLine("")

            # Relationships
            if ($fkByParent.ContainsKey($tbl)) {
                $sw.WriteLine("**Relacionamentos de $tbl**")
                $sw.WriteLine("")
                foreach ($fkEntry in ($fkByParent[$tbl])) {
                    $fe = $fkEntry -split '\|'
                    # fe[0]=FK_NAME fe[1]=ParentCol fe[2]=RefTable fe[3]=RefCol
                    $sw.WriteLine("- ``$tbl.$($fe[1])`` → ``$($fe[2]).$($fe[3])`` *(FK: $($fe[0]))*")
                }
                $sw.WriteLine("")
            }
        }
    }

    $sw.Flush()
    $sw.Close()
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Done: $outFile"
}

# ─────────────────────────────────────────────
# FILE 1: MER_BennerSistemaCorporativo.md
# ─────────────────────────────────────────────
Write-MER "$outDir\MER_BennerSistemaCorporativo.md" "BennerSistemaCorporativo" $corpTables $corpOrder $corpFKByParent $corpModuleDesc

# ─────────────────────────────────────────────
# FILE 2: MER_BennerRh.md
# ─────────────────────────────────────────────
# Build RH module descriptions from actual prefixes
$rhModuleDesc = @{
    'AA'    = 'AA — Avaliações/Análise'
    'AC'    = 'AC — Acesso/Controle'
    'AD'    = 'AD — Administração'
    'AF'    = 'AF — Ativo Fixo RH'
    'AG'    = 'AG — Agendamento'
    'AH'    = 'AH — módulo AH'
    'AI'    = 'AI — Inteligência Artificial/Integração'
    'AL'    = 'AL — Alertas'
    'AM'    = 'AM — Administração/Módulo'
    'AN'    = 'AN — Análise'
    'AP'    = 'AP — Aprovações'
    'AR'    = 'AR — Arquivo'
    'AS'    = 'AS — Assistência'
    'AT'    = 'AT — Atendimento/Ativo'
    'AU'    = 'AU — Auditoria'
    'AV'    = 'AV — Avaliação'
    'AX'    = 'AX — módulo AX'
    'BA'    = 'BA — Banco/Arquivo'
    'BB'    = 'BB — BennerBase RH'
    'BC'    = 'BC — módulo BC'
    'BD'    = 'BD — módulo BD'
    'BE'    = 'BE — módulo BE'
    'BF'    = 'BF — módulo BF'
    'BG'    = 'BG — módulo BG'
    'BI'    = 'BI — Business Intelligence'
    'BL'    = 'BL — módulo BL'
    'BM'    = 'BM — módulo BM'
    'BN'    = 'BN — módulo BN'
    'BP'    = 'BP — Benefícios/Plano'
    'BQ'    = 'BQ — módulo BQ'
    'BR'    = 'BR — Brasil/módulo'
    'BS'    = 'BS — módulo BS'
    'BT'    = 'BT — módulo BT'
    'BU'    = 'BU — módulo BU'
    'BV'    = 'BV — módulo BV'
    'BW'    = 'BW — módulo BW'
    'BX'    = 'BX — módulo BX'
    'BY'    = 'BY — módulo BY'
    'BZ'    = 'BZ — módulo BZ'
    'CA'    = 'CA — Cadastro'
    'CB'    = 'CB — módulo CB'
    'CC'    = 'CC — Centro de Custo'
    'CD'    = 'CD — módulo CD'
    'CE'    = 'CE — módulo CE'
    'CF'    = 'CF — Configurações'
    'CG'    = 'CG — módulo CG'
    'CH'    = 'CH — módulo CH'
    'CI'    = 'CI — módulo CI'
    'CJ'    = 'CJ — módulo CJ'
    'CK'    = 'CK — módulo CK'
    'CL'    = 'CL — Cálculo'
    'CM'    = 'CM — Comercial RH'
    'CO'    = 'CO — Colaboradores'
    'CP'    = 'CP — Compras RH'
    'CR'    = 'CR — módulo CR'
    'CS'    = 'CS — módulo CS'
    'CT'    = 'CT — Contabilidade RH'
    'CU'    = 'CU — módulo CU'
    'CV'    = 'CV — módulo CV'
    'CW'    = 'CW — módulo CW'
    'CX'    = 'CX — módulo CX'
    'CY'    = 'CY — módulo CY'
    'CZ'    = 'CZ — módulo CZ'
    'DA'    = 'DA — Dados/Análise'
    'DB'    = 'DB — módulo DB'
    'DC'    = 'DC — Documentos/Controle'
    'DD'    = 'DD — módulo DD'
    'DE'    = 'DE — Departamento'
    'DF'    = 'DF — módulo DF'
    'DG'    = 'DG — módulo DG'
    'DH'    = 'DH — módulo DH'
    'DI'    = 'DI — Dinâmica/Integração'
    'DJ'    = 'DJ — módulo DJ'
    'DK'    = 'DK — módulo DK'
    'DL'    = 'DL — módulo DL'
    'DM'    = 'DM — módulo DM'
    'DN'    = 'DN — módulo DN'
    'DP'    = 'DP — Departamento Pessoal'
    'DR'    = 'DR — módulo DR'
    'DS'    = 'DS — módulo DS'
    'DT'    = 'DT — módulo DT'
    'DU'    = 'DU — módulo DU'
    'DV'    = 'DV — módulo DV'
    'DW'    = 'DW — Data Warehouse'
    'DX'    = 'DX — módulo DX'
    'DY'    = 'DY — módulo DY'
    'DZ'    = 'DZ — módulo DZ'
    'EA'    = 'EA — módulo EA'
    'EB'    = 'EB — módulo EB'
    'EC'    = 'EC — módulo EC'
    'EF'    = 'EF — módulo EF'
    'EG'    = 'EG — módulo EG'
    'EH'    = 'EH — módulo EH'
    'EI'    = 'EI — módulo EI'
    'EJ'    = 'EJ — módulo EJ'
    'EL'    = 'EL — módulo EL'
    'EM'    = 'EM — módulo EM'
    'EN'    = 'EN — módulo EN'
    'EO'    = 'EO — módulo EO'
    'EP'    = 'EP — módulo EP'
    'EQ'    = 'EQ — módulo EQ'
    'ER'    = 'ER — módulo ER'
    'ES'    = 'ES — módulo ES'
    'ET'    = 'ET — módulo ET'
    'EU'    = 'EU — módulo EU'
    'EV'    = 'EV — módulo EV'
    'EW'    = 'EW — módulo EW'
    'EX'    = 'EX — módulo EX'
    'EY'    = 'EY — módulo EY'
    'EZ'    = 'EZ — módulo EZ'
    'FA'    = 'FA — Folha/Admissão'
    'FB'    = 'FB — módulo FB'
    'FC'    = 'FC — módulo FC'
    'FD'    = 'FD — módulo FD'
    'FE'    = 'FE — módulo FE'
    'FF'    = 'FF — Folha Financeiro'
    'FG'    = 'FG — módulo FG'
    'FH'    = 'FH — módulo FH'
    'FI'    = 'FI — Financeiro RH'
    'FJ'    = 'FJ — módulo FJ'
    'FK'    = 'FK — módulo FK'
    'FL'    = 'FL — módulo FL'
    'FM'    = 'FM — módulo FM'
    'FN'    = 'FN — Financeiro'
    'FO'    = 'FO — módulo FO'
    'FP'    = 'FP — Folha de Pagamento'
    'FQ'    = 'FQ — módulo FQ'
    'FR'    = 'FR — módulo FR'
    'FS'    = 'FS — módulo FS'
    'FT'    = 'FT — módulo FT'
    'FU'    = 'FU — módulo FU'
    'FV'    = 'FV — módulo FV'
    'FW'    = 'FW — módulo FW'
    'FX'    = 'FX — módulo FX'
    'FY'    = 'FY — módulo FY'
    'FZ'    = 'FZ — módulo FZ'
    'GA'    = 'GA — Gestão Administrativa'
    'GB'    = 'GB — módulo GB'
    'GC'    = 'GC — módulo GC'
    'GD'    = 'GD — módulo GD'
    'GE'    = 'GE — módulo GE'
    'GF'    = 'GF — módulo GF'
    'GG'    = 'GG — módulo GG'
    'GH'    = 'GH — módulo GH'
    'GI'    = 'GI — módulo GI'
    'GJ'    = 'GJ — módulo GJ'
    'GK'    = 'GK — módulo GK'
    'GL'    = 'GL — módulo GL'
    'GM'    = 'GM — módulo GM'
    'GN'    = 'GN — Geral'
    'GO'    = 'GO — módulo GO'
    'GP'    = 'GP — Gestão de Pessoas'
    'GQ'    = 'GQ — módulo GQ'
    'GR'    = 'GR — módulo GR'
    'GS'    = 'GS — módulo GS'
    'GT'    = 'GT — módulo GT'
    'GU'    = 'GU — módulo GU'
    'GV'    = 'GV — módulo GV'
    'GW'    = 'GW — módulo GW'
    'GX'    = 'GX — módulo GX'
    'GY'    = 'GY — módulo GY'
    'GZ'    = 'GZ — módulo GZ'
    'HA'    = 'HA — módulo HA'
    'HB'    = 'HB — módulo HB'
    'HC'    = 'HC — módulo HC'
    'HD'    = 'HD — módulo HD'
    'HE'    = 'HE — módulo HE'
    'HF'    = 'HF — módulo HF'
    'HG'    = 'HG — módulo HG'
    'HH'    = 'HH — módulo HH'
    'HI'    = 'HI — Hierarquia/Integração'
    'HJ'    = 'HJ — módulo HJ'
    'HK'    = 'HK — módulo HK'
    'HL'    = 'HL — módulo HL'
    'HM'    = 'HM — módulo HM'
    'HO'    = 'HO — módulo HO'
    'HP'    = 'HP — módulo HP'
    'HR'    = 'HR — Recursos Humanos'
    'HS'    = 'HS — módulo HS'
    'HT'    = 'HT — módulo HT'
    'HU'    = 'HU — módulo HU'
    'HV'    = 'HV — módulo HV'
    'HW'    = 'HW — módulo HW'
    'HX'    = 'HX — módulo HX'
    'HY'    = 'HY — módulo HY'
    'HZ'    = 'HZ — módulo HZ'
    'IA'    = 'IA — módulo IA'
    'IC'    = 'IC — módulo IC'
    'ID'    = 'ID — módulo ID'
    'IE'    = 'IE — módulo IE'
    'IF'    = 'IF — módulo IF'
    'IG'    = 'IG — módulo IG'
    'IH'    = 'IH — módulo IH'
    'II'    = 'II — módulo II'
    'IJ'    = 'IJ — módulo IJ'
    'IK'    = 'IK — módulo IK'
    'IL'    = 'IL — módulo IL'
    'IM'    = 'IM — módulo IM'
    'IN'    = 'IN — Integração/Indicadores'
    'IO'    = 'IO — módulo IO'
    'IP'    = 'IP — módulo IP'
    'IQ'    = 'IQ — módulo IQ'
    'IR'    = 'IR — Imposto de Renda'
    'IS'    = 'IS — módulo IS'
    'IT'    = 'IT — Integração/TI'
    'IU'    = 'IU — módulo IU'
    'IV'    = 'IV — módulo IV'
    'IW'    = 'IW — módulo IW'
    'IX'    = 'IX — módulo IX'
    'IY'    = 'IY — módulo IY'
    'IZ'    = 'IZ — módulo IZ'
    'JA'    = 'JA — módulo JA'
    'JB'    = 'JB — módulo JB'
    'JC'    = 'JC — Jornada/Controle'
    'JD'    = 'JD — módulo JD'
    'JE'    = 'JE — módulo JE'
    'JF'    = 'JF — módulo JF'
    'JG'    = 'JG — módulo JG'
    'JH'    = 'JH — módulo JH'
    'JI'    = 'JI — módulo JI'
    'JJ'    = 'JJ — módulo JJ'
    'JK'    = 'JK — módulo JK'
    'JL'    = 'JL — módulo JL'
    'JM'    = 'JM — módulo JM'
    'JN'    = 'JN — módulo JN'
    'JO'    = 'JO — módulo JO'
    'JP'    = 'JP — módulo JP'
    'JQ'    = 'JQ — módulo JQ'
    'JR'    = 'JR — módulo JR'
    'JS'    = 'JS — módulo JS'
    'JT'    = 'JT — módulo JT'
    'JU'    = 'JU — módulo JU'
    'JV'    = 'JV — módulo JV'
    'JW'    = 'JW — módulo JW'
    'JX'    = 'JX — módulo JX'
    'JY'    = 'JY — módulo JY'
    'JZ'    = 'JZ — módulo JZ'
    'K'     = 'K — Kernel'
    'LA'    = 'LA — Laudos/Análise'
    'LC'    = 'LC — Lançamentos'
    'PE'    = 'PE — Pessoal'
    'PF'    = 'PF — Pessoal/Funcionários'
    'PG'    = 'PG — módulo PG'
    'PH'    = 'PH — módulo PH'
    'PI'    = 'PI — módulo PI'
    'PJ'    = 'PJ — Pessoa Jurídica'
    'PK'    = 'PK — módulo PK'
    'PL'    = 'PL — Plano'
    'PM'    = 'PM — módulo PM'
    'PN'    = 'PN — módulo PN'
    'PO'    = 'PO — módulo PO'
    'PP'    = 'PP — módulo PP'
    'PQ'    = 'PQ — módulo PQ'
    'PR'    = 'PR — Projetos RH'
    'PS'    = 'PS — módulo PS'
    'PT'    = 'PT — módulo PT'
    'PU'    = 'PU — módulo PU'
    'PV'    = 'PV — módulo PV'
    'PW'    = 'PW — módulo PW'
    'PX'    = 'PX — módulo PX'
    'PY'    = 'PY — módulo PY'
    'PZ'    = 'PZ — módulo PZ'
    'RA'    = 'RA — Relatórios/Análise'
    'RB'    = 'RB — módulo RB'
    'RC'    = 'RC — módulo RC'
    'RD'    = 'RD — módulo RD'
    'RE'    = 'RE — módulo RE'
    'RF'    = 'RF — módulo RF'
    'RG'    = 'RG — módulo RG'
    'RH'    = 'RH — Recursos Humanos Principal'
    'RI'    = 'RI — módulo RI'
    'RJ'    = 'RJ — módulo RJ'
    'RK'    = 'RK — módulo RK'
    'RL'    = 'RL — módulo RL'
    'RM'    = 'RM — módulo RM'
    'RN'    = 'RN — módulo RN'
    'RO'    = 'RO — módulo RO'
    'RP'    = 'RP — módulo RP'
    'RQ'    = 'RQ — módulo RQ'
    'RR'    = 'RR — módulo RR'
    'RS'    = 'RS — módulo RS'
    'RT'    = 'RT — módulo RT'
    'RU'    = 'RU — módulo RU'
    'RV'    = 'RV — módulo RV'
    'RW'    = 'RW — módulo RW'
    'RX'    = 'RX — módulo RX'
    'RY'    = 'RY — módulo RY'
    'RZ'    = 'RZ — módulo RZ'
    'SA'    = 'SA — Saúde/Segurança'
    'SB'    = 'SB — SubContabilidade'
    'SC'    = 'SC — módulo SC'
    'SD'    = 'SD — módulo SD'
    'SE'    = 'SE — módulo SE'
    'SF'    = 'SF — módulo SF'
    'SG'    = 'SG — módulo SG'
    'SH'    = 'SH — módulo SH'
    'SI'    = 'SI — módulo SI'
    'SJ'    = 'SJ — módulo SJ'
    'SK'    = 'SK — módulo SK'
    'SL'    = 'SL — módulo SL'
    'SM'    = 'SM — módulo SM'
    'SN'    = 'SN — módulo SN'
    'SO'    = 'SO — módulo SO'
    'SP'    = 'SP — módulo SP'
    'SQ'    = 'SQ — módulo SQ'
    'SR'    = 'SR — módulo SR'
    'SS'    = 'SS — módulo SS'
    'ST'    = 'ST — módulo ST'
    'SU'    = 'SU — módulo SU'
    'SV'    = 'SV — módulo SV'
    'SW'    = 'SW — módulo SW'
    'SX'    = 'SX — módulo SX'
    'SY'    = 'SY — módulo SY'
    'SZ'    = 'SZ — módulo SZ'
    'TA'    = 'TA — módulo TA'
    'TB'    = 'TB — módulo TB'
    'TC'    = 'TC — módulo TC'
    'TD'    = 'TD — módulo TD'
    'TE'    = 'TE — módulo TE'
    'TF'    = 'TF — módulo TF'
    'TG'    = 'TG — módulo TG'
    'TH'    = 'TH — módulo TH'
    'TI'    = 'TI — Tecnologia da Informação'
    'TJ'    = 'TJ — módulo TJ'
    'TK'    = 'TK — módulo TK'
    'TL'    = 'TL — módulo TL'
    'TM'    = 'TM — módulo TM'
    'TN'    = 'TN — módulo TN'
    'TO'    = 'TO — módulo TO'
    'TP'    = 'TP — módulo TP'
    'TQ'    = 'TQ — módulo TQ'
    'TR'    = 'TR — Treinamento RH'
    'TS'    = 'TS — módulo TS'
    'TT'    = 'TT — módulo TT'
    'TU'    = 'TU — módulo TU'
    'TV'    = 'TV — módulo TV'
    'TW'    = 'TW — módulo TW'
    'TX'    = 'TX — módulo TX'
    'TY'    = 'TY — módulo TY'
    'TZ'    = 'TZ — módulo TZ'
    'UA'    = 'UA — módulo UA'
    'VC'    = 'VC — Vencimentos/Cargos'
    'VF'    = 'VF — módulo VF'
    'WF'    = 'WF — Workflow'
    'Z'     = 'Z — Sistema/Kernel'
    'ZA'    = 'ZA — módulo ZA'
    'ZB'    = 'ZB — módulo ZB'
    'OTHER' = 'Outros / sem prefixo de módulo'
}

Write-MER "$outDir\MER_BennerRh.md" "BennerRh" $rhTables $rhOrder $rhFKByParent $rhModuleDesc

# ─────────────────────────────────────────────
# FILE 3: DER_resumo.md — Top central entities
# ─────────────────────────────────────────────
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Building DER_resumo.md (top central entities)..."

# Combine both databases for the summary
$allRefCount = [System.Collections.Generic.Dictionary[string,int]]::new()
foreach ($tbl in $corpFKByRef.Keys) {
    $cnt = ($corpFKByRef[$tbl]).Count
    if ($allRefCount.ContainsKey($tbl)) { $allRefCount[$tbl] += $cnt }
    else { $allRefCount[$tbl] = $cnt }
}
foreach ($tbl in $rhFKByRef.Keys) {
    $cnt = ($rhFKByRef[$tbl]).Count
    if ($allRefCount.ContainsKey($tbl)) { $allRefCount[$tbl] += $cnt }
    else { $allRefCount[$tbl] = $cnt }
}

# Top 60 most referenced tables
$top60 = $allRefCount.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 60
$top60Set = [System.Collections.Generic.HashSet[string]]::new()
foreach ($e in $top60) { $null = $top60Set.Add($e.Key) }

# Build Mermaid for top 60
$sw = [System.IO.StreamWriter]::new("$outDir\DER_resumo.md", $false, [System.Text.Encoding]::UTF8)
$sw.WriteLine("# DER — Resumo de Entidades Centrais")
$sw.WriteLine("")
$sw.WriteLine("> Diagrama de Entidade-Relacionamento (ERD) mostrando as 60 entidades mais referenciadas por chaves estrangeiras.")
$sw.WriteLine("> Gerado automaticamente a partir do schema dos bancos BennerSistemaCorporativo e BennerRh.")
$sw.WriteLine("> Data: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
$sw.WriteLine("")

# Table: most referenced entities
$sw.WriteLine("## Tabela: Entidades Mais Referenciadas")
$sw.WriteLine("")
$sw.WriteLine("| # | Tabela | FKs Apontando |")
$sw.WriteLine("|---|--------|---------------|")
$rank = 1
foreach ($e in $top60) {
    $sw.WriteLine("| $rank | $($e.Key) | $($e.Value) |")
    $rank++
}
$sw.WriteLine("")

# Build ERD - include top entities and their FK relationships among themselves
$sw.WriteLine("## Diagrama ERD (Mermaid)")
$sw.WriteLine("")
$sw.WriteLine('```mermaid')
$sw.WriteLine("erDiagram")

# Add entities with their PK columns
foreach ($e in $top60) {
    $tbl = $e.Key
    $cols = $null
    if ($corpTables.ContainsKey($tbl)) { $cols = $corpTables[$tbl] }
    elseif ($rhTables.ContainsKey($tbl)) { $cols = $rhTables[$tbl] }

    if ($cols -ne $null) {
        # Sanitize table name for Mermaid (replace spaces, keep alphanumeric and underscore)
        $safeTbl = $tbl -replace '[^A-Za-z0-9_]','_'
        $sw.WriteLine("    $safeTbl {")
        $shown = 0
        foreach ($colStr in $cols) {
            if ($shown -ge 8) { break }  # limit to 8 columns for readability
            $f = $colStr -split '\|'
            $colName = $f[0] -replace '[^A-Za-z0-9_]','_'
            $colType = $f[1] -replace '[^A-Za-z0-9]','_'
            $pk = if ($f[6] -eq 'PK') { ' PK' } else { '' }
            $sw.WriteLine("        $colType $colName$pk")
            $shown++
        }
        $sw.WriteLine("    }")
    }
}

# Add relationships between top entities
$addedRels = [System.Collections.Generic.HashSet[string]]::new()
# Check corp FKs
foreach ($parentTbl in $top60Set) {
    if ($corpFKByParent.ContainsKey($parentTbl)) {
        foreach ($fkEntry in ($corpFKByParent[$parentTbl])) {
            $fe = $fkEntry -split '\|'
            $refTbl = $fe[2]
            if ($top60Set.Contains($refTbl) -and $parentTbl -ne $refTbl) {
                $relKey = "${parentTbl}__${refTbl}"
                if (-not $addedRels.Contains($relKey)) {
                    $null = $addedRels.Add($relKey)
                    $safePar = $parentTbl -replace '[^A-Za-z0-9_]','_'
                    $safeRef = $refTbl -replace '[^A-Za-z0-9_]','_'
                    $sw.WriteLine("    $safePar }o--|| $safeRef : `"FK`"")
                }
            }
        }
    }
}
# Check RH FKs
foreach ($parentTbl in $top60Set) {
    if ($rhFKByParent.ContainsKey($parentTbl)) {
        foreach ($fkEntry in ($rhFKByParent[$parentTbl])) {
            $fe = $fkEntry -split '\|'
            $refTbl = $fe[2]
            if ($top60Set.Contains($refTbl) -and $parentTbl -ne $refTbl) {
                $relKey = "${parentTbl}__${refTbl}"
                if (-not $addedRels.Contains($relKey)) {
                    $null = $addedRels.Add($relKey)
                    $safePar = $parentTbl -replace '[^A-Za-z0-9_]','_'
                    $safeRef = $refTbl -replace '[^A-Za-z0-9_]','_'
                    $sw.WriteLine("    $safePar }o--|| $safeRef : `"FK`"")
                }
            }
        }
    }
}
$sw.WriteLine('```')
$sw.WriteLine("")
$sw.Flush()
$sw.Close()
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Done: DER_resumo.md"

# ─────────────────────────────────────────────
# FILE 4: DER_turismo.md — TR + TU + BB modules
# ─────────────────────────────────────────────
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Building DER_turismo.md (TR + TU + BB modules)..."

# Get all TR_, TU_, BB_ tables
$tourismTables = [System.Collections.Generic.HashSet[string]]::new()
foreach ($tbl in $corpOrder) {
    $prefix = Get-Prefix $tbl
    if ($prefix -eq 'TR' -or $prefix -eq 'TU' -or $prefix -eq 'BB') {
        $null = $tourismTables.Add($tbl)
    }
}
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Tourism tables: $($tourismTables.Count)"

# Find tables that have FK relationships with each other (within tourism + cross-reference tables)
$tourismFKTables = [System.Collections.Generic.HashSet[string]]::new()
$tourismFKRels   = [System.Collections.Generic.List[object]]::new()

foreach ($tbl in $tourismTables) {
    if ($corpFKByParent.ContainsKey($tbl)) {
        foreach ($fkEntry in ($corpFKByParent[$tbl])) {
            $fe = $fkEntry -split '\|'
            $refTbl = $fe[2]
            # Include if refTbl is in tourism OR is a commonly referenced shared table
            $refPrefix = Get-Prefix $refTbl
            if ($tourismTables.Contains($refTbl) -or $refPrefix -eq 'GN' -or $refPrefix -eq 'K' -or $refPrefix -eq 'FN') {
                $null = $tourismFKTables.Add($tbl)
                $null = $tourismFKTables.Add($refTbl)
                $tourismFKRels.Add([PSCustomObject]@{ Parent=$tbl; Child=$fe[1]; Ref=$refTbl; RefCol=$fe[3]; FK=$fe[0] })
            }
        }
    }
}
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Tourism FK tables: $($tourismFKTables.Count), Relationships: $($tourismFKRels.Count)"

# The number of relationships might be too large for a single Mermaid diagram.
# Let's cap at tables with most relationships and limit to 150 tables
$tblRelCount = @{}
foreach ($rel in $tourismFKRels) {
    if ($tblRelCount.ContainsKey($rel.Parent)) { $tblRelCount[$rel.Parent]++ }
    else { $tblRelCount[$rel.Parent] = 1 }
    if ($tblRelCount.ContainsKey($rel.Ref)) { $tblRelCount[$rel.Ref]++ }
    else { $tblRelCount[$rel.Ref] = 1 }
}

$topTourismTables = $tblRelCount.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 150
$topTourismSet = [System.Collections.Generic.HashSet[string]]::new()
foreach ($e in $topTourismTables) { $null = $topTourismSet.Add($e.Key) }

$sw = [System.IO.StreamWriter]::new("$outDir\DER_turismo.md", $false, [System.Text.Encoding]::UTF8)
$sw.WriteLine("# DER — Módulo Turismo (TR + TU + BB)")
$sw.WriteLine("")
$sw.WriteLine("> Diagrama de Entidade-Relacionamento para os módulos de Turismo (TR_), Turismo Utilitário (TU_) e BennerBase (BB_).")
$sw.WriteLine("> Inclui as 150 tabelas com mais relacionamentos FK, mais tabelas compartilhadas chave (GN_, K_, FN_).")
$sw.WriteLine("> Data: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
$sw.WriteLine("")

# Statistics section
$sw.WriteLine("## Estatísticas do Módulo")
$sw.WriteLine("")
$sw.WriteLine("| Prefixo | Descrição | Total de Tabelas |")
$sw.WriteLine("|---------|-----------|-----------------|")
$bbCount = ($corpOrder | Where-Object { (Get-Prefix $_) -eq 'BB' }).Count
$trCount = ($corpOrder | Where-Object { (Get-Prefix $_) -eq 'TR' }).Count
$tuCount = ($corpOrder | Where-Object { (Get-Prefix $_) -eq 'TU' }).Count
$sw.WriteLine("| BB | BennerBase — base do sistema de agência de viagens | $bbCount |")
$sw.WriteLine("| TR | Turismo — módulo principal de viagens e turismo | $trCount |")
$sw.WriteLine("| TU | Turismo Utilitário | $tuCount |")
$sw.WriteLine("")

$sw.WriteLine("## Tabela de Relacionamentos")
$sw.WriteLine("")
$sw.WriteLine("| Tabela Origem | Coluna | Tabela Destino | Coluna Destino | FK |")
$sw.WriteLine("|---------------|--------|---------------|----------------|-----|")
foreach ($rel in ($tourismFKRels | Sort-Object Parent, Child)) {
    if ($topTourismSet.Contains($rel.Parent) -and $topTourismSet.Contains($rel.Ref)) {
        $sw.WriteLine("| $($rel.Parent) | $($rel.Child) | $($rel.Ref) | $($rel.RefCol) | $($rel.FK) |")
    }
}
$sw.WriteLine("")

# Mermaid ERD - split into sub-diagrams by module to keep manageable size
$sw.WriteLine("## Diagrama ERD — BennerBase (BB_)")
$sw.WriteLine("")
$sw.WriteLine('```mermaid')
$sw.WriteLine("erDiagram")

$bbInTop = $topTourismSet | Where-Object { (Get-Prefix $_) -eq 'BB' }
foreach ($tbl in ($bbInTop | Sort-Object)) {
    if (-not $corpTables.ContainsKey($tbl)) { continue }
    $safeTbl = $tbl -replace '[^A-Za-z0-9_]','_'
    $sw.WriteLine("    $safeTbl {")
    $shown = 0
    foreach ($colStr in ($corpTables[$tbl])) {
        if ($shown -ge 6) { break }
        $f = $colStr -split '\|'
        $colName = $f[0] -replace '[^A-Za-z0-9_]','_'
        $colType = ($f[1] -replace '[^A-Za-z0-9]','_').PadRight(4).Substring(0,4).Trim()
        $pk = if ($f[6] -eq 'PK') { ' PK' } else { '' }
        $sw.WriteLine("        $colType $colName$pk")
        $shown++
    }
    $sw.WriteLine("    }")
}
$addedBBRels = [System.Collections.Generic.HashSet[string]]::new()
foreach ($rel in $tourismFKRels) {
    if ($topTourismSet.Contains($rel.Parent) -and $topTourismSet.Contains($rel.Ref)) {
        $pPfx = Get-Prefix $rel.Parent
        $rPfx = Get-Prefix $rel.Ref
        if (($pPfx -eq 'BB' -or $rPfx -eq 'BB') -and ($pPfx -eq 'BB' -or $pPfx -eq 'GN' -or $pPfx -eq 'K') -and ($rPfx -eq 'BB' -or $rPfx -eq 'GN' -or $rPfx -eq 'K')) {
            $relKey = "$($rel.Parent)__$($rel.Ref)"
            if (-not $addedBBRels.Contains($relKey)) {
                $null = $addedBBRels.Add($relKey)
                $safePar = $rel.Parent -replace '[^A-Za-z0-9_]','_'
                $safeRef = $rel.Ref -replace '[^A-Za-z0-9_]','_'
                $sw.WriteLine("    $safePar }o--|| $safeRef : `"FK`"")
            }
        }
    }
}
$sw.WriteLine('```')
$sw.WriteLine("")

$sw.WriteLine("## Diagrama ERD — Turismo Principal (TR_)")
$sw.WriteLine("")
$sw.WriteLine('```mermaid')
$sw.WriteLine("erDiagram")
$trInTop = $topTourismSet | Where-Object { (Get-Prefix $_) -eq 'TR' }
foreach ($tbl in ($trInTop | Sort-Object)) {
    if (-not $corpTables.ContainsKey($tbl)) { continue }
    $safeTbl = $tbl -replace '[^A-Za-z0-9_]','_'
    $sw.WriteLine("    $safeTbl {")
    $shown = 0
    foreach ($colStr in ($corpTables[$tbl])) {
        if ($shown -ge 6) { break }
        $f = $colStr -split '\|'
        $colName = $f[0] -replace '[^A-Za-z0-9_]','_'
        $colType = ($f[1] -replace '[^A-Za-z0-9]','_').PadRight(4).Substring(0,4).Trim()
        $pk = if ($f[6] -eq 'PK') { ' PK' } else { '' }
        $sw.WriteLine("        $colType $colName$pk")
        $shown++
    }
    $sw.WriteLine("    }")
}
$addedTRRels = [System.Collections.Generic.HashSet[string]]::new()
foreach ($rel in $tourismFKRels) {
    if ($topTourismSet.Contains($rel.Parent) -and $topTourismSet.Contains($rel.Ref)) {
        $pPfx = Get-Prefix $rel.Parent
        $rPfx = Get-Prefix $rel.Ref
        if ($pPfx -eq 'TR' -or $rPfx -eq 'TR') {
            $relKey = "$($rel.Parent)__$($rel.Ref)"
            if (-not $addedTRRels.Contains($relKey)) {
                $null = $addedTRRels.Add($relKey)
                $safePar = $rel.Parent -replace '[^A-Za-z0-9_]','_'
                $safeRef = $rel.Ref -replace '[^A-Za-z0-9_]','_'
                $sw.WriteLine("    $safePar }o--|| $safeRef : `"FK`"")
            }
        }
    }
}
$sw.WriteLine('```')
$sw.WriteLine("")

$sw.WriteLine("## Diagrama ERD — Turismo Utilitário (TU_) e Tabelas Compartilhadas")
$sw.WriteLine("")
$sw.WriteLine('```mermaid')
$sw.WriteLine("erDiagram")
$tuGnInTop = $topTourismSet | Where-Object { $pf = Get-Prefix $_; $pf -eq 'TU' -or $pf -eq 'GN' -or $pf -eq 'K' -or $pf -eq 'FN' }
foreach ($tbl in ($tuGnInTop | Sort-Object)) {
    $cols = $null
    if ($corpTables.ContainsKey($tbl)) { $cols = $corpTables[$tbl] }
    if ($cols -eq $null) { continue }
    $safeTbl = $tbl -replace '[^A-Za-z0-9_]','_'
    $sw.WriteLine("    $safeTbl {")
    $shown = 0
    foreach ($colStr in $cols) {
        if ($shown -ge 6) { break }
        $f = $colStr -split '\|'
        $colName = $f[0] -replace '[^A-Za-z0-9_]','_'
        $colType = ($f[1] -replace '[^A-Za-z0-9]','_').PadRight(4).Substring(0,4).Trim()
        $pk = if ($f[6] -eq 'PK') { ' PK' } else { '' }
        $sw.WriteLine("        $colType $colName$pk")
        $shown++
    }
    $sw.WriteLine("    }")
}
$addedTURels = [System.Collections.Generic.HashSet[string]]::new()
foreach ($rel in $tourismFKRels) {
    if ($topTourismSet.Contains($rel.Parent) -and $topTourismSet.Contains($rel.Ref)) {
        $pPfx = Get-Prefix $rel.Parent
        $rPfx = Get-Prefix $rel.Ref
        if ($pPfx -eq 'TU' -or $rPfx -eq 'TU' -or (($pPfx -eq 'GN' -or $pPfx -eq 'K') -and ($rPfx -eq 'GN' -or $rPfx -eq 'K'))) {
            $relKey = "$($rel.Parent)__$($rel.Ref)"
            if (-not $addedTURels.Contains($relKey)) {
                $null = $addedTURels.Add($relKey)
                $safePar = $rel.Parent -replace '[^A-Za-z0-9_]','_'
                $safeRef = $rel.Ref -replace '[^A-Za-z0-9_]','_'
                $sw.WriteLine("    $safePar }o--|| $safeRef : `"FK`"")
            }
        }
    }
}
$sw.WriteLine('```')
$sw.WriteLine("")
$sw.Flush()
$sw.Close()
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Done: DER_turismo.md"

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ALL FILES GENERATED SUCCESSFULLY"
