# saniDmae - DSES (plugin QGIS)

**Simulação em redes de esgoto**

Plugin para agilizar o fluxo: bacia -> coletor -> coletor (cascata),
calculando populacao, vazao acumulada e diametro calculado (Manning),
comparando com o diametro existente e marcando trechos criticos no mapa.

> **Documentacao complementar:**
> - `GUIA_DE_USO.md` - passo a passo completo de como usar o plugin.
> - `FORMULAS_E_PARAMETROS.md` - todas as formulas, parametros padrao e
>   onde cada calculo esta implementado no codigo.

## Instalacao

1. Localize a pasta de plugins do QGIS:
   - Windows: `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins`
2. Copie a pasta `rede_cascata` inteira para dentro dessa pasta de plugins.
3. Abra o QGIS -> menu `Complementos` -> `Gerenciar e Instalar Complementos`
   -> aba `Instalados` -> marque a caixa de `Rede Cascata - Dimensionamento
   de Esgoto`.
4. Um icone/entrada de menu "Rede Cascata - Esgoto" vai aparecer. Clique
   para abrir o painel lateral (dock).

## Fluxo de uso

1. **Passo 1 (configuracao)**: no painel, escolha a camada de bacias e o
   campo que identifica cada bacia (ex: `NOME`, `SIGLA` ou `id`), depois a
   camada de coletores, o campo de ID do coletor e o campo onde esta o
   diametro existente (em metros). Clique em "Criar/abrir banco de
   calculo" e escolha onde salvar o arquivo `.sqlite` (sugestao: salvar do
   lado do seu `.qgz`/`.qgs`). Esse arquivo guarda todos os vinculos e
   parametros - pode reabrir depois pra continuar de onde parou.

2. **Passo 2 (vinculos)**: clique em "Vincular bacia(s) -> coletor",
   depois va clicando no mapa em uma ou varias bacias (elas ficam
   destacadas em laranja) e por fim clique no coletor de destino - todas
   as bacias marcadas sao vinculadas de uma vez. Botao direito ou ESC
   limpa a selecao pendente. Use "Vincular coletor(es) -> coletor de
   jusante" do mesmo jeito para montar a cascata (ex: coletor 4 -> coletor
   6).

3. **Passo 3 (densidade)**: selecione uma ou mais bacias na tabela de
   atributos/mapa (selecao normal do QGIS), escolha a densidade (hab/ha)
   na lista ou digite um valor manual, e clique em "Aplicar". A area em
   hectare e lida automaticamente da geometria da bacia (equivalente ao
   `$area/10000` que voce ja usava).

4. **Passo 4 (parametros)**: edite os parametros globais (qf, C, k1, k2,
   inclinacao, lamina relativa h/D, rugosidade de Manning) e, se algum
   trecho especifico precisar de valores diferentes, selecione o coletor
   na camada e use "Editar excecao do coletor selecionado".

5. **Passo 5 (calcular)**: clique em "Calcular tudo". O plugin percorre a
   cascata inteira, grava `VAZAO_ACM`, `DN_CALC` e `CRITICO` como novos
   campos na sua camada de coletores, pinta em vermelho os trechos onde o
   diametro calculado ultrapassa o existente, e mostra a tabela resumo no
   painel. Depois use "Exportar relatorio de trechos criticos (CSV)" para
   gerar a lista final de necessidade de troca/melhoria.

## Sobre a formula do diametro calculado

A formula padrao usada e a forma classica de Manning para secao circular:

```
D = ( (4 * Q * n) / (pi * sqrt(S) * f) ) ** (3/8)
```

onde `Q` esta em m3/s (o plugin ja converte a vazao de L/s pra m3/s antes
de aplicar a formula), `n` = rugosidade, `S` = inclinacao (m/m) e `f` =
fator relativo a lamina (h/D).

**Importante**: eu nao tive acesso a formula exata e completa da sua
planilha (a celula estava com a formatacao cortada/ilegivel no print). Por
isso deixei a formula **editavel** dentro do plugin (botao "Editar
parametros globais" -> campo "Formula do diametro"). Pegue um trecho que
voce ja calculou no Excel, calcule o mesmo trecho no plugin, compare os
diametros e, se der diferente, ajuste a expressao no campo de formula ate
bater com a sua planilha de referencia. A expressao aceita as variaveis
`Q`, `n`, `S`, `f` e funcoes do modulo `math` (ex: `math.pi`).

A formula de vazao (populacao e Q em L/s) foi conferida e bate exatamente
com o exemplo da sua planilha (Uberabinha MD, 463,98 ha, 300 hab/ha ->
347,99 L/s).

## Changelog

- v6.2: **memorial de calculo do SAMAE quase completo - reducao
  automatica de lamina e espacamento entre PVs:**
  1. **Reducao automatica de lamina quando vf > vc**: a norma manda
     reduzir a lamina maxima pra 50% do diametro nesse caso - antes o
     plugin so avisava, agora **recalcula sozinho** (Rh, tensao trativa,
     vf, vc) com a lamina reduzida (novo parametro `razao_h_d_reduzida`,
     padrao 0,50) e usa esses valores ajustados como resultado final.
     Novo campo `LAMRED_C`/`LAMRED_E` marca quando a reducao foi
     aplicada.
  2. **Espacamento maximo entre pocos de visita** (80m por padrao, novo
     parametro `espacamento_max_pv`): como cada trecho ja representa o
     segmento entre duas juncoes, a checagem e direta - se o comprimento
     do trecho passar do maximo, sinaliza (`OK_ESPAC`, "Espac!" na
     tabela/rotulo). O comprimento agora fica sempre atualizado no campo
     `COMPR_M` a cada "Calcular tudo" (antes so era preenchido via
     "Definir declividade por trecho").
  Testei tudo isolado (reducao automatica ativando corretamente num caso
  de declividade forte, espacamento sinalizando certo pra trechos longos
  e curtos, fluxo completo calcular->salvar->reabrir preservando os
  campos novos) antes de integrar. So falta o recobrimento minimo da
  lista original do SAMAE, que fica pendente (depende de modelar
  profundidade do tubo e tipo de via, dado que o plugin nao captura
  hoje - ver FORMULAS_E_PARAMETROS.md secao 11 pra detalhes).
- v6.1: **completando o memorial de calculo do SAMAE - velocidade
  final/critica e DN minimo de projeto:**
  1. **Velocidade final e critica** (itens 6.4.6/6.4.7 do Termo de
     Referencia): `vf = (1/n_pvc) x Rh^(2/3) x I^0,5` e
     `vc = 6 x (g x Rh)^0,5`. Novo parametro `n_pvc` (padrao 0,010,
     rugosidade do PVC - diferente do `rugosidade`=0,013 usado no
     diametro). Quando vf excede vc, o plugin sinaliza (`OK_VELC`,
     "Vel!" na tabela/rotulo) - a norma recomenda reduzir a lamina a 50%
     do diametro nesse caso, mas o plugin so avisa, nao recalcula sozinho.
  2. **DN minimo de projeto** (item 7.3.3, padrao 150mm): agora o plugin
     calcula `dn_adotado = max(dn_calculado, dn_minimo)`, e e ESSE valor
     (nao o dn_calculado bruto) que decide se o trecho e critico e que
     entra nas verificacoes de tensao trativa/velocidade - mais realista
     que comparar com um diametro hidraulicamente "correto" mas menor
     que qualquer tubulacao que se especificaria na pratica. O
     dn_calculado bruto continua disponivel separado, pra auditoria.
  Testei tudo isolado (velocidade final/critica batendo com calculo
  manual, DN minimo aplicando o piso corretamente, fluxo completo
  calcular->salvar->reabrir preservando todos os campos novos) antes de
  integrar na interface e nos relatorios. `FORMULAS_E_PARAMETROS.md`
  atualizado - a lista de pendencias do memorial SAMAE agora so tem
  espacamento entre PVs, recobrimento minimo, e a reducao automatica de
  lamina quando vf>vc.
- v6.0: **grande atualizacao de calculo - criterios reais de dimensionamento
  NBR 9649, alem da simulacao/aproximacao que ja existia:**
  1. **Vazao de infiltracao**: `Qinf = Lt x Cinf`, acumulada pela cascata
     igual a vazao domestica (novo parametro `c_inf`, padrao 0,0005 L/s/m,
     conforme Termo de Referencia oficial do SAMAE Caxias do Sul).
  2. **Vazao minima de projeto**: se `Qd + Qinf` ficar abaixo do minimo
     (novo parametro `vazao_minima`, padrao 1,5 L/s), adota-se o minimo.
  3. **Declividade minima NBR 9649**: `Imin = 0,0055 x Qi^-0,47`, com
     verificacao automatica se a declividade adotada atende (`IMIN_PCT`,
     `OK_IMIN`).
  4. **Tensao trativa**: calculada via raio hidraulico da secao circular
     parcialmente cheia (`Rh`, a partir de novo parametro `razao_h_d`,
     padrao 0,75) e peso especifico (`peso_especifico`, padrao
     10.000 N/m3) - verificada tanto pro DN calculado quanto pro DN
     existente (`TRAT_CPA`/`OK_TRATC`, `TRAT_EPA`/`OK_TRATE`).
  5. **Vazao por micromedicao**: agora da pra importar um CSV com pontos
     de consumo medido por imovel (com coordenadas X/Y) e, por bacia,
     escolher manualmente usar a soma desses pontos em vez da estimativa
     por area/densidade (`Q = consumo_medido x C x k1 x k2`). O plugin
     cruza automaticamente cada ponto com a bacia onde ele cai
     (point-in-polygon, com correcao de CRS), cria uma camada de pontos
     pra conferencia visual, e tudo fica salvo no banco `.sqlite`.
  Todas essas verificacoes aparecem na tabela do painel (coluna "NBR
  9649"), no rotulo do mapa, e nos dois relatorios (Excel e CSV de
  reserva). Testei cada formula nova isoladamente (infiltracao acumulando
  na cascata, piso de vazao minima, raio hidraulico, tensao trativa,
  micromedicao substituindo area/densidade so na bacia marcada) antes de
  integrar. Ver `FORMULAS_E_PARAMETROS.md` secoes 10 e 11 para detalhes
  completos, incluindo o que ainda NAO foi implementado (velocidade
  final/critica, DN minimo de 150mm, espacamento entre PVs).
- v5.0: **reorganizacao do codigo e da documentacao - nenhuma
  funcionalidade foi alterada.**
  - O arquivo `rede_cascata_dockwidget.py`, que tinha crescido pra mais
    de 2300 linhas com tudo junto, foi dividido em 7 arquivos por
    assunto (`painel_ui.py`, `painel_camadas.py`, `painel_banco.py`,
    `painel_vinculos.py`, `painel_calculo.py`, `painel_mapa.py`,
    `painel_relatorios.py`), usando o padrao de "mixins" do Python -
    em tempo de execucao continua sendo exatamente a mesma classe/
    comportamento de antes (testei o encadeamento de heranca isolado
    antes de aplicar, e recompilei tudo depois). O arquivo principal
    agora so tem o `__init__` e a composicao dos mixins.
  - Nomes de campo centralizados em `constantes.py` (antes viviam soltos
    no meio do arquivo grande).
  - Criado `GUIA_DE_USO.md` (passo a passo completo pro usuario final) e
    `FORMULAS_E_PARAMETROS.md` (todas as formulas/parametros usados nos
    calculos, com referencia de onde cada coisa esta implementada no
    codigo) - ver os dois na raiz da pasta do plugin.
- v4.9: otimizacoes de performance na geracao do relatorio Excel (estava
  travando muito em redes grandes):
  1. Largura de coluna agora e estimada olhando so uma amostra das
     primeiras 300 linhas, em vez de escanear a planilha inteira -
     testei isoladamente e ficou ~13x mais rapido com 5000 linhas.
  2. Os estilos de celula (cor de cabecalho, fundo vermelho dos trechos
     criticos) agora sao criados uma unica vez e reaproveitados, em vez
     de criar um objeto novo por celula/linha.
  3. O calculo de area das bacias (usado no relatorio de diagnostico e no
     "Calcular tudo") reaproveita um unico conversor de coordenadas
     (`QgsDistanceArea`) para todas as bacias do loop, em vez de recriar
     e reconfigurar um novo a cada bacia - essa parte provavelmente era a
     maior responsavel pela travada em redes com muitas bacias, ja que
     recriar esse objeto tem custo real do lado do QGIS.
  Se mesmo assim ainda estiver lento com sua rede (redes muito grandes,
  milhares de trechos), me avise - o proximo passo seria rodar a
  exportacao em segundo plano com uma barra de progresso, pra pelo menos
  nao travar a tela do QGIS enquanto gera.
- v4.8: **relatorios agora saem em Excel (.xlsx) de verdade**, com abas
  separadas (Resumo, Parametros globais, Excecoes por trecho, Densidades
  por bacia, Cascata, Resultado por coletor), cabecalho colorido, linhas
  criticas destacadas e largura de coluna automatica. Isso tambem corrige
  o motivo da "declividade errada" no CSV: o Excel brasileiro espera
  numero com VIRGULA decimal, mas o CSV estava sendo escrito com PONTO
  (padrao Python) - o Excel podia interpretar "3.406" como o numero 3406
  em vez de 3,406. No xlsx os numeros ficam gravados nativamente (nao
  dependem de separador de texto nenhum, testei e confirmei que abrem
  como float de verdade). Se o pacote `openpyxl` nao estiver instalado no
  Python do QGIS, o plugin cai automaticamente pro CSV de antes, mas
  agora com virgula decimal corrigida tambem.
- v4.7: **causa raiz do rotulo de declividade nao aparecer, finalmente
  encontrada**: `S_USADA_PCT` tem 11 caracteres, e Shapefile (.shp) limita
  nomes de campo a 10 - o QGIS truncava sozinho pra `S_USADA_PC`, e como o
  plugin sempre procurava pelo nome completo (que nunca existia de fato),
  ele achava que o campo estava faltando e criava um novo a cada calculo
  (por isso apareceram `S_USADA_1`, `S_USADA_2`, `S_USADA_3`... todos
  vazios). Corrigido renomeando TODOS os campos do plugin pra no maximo
  10 caracteres (`S_USO_PCT`, `COL_DEST`, `DENS_HAB`, `AREA_CALC`).
  Tambem adicionado um aviso automatico: se o formato da camada truncar
  algum nome de campo no futuro, o plugin avisa na hora em vez de ficar
  recriando campo duplicado silenciosamente.
  **Os campos velhos e vazios (`S_USADA_1` a `S_USADA_4`, `S_USADA_PC`)
  ficaram na sua camada de coletores - sao inofensivos (o plugin nao usa
  mais eles), mas se quiser uma tabela de atributos limpa, pode apagar
  eles manualmente em Propriedades da Camada -> Campos.**
- v4.6: adicionado o slogan "Simulacao em redes de esgoto" - aparece como
  subtitulo no topo do painel (abaixo do titulo "saniDmae - DSES") e na
  descricao do plugin no Gerenciador de Complementos do QGIS.
- v4.5: plugin renomeado para **saniDmae - DSES** (menu, titulo do painel,
  mensagens da barra do QGIS, nome do layout de apresentacao e
  metadata.txt). A pasta de instalacao continua se chamando `rede_cascata`
  internamente (nao precisa desinstalar/reinstalar do zero, so substituir
  os arquivos por cima funciona normalmente).
- v4.4: a declividade EFETIVAMENTE usada no calculo de cada trecho
  (seja o parametro global, uma excecao manual, ou a calculada a partir
  das cotas de inicio/fim) agora aparece em quatro lugares pra conferencia
  facil: na tabela do painel (nova coluna "Declividade (%)"), no rotulo
  do mapa (linha "Declividade: X%"), no atributo `S_USADA_PCT` gravado na
  camada de coletores, e nos dois relatorios CSV (trechos criticos e
  diagnostico geral). Bancos `.sqlite` criados em versoes anteriores do
  plugin sao migrados automaticamente (ganham a coluna nova sem perder
  nada do que ja tinha calculado).
- v4.3: seta ajustada - removido o deslocamento ao longo da linha (que
  estava jogando ela pra longe do ponto certo), girada 90 graus a mais
  pra ficar perpendicular ao coletor (em vez de alinhada/paralela a ele),
  e tamanho aumentado (~2.3x maior que antes).
- v4.2: a forma "filled_arrowhead" usada na seta parece nao estar
  renderizando direito nessa versao do QGIS (virava um formato estranho,
  tipo um laco/oval, em vez de uma seta). Trocada por "triangle" - uma
  forma padrao muito mais estavel e suportada em praticamente todas as
  versoes do QGIS 3.x. Tambem reduzi um pouco o tamanho pra nao se
  misturar com os marcadores circulares de inicio/fim de trecho.
- v4.1: melhorada a deteccao de trecho invertido (`DIRECAO_OK`). A versao
  anterior comparava so com o INICIO do trecho de jusante - se aquele
  trecho de jusante tambem estivesse digitalizado ao contrario, a
  referencia ficava errada e a seta saia torta mesmo depois da correcao.
  Agora o plugin compara as duas pontas dos dois trechos entre si (4
  combinacoes) pra achar o ponto de encontro real, independente de qual
  extremidade e o "inicio" ou "fim" de cada linha. Testado em 4 cenarios
  (ambos corretos, so um invertido de cada lado, os dois invertidos) e
  bateu certo em todos. Precisa rodar "Calcular tudo" de novo pra
  recalcular o campo `DIRECAO_OK` com a formula nova.
- v4.0: adicionada a linha "🚰 Desenho por: Diretoria do Sistema de
  Esgotamento Sanitario" no rodape do "Gerar mapa de apresentacao (layout
  pronto)", acima da linha de data/hora de geracao.
- v3.9: seta agora segue o SENTIDO DO VINCULO (coletor -> coletor de
  jusante que voce configurou), nao a direcao fisica de digitalizacao da
  linha. O plugin calcula automaticamente, durante "Calcular tudo", se
  cada trecho foi desenhado no sentido do fluxo (comparando o fim do
  trecho com o inicio do trecho de jusante) e gira a seta 180 graus nos
  trechos que estavam ao contrario - sem precisar editar a geometria da
  camada original. Isso fica gravado no campo `DIRECAO_OK` (1 = ok, 0 =
  estava invertido, corrigido automaticamente na seta).
- v3.8: seta de sentido movida do meio do trecho para a extremidade FINAL
  (ponto de jusante) de cada coletor, com um pequeno recuo pra nao ficar
  100% em cima do marcador circular do "fim" do trecho.
- v3.7:
  1. **Seta de sentido do coletor**: a simbologia da rede agora tem uma
     seta no meio de cada trecho, rotacionada automaticamente conforme a
     direcao da linha. Importante: a seta segue a direcao de
     DIGITALIZACAO da linha (do primeiro pro ultimo vertice) - se ela
     apontar ao contrario do escoamento real em algum trecho, use a
     ferramenta nativa do QGIS "Inverter direcao da linha" (Editar ->
     Ferramentas de geometria, ou clique direito na feicao selecionada)
     naquele trecho especifico.
  2. **Sem legenda no mapa de apresentacao**: o botao "Gerar mapa de
     apresentacao" nao adiciona mais o item de legenda no layout - fica
     so mapa, titulo, escala e rodape.
- v3.6: tamanho do texto do rotulo (bacias e coletores) trocado de pontos
  fixos pra **unidades do mapa**, tamanho 10 - assim o texto escala junto
  com o zoom/escala real do mapa (ex: 10 metros, se a camada estiver num
  CRS metrico), em vez de ficar sempre do mesmo tamanho na tela
  independente do quanto voce deu zoom.
- v3.5: rotulo do coletor agora fica fixo no centroide (centro) da
  geometria da linha, em vez do QGIS escolher a posicao automaticamente
  ao longo do trecho (o que mudava dependendo do zoom). Tambem fixei o
  tamanho do texto do rotulo em 5, independente do modo apresentacao (que
  continua controlando a espessura da linha e o tamanho dos marcadores de
  inicio/fim de trecho).
- v3.4: tres pedidos de apresentacao/plotagem:
  1. **Marcadores de inicio/fim de trecho**: a simbologia da rede agora
     desenha um circulo (branco com contorno colorido) no inicio e no fim
     de cada coletor, alem da linha - fica visualmente claro onde um
     trecho termina e o proximo comeca (tipo um poço de visita esquematico
     nos limites). Se a versao do QGIS nao suportar esse recurso por
     algum motivo, o plugin cai de volta pra linha simples automaticamente
     em vez de falhar.
  2. **Modo apresentacao**: novo checkbox na secao 6 - deixa a linha, os
     marcadores e o texto dos rotulos menores/mais discretos. Reaplica na
     hora (sem precisar recalcular tudo de novo), tanto na simbologia
     quanto nos rotulos se ja estiverem ativos.
  3. **Gerar mapa de apresentacao (layout pronto)**: novo botao que cria
     um Layout de Impressao do QGIS (mapa + titulo + legenda + escala +
     rodape com data) e ja abre o Compositor de Impressao pra voce
     ajustar e exportar como PDF/imagem. Se houver bacias ou coletores
     selecionados no mapa, o layout usa a area deles (com uma margem);
     senao, usa a vista atual do mapa.
- v3.3: corrigido o motivo real do rotulo nao aparecer (nem dos coletores,
  nem depois dos poligonos): o codigo da v3.2 acessava
  `QgsPalLayerSettings.Horizontal`/`OverPoint`/`Color` direto na classe,
  mas em algumas versoes do QGIS esses valores foram movidos pra dentro
  de um enum aninhado (`QgsPalLayerSettings.Placement.Horizontal`, por
  exemplo). Quando o nome nao existe no lugar esperado, o Python levanta
  um erro que ficava silencioso (sem aviso na tela), interrompendo a
  ativacao dos rotulos - inclusive dos poligonos, que ja vinham
  funcionando antes, porque o erro podia acontecer no meio do processo.
  Agora o plugin tenta os dois formatos de API automaticamente, e se
  mesmo assim algo der errado, mostra uma mensagem de erro CLARA na tela
  (em vez de falhar calado) pra dar pra diagnosticar na hora.
- v3.2: corrigido rotulo dos coletores nao aparecendo no mapa (so os das
  bacias apareciam). Camadas de LINHA precisam de um modo de
  posicionamento de rotulo (`placement`) definido explicitamente - sem
  isso o QGIS simplesmente nao desenha nada, mesmo com os dados corretos
  na tabela de atributos (o que explicava a tabela mostrar tudo certo mas
  o mapa nao mostrar o rotulo). Agora o plugin define isso automaticamente
  de acordo com o tipo de geometria de cada camada (linha, poligono ou
  ponto).
- v3.1: o rotulo dos coletores (camada de simulacao da rede) agora mostra
  o resumo completo da simulacao: ID, coletor de jusante, vazao acumulada,
  DN calculado, DN existente e status (ATENDE/CRITICO) - e o texto fica
  vermelho automaticamente nos trechos criticos, no mesmo esquema de cor
  da simbologia da linha. Tambem foram adicionados os campos `DN_EXIST_M`
  (DN existente normalizado pra metros) e `STATUS` na camada de coletores,
  gravados junto com o resto dos resultados em "Calcular tudo".
- v3.0:
  1. **"Recarregar camadas do projeto" corrigido**: se um banco ja
     estivesse aberto com configuracao valida, clicar em recarregar podia
     trocar a camada certa pela "adivinhada" por palavra-chave sem avisar
     (ex: "INTERCEPTORES-BACIAS E SUBBACIAS" tambem contem "bacia" e podia
     vencer "SUBBACIAS_ESGOTO"). Agora a configuracao salva tem prioridade
     e so cai no chute automatico se a camada salva realmente nao for
     encontrada.
  2. **Janela de cota nao-modal**: a janela de "Cota de inicio/saida" (no
     "Definir declividade por trecho") agora nao trava mais o mapa - da
     pra continuar arrastando/dando zoom por baixo dela pra conferir a
     cota do outro lado do trecho antes de digitar. Ela tambem abre num
     canto da tela, nao em cima do mapa.
  3. **Desvincular bacia(s) / coletor(es)**: dois botoes novos na secao 2 -
     selecione bacias ou coletores na camada e desvincule o vinculo deles
     (com o coletor ou com o coletor de jusante) pra reprocessar o calculo
     de outro jeito, sem precisar apagar o banco inteiro.
  4. **Linha da rede mais grossa**: a simbologia aplicada apos "Calcular
     tudo" (cinza = atende, vermelho = critico) agora usa uma espessura
     maior, mais facil de enxergar no mapa.
  5. **Nova secao "6) Resumo e rotulos no mapa"**: um resumo textual
     (quantas bacias vinculadas, com densidade, quantos coletores em
     cascata, excecoes, parametros globais atuais) atualizado
     automaticamente apos abrir o banco ou calcular. Tambem tem botoes
     pra ativar/desativar rotulos diretamente no mapa mostrando, em cada
     bacia e coletor, o vinculo, a densidade e os principais resultados.
- v2.9: dois ajustes na "restauracao automatica" ao abrir um banco
  existente:
  1. Agora o plugin **avisa explicitamente** o que conseguiu e o que NAO
     conseguiu restaurar (camada de bacias, campo ID, camada de coletores,
     campo ID, campo DN, unidade), em vez de falhar silenciosamente e
     deixar a auto-deteccao por palavra-chave assumir no lugar (o que
     podia fazer parecer que "as camadas mudaram sozinhas"). A
     correspondencia de nome tambem ficou mais tolerante (ignora
     maiusculas/minusculas e espacos nas pontas).
  2. A secao "3) Densidade" agora mostra automaticamente a densidade JA
     SALVA da bacia quando voce clica nela no mapa/tabela (se so uma
     estiver selecionada) - antes o campo sempre aparecia zerado ao reabrir
     o plugin, dando a impressao de que a densidade tinha se perdido,
     quando na verdade ela sempre esteve salva no banco e era usada
     normalmente no calculo; so a tela nao refletia isso.
- v2.8: o botao "Definir declividade por trecho" agora calcula a
  declividade sozinho. Em vez de digitar a % direto, voce informa a
  **cota de inicio** (montante) e a **cota de saida** (jusante) de cada
  trecho selecionado - o plugin mede o comprimento direto da geometria da
  rede (com a mesma correcao de CRS/elipsoide usada na area das bacias) e
  calcula: `declividade = (cota_inicio - cota_final) / comprimento`. O
  resultado em % aparece na hora, antes de confirmar. As cotas ficam
  salvas no banco (pra reabrir e ajustar depois sem perder o que ja foi
  digitado) e tambem sao gravadas como atributos na camada de coletores
  (`COTA_INIC`, `COTA_FIN`, `COMPR_M`, `DECLIV_PCT`), junto com o resto
  dos dados de diagnostico. A opcao de digitar a inclinacao direto em %
  continua disponivel em "Editar excecao do coletor", caso voce nao tenha
  as cotas de um trecho especifico.
- v2.7: corrigido o scroll que nao chegava ate o final mesmo com todas as
  secoes abertas (so "resolvia sozinho" ao recolher e expandir algo). A
  causa era a tabela de resultados, que tinha politica de crescimento
  vertical "Expanding" dentro da area de rolagem - isso confundia o
  calculo da altura total do conteudo. Agora a tabela tem altura fixa
  (entre 160 e 220px, com rolagem propria dela se tiver muitas linhas), e
  cada vez que uma secao e recolhida/expandida o plugin forca um
  recalculo de geometria, entao a barra de rolagem deve refletir a altura
  real do conteudo desde o primeiro carregamento, sem precisar de
  nenhuma interacao extra.
- v2.6: corrigido bug em que os botoes de acao (Vincular, Editar excecao,
  Definir declividade por trecho, Aplicar densidade, Calcular tudo etc)
  podiam usar uma referencia DESATUALIZADA da camada/campo de bacias ou
  coletores, se voce trocasse a selecao no combo depois de ja ter aberto
  o banco de calculo. Isso fazia o plugin checar a selecao feita no mapa
  contra a camada errada (por isso a caixa de "selecione um coletor"
  aparecia mesmo com uma feicao selecionada). Agora essas referencias
  sao sempre lidas direto dos combos no momento da acao, nunca guardadas
  desatualizadas.
- v2.5: corrigido bug visual serio introduzido na v2.2 - os combos de
  campo (Campo ID da bacia, Campo ID do coletor, Campo DN existente,
  Unidade do DN) estavam ficando **invisiveis** (so o rotulo aparecia,
  sem a caixa de selecao), porque a politica de tamanho usada pra evitar
  que ficassem largos demais (`Ignored`) fazia o Qt colapsar o widget pra
  largura zero em vez de so limitar o crescimento. Isso tambem bagunçava
  o calculo de altura total do painel, fazendo a barra de rolagem nao
  chegar ate o final do conteudo. Trocado para uma politica que limita
  a largura maxima (260px) sem esconder o widget.
- v2.4: agora ha dois botoes separados na secao 1: **"Criar novo banco de
  calculo"** e **"Abrir banco de calculo existente"**. Ao abrir um banco
  ja existente, o plugin lembra sozinho quais camadas e campos voce tinha
  configurado da ultima vez (nome da camada de bacias/coletores, campo de
  ID, campo de DN existente, unidade m/mm) e tenta selecionar tudo de
  novo automaticamente - so funciona se as camadas com aqueles nomes
  ainda estiverem carregadas no projeto atual. Assim, pra continuar de
  onde parou (mudar uma densidade, um vinculo, um parametro, e recalcular)
  nao e preciso reconfigurar o passo 1 nem refazer a vinculacao - so abrir
  o mesmo arquivo `.sqlite` de novo.
- v2.3:
  1. **Inclinacao mostrada em %** nas telas "Editar parametros globais" e
     "Editar excecao do coletor" (mais facil de digitar/ler, ex: 0,4%
     em vez de 0,004). O calculo internamente continua usando m/m - a
     conversao e automatica.
  2. **Novo botao "Definir declividade por trecho"** (secao 4): selecione
     varios coletores na camada (Ctrl+clique ou retangulo de selecao) e
     clique nele - o plugin abre uma caixinha pedindo a declividade media
     (%) de cada trecho, um de cada vez, ja mostrando o valor atual como
     sugestao. Cada valor e salvo como excecao daquele coletor
     especifico (equivalente a usar "Editar excecao do coletor" varias
     vezes, so que mais rapido para varios trechos seguidos).
  3. O relatorio de diagnostico geral (CSV) agora mostra a inclinacao
     tambem em % (alem do m/m), tanto nos parametros globais quanto nas
     excecoes por trecho.
- v2.2: painel reorganizado para caber em docks estreitos (o problema da
  v2.1: o conteudo ficava cortado na largura, sem rolagem horizontal).
  Mudancas: combo + botao de "usar camada" agora ficam empilhados (um
  embaixo do outro) em vez de lado a lado; textos de botao longos foram
  encurtados (o detalhe completo continua no tooltip, passe o mouse por
  cima); os combos de camada/campo tem largura limitada e mostram "..."
  quando o nome e muito comprido (o nome completo aparece no tooltip); e
  os formularios agora quebram a linha (label em cima, campo embaixo)
  quando o espaco horizontal e curto.
- v2.1: o painel inteiro agora fica dentro de uma area com barra de
  rolagem (QScrollArea). Antes, se a janela do QGIS ou o dock ficasse
  pequeno, partes do painel sumiam sem jeito de rolar ate elas - agora
  aparece a barra de rolagem vertical normalmente.
- v2.0:
  1. **Formula do diametro corrigida**: faltava um coeficiente (0,3969)
     que aparece na formula real da sua planilha
     (`=((4*(Q/1000))*n)/(PI()*f*(S^(1/2))*0,3969))^(3/8)`). A formula
     padrao do plugin foi atualizada para bater com a planilha. Se voce ja
     tinha um banco `.sqlite` criado com a formula antiga (e nunca
     personalizou o campo manualmente), o plugin corrige sozinho ao reabrir
     esse banco. Se voce customizou a formula, o valor customizado e
     mantido - confira em "Editar parametros globais".
  2. **Atributos gravados direto nas camadas**: ao clicar em "Calcular
     tudo", alem de atualizar `VAZAO_ACM`, `DN_CALC` e `CRITICO` na camada
     de coletores, agora tambem grava `COL_JUSANT` (coletor de jusante) la,
     e cria/preenche na camada de BACIAS os campos `COL_DESTINO` (coletor
     vinculado), `DENS_HAB_HA`, `AREA_HA_CALC`, `POP_EST` e `VAZAO_PROP`.
     Assim, os dados usados no calculo ficam visiveis e conferiveis
     direto na tabela de atributos do QGIS, mesmo sem abrir o plugin.
     O botao de exportar relatorio completo (CSV) foi renomeado para deixar
     isso mais claro.

     Importante: esses campos nas camadas sao so para CONSULTA/registro -
     quem manda no recalculo continua sendo o banco `.sqlite` (vinculos,
     densidades e parametros). Editar o valor direto na tabela de
     atributos NAO afeta o proximo calculo; para mudar algo, use os
     controles do proprio painel (secoes 2, 3 e 4) e clique em "Calcular
     tudo" de novo.
- v1.9: corrigidos dois bugs de calculo detectados com dados reais:
  1. **Area em graus vs metros**: quando a camada de bacias esta num CRS
     geografico (graus), calcular a area direto da geometria dava um
     numero absurdamente pequeno (tipo 1e-9), gerando vazoes e diametros
     igualmente errados perto de zero. Agora o plugin usa `QgsDistanceArea`
     com o elipsoide do projeto, replicando exatamente o que o `$area` da
     Calculadora de Campo do QGIS faz.
  2. **Unidade do DN existente (m vs mm)**: se o campo de diametro
     existente estiver em milimetros (ex: 150, 200, 300 - padrao DN),
     comparar direto com o diametro calculado em metros (ex: 0.3) nunca
     acusava trecho critico corretamente. Agora ha um combo "Unidade do DN
     existente" (metros ou milimetros), com sugestao automatica baseada
     nos proprios valores da camada (valores tipicos de rede de esgoto:
     0.1-2 m ou 100-2000 mm - a escala e bem diferente). Confira se a
     sugestao automatica bateu antes de calcular.
- v1.8: corrigido caso de bacias sobrepostas (ex: uma bacia grande "por
  baixo" e sub-bacias menores "por cima", como no seu projeto com Liso
  P21-P26 dentro de uma area maior). Antes, ao clicar num ponto onde havia
  mais de uma feicao naquele lugar, o plugin podia pegar a bacia grande
  (oculta visualmente) em vez da pequena que estava destacada/visivel.
  Agora, quando ha mais de uma feicao no mesmo ponto, o plugin escolhe a
  de MENOR area - que normalmente e a mais especifica e a que esta visivel
  por cima no mapa.
- v1.7: trocado o botao "Clicar no mapa" (que dependia do clique acertar a
  feicao no canvas e podia falhar por CRS/zoom/visibilidade) pelo botao
  "Usar camada selecionada na arvore". Agora e so clicar na camada
  desejada no painel "Camadas" do QGIS (a arvore a esquerda, onde ficam
  os nomes das camadas) e depois clicar nesse botao no plugin - muito mais
  direto e nao depende de clicar certo no mapa.
- v1.6: as secoes do painel agora sao recolhiveis - clique na caixinha do
  titulo de cada secao (ex: "1) Configuracao...") pra esconder/mostrar o
  conteudo dela. Tambem foram adicionados os botoes "Recolher todas as
  secoes" e "Expandir todas as secoes" no topo do painel, uteis quando o
  dock esta pequeno na tela e voce quer ver todas as secoes de uma vez ou
  focar so na que esta usando no momento.
- v1.5: corrigido bug em que o "Clicar no mapa" (e o "Vincular bacia(s) ->
  coletor" / "Vincular coletor(es) -> coletor de jusante") nao encontrava
  a feicao clicada quando a camada estava num CRS diferente do CRS do
  projeto/canvas (situacao comum: projeto em SIRGAS2000 geografico e a
  camada de rede em UTM). Agora o clique e transformado corretamente para
  o CRS de cada camada antes de procurar a feicao mais proxima.
- v1.4: novo botao "Gerar relatorio de diagnostico geral (CSV)". Ele exporta
  um relatorio completo (nao so os trechos criticos): parametros globais
  adotados, excecoes aplicadas por trecho, a densidade e a vazao propria
  usada em cada bacia, a cascata coletor->coletor montada, e o resultado de
  TODOS os coletores calculados (vazao acumulada, DN calculado, DN
  existente, diferenca e status ATENDE/PRECISA TROCAR). O botao antigo de
  exportar so os trechos criticos continua disponivel, agora com o rotulo
  "Exportar so os trechos criticos (CSV)".
- v1.3: adicionado o botao "Clicar no mapa" ao lado dos combos de camada de
  bacias e de coletores. Clique nele e depois clique em qualquer feicao no
  mapa - o plugin identifica exatamente qual camada e aquela (respeitando a
  ordem de desenho, ou seja, a camada visivel no topo da legenda tem
  prioridade) e ja seleciona ela no combo. Muito util quando o projeto tem
  varias camadas com nomes parecidos e a deteccao automatica por nome pode
  errar. ESC cancela a escolha.
- v1.2: ao abrir o painel (ou clicar em "Recarregar camadas do projeto"),
  o plugin agora tenta adivinhar sozinho qual camada e a de bacias e qual
  e a de coletores (pelo nome, ex: "SUBBACIAS_ESGOTO", "..._COLETORAS_...")
  e qual campo e o ID e o DN existente (ex: "NOME", "SIGLA",
  "DN_EXISTENTE"). Se o palpite vier errado, so trocar no combo mesmo -
  a deteccao automatica e so um ponto de partida, nao trava nada.
- v1.1: corrigido erro `QgsPointXY has no attribute 'buffer'` ao clicar para
  vincular (o ponto do clique precisa virar `QgsGeometry` antes do buffer).
  Agora, ao marcar uma origem pendente, ela tambem e selecionada de verdade
  na camada (destaque nativo do QGIS, alem do contorno laranja), e o painel
  mostra um aviso fixo (nao some sozinho) com o modo ativo e a quantidade de
  selecoes pendentes.

## Limitacoes desta primeira versao

- Cada bacia so pode apontar para um coletor, e cada coletor so pode
  apontar para um coletor de jusante (sem bifurcacao de saida) - o que
  bate com o seu fluxo descrito. Um coletor pode, entretanto, **receber**
  varias bacias e varios coletores de montante.
- O plugin detecta e avisa se voce acidentalmente criar um ciclo na
  cascata (coletor A -> B -> A).
- Nao ha ainda desfazer (undo) de vinculos pela interface - para remover
  um vinculo, use os metodos `remove_bacia_coletor` /
  `remove_coletor_destino` da classe `RedeDB` (posso adicionar botoes de
  remocao na interface se voce quiser, e mais facil agora que a base
  esta pronta).
- Testado apenas a logica de calculo isoladamente (fora do QGIS, ja que
  nao tenho um ambiente QGIS aqui para rodar a interface). A logica de
  vazao/cascata/deteccao de ciclo foi validada com testes automatizados e
  bate com seus numeros de referencia. Recomendo testar a interface num
  projeto de teste pequeno antes de usar no projeto real.
