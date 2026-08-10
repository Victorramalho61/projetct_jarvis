# Auditoria — Report_ACCIONA_Geral (qualidade de dados / reconciliação)

Processo para auditar o extrato de viagens da ACCIONA (aéreo/hotel/carro) que o
Victor recebe em CSV e usa no relatório mensal enviado à operação. Existe
porque a ACCIONA reclama recorrentemente que "os dados não batem" e o
comercial some com o botão de reconciliação quando algo não fecha. Este doc
existe para repetir a auditoria (e a correção automática) em uma sessão nova
sem redescobrir a lógica do zero — basta pedir "audita o report da ACCIONA
desse mês".

Não confundir com `docs/relatorio-acciona-freshdesk.md` — aquele é sobre
tickets de suporte (Freshdesk); este é sobre o extrato financeiro/operacional
de viagens (voos, hotéis, carros) fornecido por outro sistema (provavelmente
um OBT/TMC — nomes de coluna em espanhol).

## Fonte de dados

- Arquivo recebido manualmente, salvo em
  `C:\Users\victor.ramalho\Desktop\Report_ACCIONA_Geral <N>.csv` (o `<N>`
  varia a cada envio — confirmar o nome exato com `ls` no Desktop antes de
  rodar qualquer coisa).
- CSV separado por `;`, encoding **UTF-8 com BOM** (`utf-8-sig`), decimal
  `,` e milhar `.` (padrão pt-BR/es). ~2200 linhas, ~145 colunas por export
  mensal, cobrindo o ano corrente até o mês do envio (não é só o mês atual —
  vem o acumulado do ano).
- Coluna-chave de produto: `PRODUCTO NUEVO` (`Aereo`, `Hotel`, `Coche`,
  `Autobus`, `Servicios Varios`). Muita coluna só faz sentido para um
  produto — colunas de aéreo (`CABINA*`, `NROBILLETE`, `NV_TRAMO*`, etc.)
  ficam 0% preenchidas em linhas de Hotel e vice-versa. **Isso é esperado,
  não é bug** — só reportar como problema o que diverge do padrão do próprio
  tipo de produto.

## Passo 1 — carregar

```python
import pandas as pd
df = pd.read_csv('Report_ACCIONA_Geral <N>.csv', sep=';', encoding='utf-8-sig', low_memory=False)

def num(s):  # colunas numéricas vêm como texto com decimal ","
    return pd.to_numeric(s.astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False), errors='coerce')
```

Rodar sempre com `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` no terminal Windows,
senão nomes acentuados (ex. "Água") saem corrompidos no print (o dado em si
está correto em UTF-8 — é só a exibição no terminal).

## Passo 2 — taxa de preenchimento por coluna × produto

Cruzar `PRODUCTO NUEVO` com cada coluna (`isna()` ou string vazia/"nan") para
ver % preenchido. Separar os achados em 4 baldes — **só os 2 últimos são
"dado ruim" de fato**:

1. **Branco esperado por tipo de produto** (0% em colunas de outro produto) — não reportar.
2. **"Falso preenchido"** — campo vem com `0` em vez de branco quando não se
   aplica (`CATEGORIA HOTEL` e `NUM. NOCHES` = 0 em 100% das linhas de
   Aéreo). Não é erro, mas confunde quem faz pivot table — vale explicar.
3. **Gap crônico** (sempre foi assim, todo mês) — ex. `REGIMEN` (hotel)
   ~50-60% preenchido sempre; `PROYECTO` ~5-7%; `TARIFAPREDOMINANTE` ~1%
   (praticamente morto, considerar perguntar à fonte se ainda é alimentado).
4. **Regressão aguda recente** — comparar preenchimento mês a mês
   (`groupby(ANO,MES)`). Em ago/26 identificamos `NROFACTURA` e
   `TIPO TARIFA` caindo de ~95-100% (até maio/26) para 0-58% (jun-ago/26) —
   isso é o que dá pra levar como prova concreta de falha de feed pro
   fornecedor de dados, e é a causa mais provável de reclamação de "dados
   faltando".

## Passo 3 — reconciliação célula a célula ("dados que não batem")

Três checagens que capturaram problemas reais até agora:

**a) `IMPORTE TOTAL` vs `BASE IMPONIBLE TOTAL`** — devem ser iguais, exceto
quando há `TASAS AEREO` (taxa de embarque) somada. Calcular
`diff = IMPORTE TOTAL - BASE IMPONIBLE TOTAL` e `diff - TASAS AEREO`; o que
sobrar sem explicação (tolerância 0,02) é divergência real. No histórico,
~99,4% da divergência é só a taxa aérea (comportamento correto) — o resto
(normalmente linhas de `TIPO FACTURA/ABONO == 'Abono'`, ou seja notas de
crédito) precisa checagem manual, mas em geral converge para
`BASE IMPONIBLE TOTAL = IMPORTE TOTAL` quando `TASAS AEREO = 0` (~99% das
linhas seguem esse padrão — pode ser usado como correção automática de alta
confiança para os poucos casos de Abono divergente).

**b) `ID_ORGANIZADOR` fora do padrão** — deveria ser sempre um ID numérico
SAP. Classificar cada valor:

```python
import re
def classify_id(v):
    v = str(v)
    if v in ('nan','NaN',''): return 'Vazio'
    if re.fullmatch(r'\d+(\.0)?', v): return 'OK - numerico'
    if '@' in v and re.search(r'@\w+\.\w+', v): return 'Email/UUID no lugar do ID'
    if '@' in v: return 'Email malformado'
    if re.fullmatch(r'[A-ZÀ-Ú]+', v.upper()) and len(v) < 15: return 'So 1o nome (incompleto)'
    return 'Outro padrao invalido'
```

Historicamente ~9% das linhas vêm com e-mail, UUID (`xxxx-...@email.com`),
primeiro nome solto ou vazio no lugar do ID — **esse é o achado que o
comercial descreve como "e-mail" quando reclama de dado que não bate**.
Quebra qualquer agrupamento "por organizador" (mesma pessoa contada como
gente diferente).

**c) `NOMBRE_PASAJERO` inconsistente para o mesmo `ID_EMPLEADO`** — mesmo
funcionário gravado como `"NOME SOBRENOME"` numa linha e
`"SOBRENOME/NOME"` noutra (formatos trocados), às vezes com typo real
(`"LUCIANAS"` em vez de `"LUCIANA"`). Em alguns casos raros, o mesmo
`ID_EMPLEADO` tem nomes **sem nenhum sobrenome em comum** — isso não é typo,
é indício de cadastro compartilhado (ex. dependente/familiar no mesmo
perfil corporativo) e não deve ser tratado como erro de formatação.

## Passo 4 — resolução por associação (quando não há match exato)

Para os casos sem correspondência exata, usar similaridade de tokens em vez
de string exata (nomes vêm com ordem trocada, sufixos de sistema como
`(ADT)`, e às vezes truncados para o primeiro nome só):

```python
def tokens(name):
    name = re.sub(r'\(ADT\)|\(CHD\)|\(INF\)', '', str(name).upper())
    stop = {'MISS','MR','MRS','DE','DA','DO','DOS','DAS','E',''}
    return set(p for p in re.split(r'[\/\s]+', name) if p and p not in stop and len(p)>1)

def containment(a, b):  # bom para nome truncado ("HUGO" dentro de "HUGO CESAR VIANA MORAIS")
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0
```

- **`ID_ORGANIZADOR`**: achar, entre os nomes que têm ID numérico válido, o
  de maior `containment` com o nome/token inválido. Se houver mais de um ID
  numérico para o nome batido, escolher por frequência (maioria). Confiança
  final = `containment × share_da_maioria`.
- **`NOMBRE_PASAJERO`** por `ID_EMPLEADO`: clusterizar variantes de nome por
  *qualquer* token em comum entre pares (union-find — **não** exigir token
  comum entre todas as variantes ao mesmo tempo, isso mistura "mesma pessoa
  formatada diferente" com "pessoas diferentes no mesmo ID" e gera falso
  positivo). Dentro de cada cluster, padronizar pro nome mais frequente
  (empate → mais longo/completo). Se o `ID_EMPLEADO` tiver mais de um
  cluster (pessoas prováveis distintas), só associar as linhas minoritárias
  ao cluster majoritário se ele tiver >30% das linhas daquele ID.

**Regra de decisão usada (definida pelo Victor em 2026-08)**: aplicar a
correção automaticamente sempre que a confiança estimada for **> 30%**;
abaixo disso, deixar de fora para revisão manual. Toda correção aplicada por
associação (não por match exato) precisa ficar logada com o % de confiança e
o método usado, para poder ser revertida se a ACCIONA contestar.

## Saída — 3 arquivos, sempre no Desktop do Victor

| Arquivo | Conteúdo |
|---|---|
| `Report_ACCIONA_Geral <N>_AJUSTADO.csv` | cópia do CSV original, mesmo layout/separador/encoding, só com as células corrigidas (nunca reescrever colunas não tocadas — ler o resto como `dtype=str, keep_default_na=False` pra não reformatar números/datas por acidente) |
| `Log_Alteracoes_Automaticas_ACCIONA.xlsx` | uma aba por tipo de correção, colunas `Valor_anterior`, `Valor_novo`, `Metodo`, `Confianca_%` — trilha de auditoria completa |
| `Ajustes_Manuais_ACCIONA.xlsx` | o que sobrou sem confiança suficiente (< 30%) pra corrigir sozinho — precisa confirmação do RH/ACCIONA ou verificação manual no SAP |

Sempre **verificar depois de gerar**: recarregar original vs ajustado com
`dtype=str, keep_default_na=False`, comparar linha a linha
(`orig != adj`), confirmar que só as colunas esperadas mudaram e que a
contagem de linhas/colunas é idêntica. Já aconteceu de uma primeira versão
da lógica de cluster de nomes gerar sugestão errada (juntar duas pessoas
diferentes) — sempre revisar a amostra antes de fechar o arquivo, não
confiar de primeira no resultado do script.

## Referência

- Arquivo de origem: `Report_ACCIONA_Geral <N>.csv` no Desktop do Victor
  (nome varia a cada envio).
- Nenhum script fixo no repo ainda — todo o processo acima foi feito ad-hoc
  via `python3 -c "..."` num terminal Bash. Se isso for repetir todo mês,
  vale a pena consolidar num script único (`audit_acciona_report.py`) em vez
  de reescrever a lógica a cada sessão.
