# Fórmulas e Parâmetros - saniDmae - DSES

Este documento reúne, num só lugar, todas as fórmulas e todos os
parâmetros usados nos cálculos do plugin. Serve tanto de referência
técnica quanto de guia para quem for mexer no código (`calculo.py` é o
único arquivo que implementa as contas em si).

---

## 1) População e vazão própria da bacia

```
Hab = area_ha × densidade_hab_ha

Q (L/s) = Hab × qf × C × k1 × k2 / 86400
```

- `area_ha`: área da bacia em hectares (medida da geometria, com
  correção elipsoidal — ver seção 6).
- `densidade_hab_ha`: densidade populacional adotada (hab/ha), escolhida
  na seção 3 do painel.
- `qf`: consumo per capita de água (L/hab.dia).
- `C`: coeficiente de retorno esgoto/água (adimensional).
- `k1`: coeficiente do dia de maior consumo (adimensional).
- `k2`: coeficiente da hora de maior consumo (adimensional).
- `86400`: segundos em um dia (converte L/dia para L/s).

Implementado em `calculo.py`, função `calcular_vazao_bacia()`.

---

## 2) Vazão acumulada por coletor (cascata)

```
Vazao_acumulada(coletor) = Σ vazao_propria de todas as bacias vinculadas
                            diretamente a ele
                          + Σ vazao_acumulada de todos os coletores de
                            montante que apontam pra ele
```

O cálculo percorre a topologia definida pelo usuário na seção 2 do
painel (bacia → coletor, coletor → coletor de jusante), recursivamente,
com detecção de ciclos (se A → B → A por engano, o plugin avisa em vez
de entrar num loop infinito).

Implementado em `calculo.py`, função `calcular_tudo()` (função interna
`vazao_acumulada`, com memoização).

---

## 3) Declividade (inclinação) de um trecho

### 3a) A partir de cotas (forma recomendada)

```
Declividade (m/m) = (cota_inicio - cota_final) / comprimento_m
```

- `cota_inicio`: cota de montante do trecho (m).
- `cota_final`: cota de jusante do trecho (m).
- `comprimento_m`: comprimento da linha do coletor, medido com correção
  elipsoidal (ver seção 6) — não é o comprimento "no papel" se a camada
  estiver num CRS geográfico.

Usado no botão "Definir declividade por trecho" (seção 4). O resultado
vira uma **exceção** daquele coletor especificamente (ver seção 4
abaixo).

### 3b) Conversão % ↔ m/m

A interface sempre mostra/recebe a inclinação em **porcentagem** (mais
fácil de ler/digitar), mas o cálculo usa **m/m** internamente:

```
inclinacao_m_m = inclinacao_pct / 100
inclinacao_pct = inclinacao_m_m × 100
```

---

## 4) Parâmetros globais x exceções por trecho

Cada trecho usa, para os parâmetros `inclinacao` (S), `lamina_relativa`
(f) e `rugosidade` (n):

1. o valor da **exceção daquele coletor especificamente**, se existir;
2. senão, o **parâmetro global** do projeto.

```python
def _parametro_efetivo(nome, coletor_id, parametros_globais, excecoes_por_coletor):
    excecoes = excecoes_por_coletor.get(str(coletor_id), {})
    if nome in excecoes:
        return float(excecoes[nome])
    return float(parametros_globais[nome])
```

O valor efetivamente usado em cada trecho fica salvo no resultado
(`inclinacao_usada`) e é gravado no campo `S_USO_PCT` da camada de
coletores — dá pra conferir exatamente o que entrou na conta de cada
trecho.

---

## 5) Diâmetro calculado (fórmula de Manning)

```
D = ( (4 × Q × n) / (π × f × √S × 0,3969) ) ^ (3/8)
```

onde:
- `Q`: vazão acumulada do trecho, em **m³/s** (a vazão calculada em L/s
  é dividida por 1000 antes de entrar na fórmula).
- `n`: rugosidade de Manning (adimensional).
- `S`: inclinação/declividade (m/m).
- `f`: fator relativo à lâmina d'água, `f(h/D)` — ver tabela na seção 7.
- `0,3969`: coeficiente fixo, transcrito diretamente da planilha Excel que
  o usuário já usava (célula de fórmula original:
  `=((4*(Q/1000))*n)/(PI()*f*(S^(1/2))*0,3969))^(3/8)`). Não é um valor
  "clássico" da literatura de Manning-Strickler — é específico da
  planilha de referência do usuário, mantido aqui só pra bater com os
  números que ele já validava manualmente antes de usar o plugin.

Essa fórmula é **editável** no painel ("Editar parâmetros globais" →
campo "Fórmula do diâmetro"), avaliada com `eval()` num ambiente restrito
que só permite as variáveis `Q`, `n`, `S`, `f` e o módulo `math`. Se você
tiver uma planilha de referência com resultado diferente, ajuste a
fórmula até bater — ela não está travada no código.

Implementado em `calculo.py`, funções `calcular_diametro()` e
`calcular_tudo()`.

### Trecho crítico

```
critico = (dn_calculado > dn_existente)
```

O `dn_existente` é normalizado para metros antes da comparação (ver
seção 8 - unidade do DN existente).

---

## 6) Área e comprimento (correção elipsoidal)

**Nunca** use `geometria.area()` ou `geometria.length()` direto quando a
camada pode estar num CRS geográfico (graus) — o resultado viria em
graus² ou graus, um número sem sentido para hectares/metros.

O plugin usa `QgsDistanceArea` configurado com o elipsoide do projeto,
replicando exatamente o que o `$area` / `$length` da Calculadora de Campo
do QGIS fazem:

```python
da = QgsDistanceArea()
da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
da.setEllipsoid(QgsProject.instance().ellipsoid())

area_m2 = da.convertAreaMeasurement(da.measureArea(geom), QgsUnitTypes.AreaSquareMeters)
area_ha = area_m2 / 10000

comprimento_m = da.convertLengthMeasurement(da.measureLength(geom), QgsUnitTypes.DistanceMeters)
```

Implementado em `geo_utils.py` (`calcular_area_ha`, `calcular_comprimento_m`,
`nova_distance_area` — esta última monta um `QgsDistanceArea` uma vez só
para reaproveitar em loops com muitas feições, por performance).

---

## 7) Valores padrão (ao criar um banco novo)

| Parâmetro | Valor padrão | Unidade | Significado |
|---|---|---|---|
| `qf` | 150 | L/hab.dia | Consumo per capita de água |
| `C` | 0,8 | adimensional | Coeficiente de retorno |
| `k1` | 1,2 | adimensional | Coef. dia de maior consumo |
| `k2` | 1,5 | adimensional | Coef. hora de maior consumo |
| `inclinacao` (S) | 0,004 (0,4%) | m/m | Inclinação padrão do trecho |
| `lamina_relativa` (f) | 0,7 | adimensional | Fator f(h/D) — ver tabela abaixo |
| `rugosidade` (n) | 0,013 | adimensional | Coeficiente de Manning |
| `formula_diametro` | ver seção 5 | — | Fórmula do diâmetro calculado |
| `razao_h_d` | 0,75 (75%) | adimensional | Lâmina relativa h/D geométrica — só para tensão trativa (seção 11), não confundir com `lamina_relativa` acima |
| `peso_especifico` | 10000 | N/m³ | Peso específico do esgoto, para tensão trativa |
| `c_inf` | 0,0005 | L/s/m | Coeficiente de infiltração (seção 10) |
| `vazao_minima` | 1,5 | L/s | Vazão mínima de projeto por trecho (seção 10) |
| `dn_minimo` | 0,15 (150 mm) | m | Diâmetro mínimo de projeto (seção 11) |
| `n_pvc` | 0,010 | adimensional | Manning do PVC, só p/ velocidade final/crítica (seção 11) |
| `razao_h_d_reduzida` | 0,50 (50%) | adimensional | Lâmina aplicada automaticamente quando vf > vc (seção 11) |
| `espacamento_max_pv` | 80 | m | Espaçamento máximo entre poços de visita (seção 11) |

### Tabela de referência h/D → f(h/D)

| h/D | f(h/D) |
|-----|--------|
| 1,00 | 1,00 |
| 0,90 | 0,90 |
| 0,80 | 0,78 |
| 0,75 | 0,70 |
| 0,70 | 0,65 |
| 0,60 | 0,53 |
| 0,50 | 0,40 |

(Referência usada na planilha original do usuário; o valor padrão 0,7
corresponde a h/D = 0,75.)

### Densidades de referência (tabela RMSP)

| Descrição | hab/ha |
|---|---|
| Residencial de luxo (lote 800 m²) | 100 |
| Residencial médio (lote 450 m²) | 120 |
| Misto popular (lote 250 m²) | 150 |
| Misto residencial/comercial central (prédios 3-4 pav.) | 300 |
| Misto residencial/comercial central (edifícios 10-12 pav.) | 450 |
| Misto residencial-comercial-industrial (comércio/indústria leve) | 600 |
| Comercial da zona central (edifícios de escritório) | 1000 |

Implementado em `db.py`, `PARAMETROS_PADRAO` e `DENSIDADES_PADRAO`.

---

## 8) Unidade do DN existente (m ou mm)

O campo de diâmetro existente pode estar em metros (ex: 0,3) ou em
milímetros (ex: 300 — notação DN comum em projetos de rede). O plugin
tenta adivinhar pela mediana dos valores da camada (`mediana > 10` ⇒
assume mm), e converte para metros internamente antes de comparar com o
diâmetro calculado:

```
dn_existente_m = valor_bruto × (0.001 se mm, senão 1.0)
```

---

## 9) Sentido do fluxo (seta na simbologia)

A seta desenhada em cada trecho não segue a direção física de
digitalização da linha — ela segue o **vínculo lógico** (coletor →
coletor de jusante, configurado na seção 2). Para isso, o plugin calcula
automaticamente, a cada "Calcular tudo", se a linha foi desenhada no
sentido do fluxo ou ao contrário:

```
Para cada coletor com um coletor de jusante vinculado:
    compara as 4 combinações de distância entre as pontas dos dois
    trechos (início/fim do atual x início/fim do jusante)
    -> a ponta do trecho atual mais próxima de QUALQUER ponta do
       jusante é o "ponto de encontro" real entre eles
    -> se essa ponta for o FIM do trecho atual: direção correta (1)
    -> se for o INÍCIO: invertida (0), e a seta gira 180°
```

Esse resultado fica salvo no campo `DIRECAO_OK` da camada de coletores.
Implementado em `painel_calculo.py`, funções `_extremos_linha()` e
`_calcular_direcao_ok()`.

---

## 10) Vazão de infiltração e vazão mínima de projeto

Baseado no Termo de Referência oficial do SAMAE (Caxias do Sul) para redes
de esgotamento sanitário, item 6.3:

```
Q = Qd + Qinf + Qc
```

- `Qd`: vazão doméstica acumulada (seção 1/2 acima — por área/densidade
  ou micromedição).
- `Qinf`: vazão de infiltração. **Cada trecho contribui com a sua
  própria parcela**, que se acumula pela cascata igual a vazão
  doméstica:
  ```
  Qinf_trecho (L/s) = Lt (m) × Cinf (L/s/m)
  ```
  `Cinf` é o coeficiente de infiltração — a NBR 9649 recomenda entre
  0,00005 e 0,001 L/s/m (0,05 a 1,0 L/s.km), a ser justificado; o SAMAE
  adota **0,0005 L/s/m** como padrão (tubulação com junta elástica, sem
  lençol freático raso). Parâmetro editável (`c_inf`).
- `Qc`: vazão concentrada/singular (contribuições pontuais específicas,
  ex: indústrias). **Não modelada automaticamente** — se precisar,
  ajuste manualmente via exceção do trecho ou usando o campo "consumo"
  da micromedição num ponto específico.

Depois de somado `Qd + Qinf`, se o total ficar abaixo da **vazão mínima
de projeto**, adota-se o mínimo:

```
Q_final = max(Qd + Qinf, Q_minima)
```

A NBR 9649 admite `Q_minima = 1,5 L/s` (vazão correspondente ao pico
instantâneo de descarga de vaso sanitário) — parâmetro editável
(`vazao_minima`).

Implementado em `calculo.py`, funções `calcular_vazao_infiltracao()` e
dentro de `calcular_tudo()` (funções internas `vazao_domestica_acumulada`
e `vazao_infiltracao_acumulada`, cada uma com sua própria memoização,
somadas e só então comparadas com a vazão mínima).

O comprimento de cada trecho (`Lt`) vem, em ordem de prioridade: (1) do
comprimento salvo no banco se você já rodou "Definir declividade por
trecho" naquele coletor (já mede o comprimento real da geometria); (2)
senão, medido na hora direto da geometria da linha (com a mesma correção
elipsoidal da seção 6).

---

## 11) Verificações complementares (NBR 9649) — declividade mínima e tensão trativa

Verificações adicionais, que **não substituem** o critério original de
"trecho crítico" (DN calculado > DN existente) — aparecem como campos
extras (`IMIN_PCT`, `OK_IMIN`, `TRAT_CPA`, `OK_TRATC`, `TRAT_EPA`,
`OK_TRATE`), para você conferir se a rede também atende aos critérios de
autolimpeza da norma.

### Declividade mínima

Do Termo de Referência SAMAE, item 6.4.1: a declividade adotada deve
proporcionar tensão trativa mínima de 1,0 Pa, calculada para a vazão
inicial. A expressão aproximada (considerando n = 0,013):

```
Imin (m/m) = 0,0055 × Qi^(-0,47)
```

onde `Qi` é a vazão do trecho no início do plano, em L/s. **Simplificação
assumida neste plugin**: não modelamos fases temporais (início/fim de
plano) separadamente — usamos a vazão acumulada calculada (já incluindo
infiltração e o piso de vazão mínima) tanto para `Qi` quanto para o
dimensionamento.

### Raio hidráulico

Seção circular parcialmente cheia, a partir do diâmetro `D` e da lâmina
relativa geométrica `h/D` (parâmetro `razao_h_d`, padrão 0,75 — **não
confundir** com o parâmetro `lamina_relativa` usado na fórmula do
diâmetro calculado, que é outro fator, vindo da planilha original):

```
θ = 2 × acos(1 − 2×(h/D))          [ângulo central, rad]
Rh = (D/4) × (1 − sen(θ)/θ)
```

### Tensão trativa

```
σt (Pa) = γ × Rh × I
```

- `γ`: peso específico do líquido, adotado 10.000 N/m³ (parâmetro
  `peso_especifico`).
- `Rh`: raio hidráulico (m), calculado acima.
- `I`: declividade do trecho (m/m).

A NBR 9649 exige `σt ≥ 1,0 Pa`. O plugin calcula a tensão trativa **duas
vezes** por trecho: uma usando o DN calculado (o que seria adotado no
projeto) e outra usando o DN existente (para saber se a tubulação atual
já atende).

Implementado em `calculo.py`, funções `raio_hidraulico_m()` e
`tensao_trativa_pa()`.

### Velocidade final e velocidade crítica

Do Termo de Referência SAMAE, itens 6.4.6 e 6.4.7:

```
vf (m/s) = (1/n_pvc) × Rh^(2/3) × I^0,5
vc (m/s) = 6 × (g × Rh)^(1/2)
```

- `n_pvc`: rugosidade de Manning **do PVC**, adotado 0,010 — **atenção**:
  é um coeficiente **diferente** do `rugosidade` (n = 0,013) usado na
  fórmula do diâmetro/fator hidráulico. São dois valores distintos no
  mesmo memorial de cálculo do SAMAE, mantidos separados no plugin
  (parâmetro `n_pvc`, editável).
- `g`: aceleração da gravidade, 9,81 m/s² (fixo).
- `Rh`: raio hidráulico (mesma fórmula acima).

Quando `vf > vc`, a norma manda reduzir a lâmina máxima de projeto para
50% do diâmetro — o plugin **aplica isso automaticamente** (ver
subseção dedicada logo abaixo), não só sinaliza. Calculado duas vezes
por trecho: uma com o DN adotado, outra com o DN existente.

Implementado em `calculo.py`, funções `velocidade_final_ms()` e
`velocidade_critica_ms()`.

### DN mínimo de projeto

Do item 7.3.3 do Termo de Referência SAMAE: diâmetro mínimo de 150 mm
(a NBR 9649/86 permitiria 100mm, mas o SAMAE adota 150mm). O plugin
calcula dois diâmetros por trecho:

```
dn_calculado = solução bruta da fórmula de Manning (seção 5)
dn_adotado   = max(dn_calculado, dn_minimo)
```

O campo **"crítico"** (e as verificações de tensão trativa/velocidade)
usam o `dn_adotado`, não o `dn_calculado` bruto — faz mais sentido
comparar com o diâmetro que seria de fato especificado num projeto
(nunca menor que o mínimo de norma) do que com um valor hidraulicamente
"correto" mas impraticável. O `dn_calculado` bruto continua disponível
separadamente, para auditoria. Parâmetro editável: `dn_minimo` (padrão
0,15 m = DN150).

### Redução automática de lâmina quando vf > vc

O item 6.4.7 do Termo de Referência SAMAE diz: quando a velocidade final
(vf) for maior que a velocidade crítica (vc), a lâmina máxima de projeto
deve ser reduzida para 50% do diâmetro. O plugin **aplica isso
automaticamente**, não só avisa:

1. Calcula vf e vc com a lâmina normal (`razao_h_d`, padrão 0,75).
2. Se `vf > vc`, recalcula tudo (Rh, tensão trativa, vf, vc) usando a
   lâmina reduzida (`razao_h_d_reduzida`, padrão 0,50).
3. Os valores finais expostos (`TRAT_CPA`, `VF_CALC`, `VC_CALC`,
   `OK_VELC`) já refletem esse ajuste. O campo `LAMRED_C` (`LAMRED_E`
   para o DN existente) marca `1` quando a redução foi necessária/
   aplicada, para você saber que aquele trecho está sendo avaliado com
   lâmina reduzida.

Testado com um caso sintético de declividade bem alta (onde vf excede vc
mesmo com a lâmina normal) e confirmado que o ajuste é aplicado e os
valores recalculados corretamente.

Implementado em `calculo.py`, função `verificar_lamina_velocidade_tensao()`.

### Espaçamento máximo entre poços de visita

Do item 7.3.1 do Termo de Referência SAMAE: distância máxima de 80 m
entre PVs. Como cada "coletor" no plugin já representa o segmento entre
dois pontos de junção (bacia→coletor ou coletor→coletor), essa checagem
é direta: **o comprimento do próprio trecho é o espaçamento a
conferir**.

```
excede_espacamento = comprimento_trecho_m > espacamento_max_pv
```

Parâmetro editável: `espacamento_max_pv` (padrão 80 m). Resultado no
campo `OK_ESPAC` da camada (1 = atende) e aviso "Espac!" na
tabela/rótulo. O comprimento usado é o mesmo já medido para a vazão de
infiltração (seção 10) — reaproveita o campo `COMPR_M`, que agora fica
sempre atualizado a cada "Calcular tudo" (antes só era preenchido se
você usasse "Definir declividade por trecho").

### O que ainda NÃO está implementado (do Termo de Referência SAMAE)

- **Recobrimento mínimo** (0,65 m em passeio, 0,90 m sob via pública) —
  depende de modelar a cota/profundidade do tubo (não só do terreno),
  e de saber se cada trecho está em passeio ou via pública — nenhuma
  dessas informações é capturada pelo plugin hoje. Fica como próximo
  passo, quando/se fizer sentido adicionar esse nível de detalhe.

---

## 12) Onde cada coisa mora no código

| Assunto | Arquivo |
|---|---|
| Fórmulas de população/vazão/diâmetro/cascata | `calculo.py` |
| Banco de dados (.sqlite): vínculos, parâmetros, densidades, cotas, config | `db.py` |
| Área/comprimento com correção elipsoidal | `geo_utils.py` |
| Identificar feição clicada no mapa (com correção de CRS e sobreposição) | `geo_utils.py`, `maptool_link.py` |
| Seção recolhível da interface | `collapsible.py` |
| Campos criados nas camadas (nomes, tipos, descrições) | `constantes.py` |
| Montagem da interface do painel | `painel_ui.py` |
| Escolha de camada/campo | `painel_camadas.py` |
| Abrir/criar banco, restaurar configuração salva | `painel_banco.py` |
| Vínculos, densidade, parâmetros, exceções, declividade por cota, micromedição | `painel_vinculos.py` |
| Execução do cálculo e escrita nas camadas | `painel_calculo.py` |
| Simbologia, resumo, rótulos, layout de apresentação | `painel_mapa.py` |
| Exportação de relatórios (Excel/CSV) | `painel_relatorios.py` |
| Classe principal (junta os mixins acima) | `rede_cascata_dockwidget.py` |
| Integração com o menu/toolbar do QGIS | `rede_cascata.py` |
