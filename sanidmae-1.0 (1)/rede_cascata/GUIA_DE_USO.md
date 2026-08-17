# Guia de Uso - saniDmae - DSES

**Simulação em redes de esgoto**

Este guia mostra o passo a passo completo, do zero até exportar o
relatório final. Para instalação, veja o `README.md`. Para entender as
fórmulas e parâmetros usados nos cálculos, veja `FORMULAS_E_PARAMETROS.md`.

---

## Visão geral do painel

O painel tem 6 seções, que podem ser recolhidas/expandidas individualmente
(clique na caixinha do título) ou todas de uma vez (botões "Recolher
tudo" / "Expandir tudo" no topo):

| # | Seção | Para que serve |
|---|-------|-----------------|
| 1 | Configuração do projeto de cálculo | Escolher as camadas de bacias/coletores e criar ou abrir o banco de cálculo |
| 2 | Vínculos | Ligar bacia → coletor e coletor → coletor de jusante (a cascata) |
| 3 | Densidade | Definir a densidade populacional (hab/ha) de cada bacia |
| 4 | Parâmetros de cálculo | Ajustar qf, C, k1, k2, inclinação, h/D, rugosidade, exceções por trecho, declividade por cota |
| 5 | Calcular e exportar | Rodar o cálculo em cascata e exportar os relatórios |
| 6 | Resumo e rótulos no mapa | Ver o resumo do projeto, ativar rótulos no mapa, gerar mapa de apresentação |

---

## Passo a passo completo

### Passo 1 — Configurar o projeto de cálculo

1. Abra o painel: menu **Complementos → saniDmae - DSES**.
2. Na seção 1, escolha a **camada de bacias** e a **camada de coletores**.
   - O plugin tenta adivinhar sozinho pelo nome da camada (ex: algo com
     "bacia" ou "coletor" no nome). Se não acertar, use o botão **"Usar
     camada da árvore"**: clique na camada certa no painel "Camadas" do
     QGIS e depois clique nesse botão.
3. Confira o **campo ID** de cada camada (o campo que identifica cada
   feição de forma única, ex: `NOME`, `SIGLA`, `id`).
4. Confira o **campo DN existente** e a **unidade** (metros ou
   milímetros) — o plugin tenta adivinhar pela ordem de grandeza dos
   valores, mas vale conferir (diâmetro de rede de esgoto real fica entre
   0,1–2 m ou 100–2000 mm; se os valores da sua camada não baterem com
   isso, o palpite pode estar errado).
5. Clique em **"Criar novo banco de cálculo (.sqlite)"** na primeira vez,
   ou **"Abrir banco de cálculo existente (.sqlite)"** para continuar um
   projeto salvo antes (o plugin tenta restaurar sozinho as camadas e
   campos usados da última vez).

> O banco `.sqlite` guarda todos os vínculos, densidades e parâmetros.
> Ele é independente do projeto `.qgz` do QGIS — pode reabrir em outra
> sessão a qualquer momento.

### Passo 2 — Vincular bacias e coletores (a cascata)

1. Clique em **"Vincular bacia(s) → coletor"**.
2. No mapa, clique em uma ou várias bacias (ficam destacadas em laranja
   e selecionadas na camada) e depois clique no coletor que recebe a
   vazão delas. Todas as bacias marcadas são vinculadas de uma vez.
3. Clique em **"Vincular coletor(es) → jusante"** e repita o processo
   para montar a cascata entre coletores (ex: coletor 7 → coletor 8).
4. Botão direito do mouse ou tecla **ESC** limpa a seleção pendente a
   qualquer momento.
5. Errou um vínculo? Selecione a(s) feição(ões) na camada e use
   **"Desvincular bacia(s) selecionada(s)"** ou **"Desvincular
   coletor(es) do jusante"**.

### Passo 3 — Definir a densidade de cada bacia

1. Selecione uma ou mais bacias na camada (clique, Ctrl+clique, ou
   retângulo de seleção do QGIS).
2. Escolha uma densidade na lista (baseada na tabela de densidades
   urbanas da RMSP) ou digite um valor manual em hab/ha.
3. Clique em **"Aplicar a bacia(s) selecionada(s)"**.
4. Ao clicar de novo numa bacia que já tem densidade salva, o campo
   mostra automaticamente o valor já definido (não fica mais "zerado" só
   porque você reabriu o plugin).

### Passo 4 — Ajustar os parâmetros de cálculo

1. **"Editar parâmetros globais"**: ajusta os valores padrão usados em
   toda a rede (qf, C, k1, k2, inclinação em %, h/D, rugosidade, e a
   fórmula do diâmetro calculado, se precisar).
2. **"Editar exceção do coletor"**: sobrescreve inclinação/h/D/rugosidade
   só no coletor selecionado na camada (ex: um trecho com declividade
   fora do padrão).
3. **"Definir declividade por trecho"**: forma mais precisa de definir a
   inclinação — selecione um ou mais coletores e, para cada um, informe a
   **cota de início** e a **cota de saída**; o plugin mede o comprimento
   real da linha e calcula a declividade média sozinho (mostra o
   resultado em % antes de confirmar).

### Passo 5 — Calcular

1. Clique em **"Calcular tudo (cascata completa)"**.
2. O plugin percorre toda a cascata (bacia → coletor → coletor de
   jusante), soma as vazões, calcula o diâmetro de cada trecho, compara
   com o diâmetro existente, e:
   - Grava os resultados como atributos nas camadas de bacias e
     coletores (visíveis na tabela de atributos do QGIS).
   - Pinta a rede: cinza = atende, vermelho = trecho crítico (precisa
     trocar/melhorar), com marcadores de início/fim de cada trecho e uma
     seta indicando o sentido do fluxo (baseada no vínculo coletor →
     jusante, não na direção física da linha).
   - Preenche a tabela de resultados no próprio painel.

> Pode alterar qualquer coisa (um vínculo, uma densidade, um parâmetro) e
> clicar em "Calcular tudo" de novo — não precisa refazer a vinculação
> nem reconfigurar o passo 1.

### Passo 6 — Conferir e exportar

- **"Exportar só os trechos críticos"**: gera um Excel (.xlsx) só com os
  trechos que precisam de troca/melhoria.
- **"Exportar relatório completo"**: gera um Excel com várias abas —
  Resumo, Parâmetros globais, Exceções por trecho, Densidades por bacia,
  Cascata, e o Resultado de todos os coletores.
  - Se o pacote `openpyxl` não estiver instalado no Python do QGIS, o
    plugin gera em CSV automaticamente (com vírgula decimal, padrão
    Brasil, pra abrir certo no Excel).

### Passo 7 (opcional) — Resumo, rótulos e mapa de apresentação

1. **"Atualizar resumo"**: mostra um resumo de texto (quantas bacias
   vinculadas, com densidade, quantos coletores em cascata, parâmetros
   atuais) — atualiza sozinho depois de calcular.
2. **"Ativar rótulos no mapa"**: mostra, direto no mapa, o vínculo, a
   densidade e os principais resultados de cada bacia e coletor
   (vazão, declividade usada, DN calculado x existente, status). O texto
   fica vermelho automaticamente nos trechos críticos.
3. **Modo apresentação**: deixa a linha, os marcadores e os rótulos mais
   discretos/menores — útil antes de gerar o mapa final.
4. **"Gerar mapa de apresentação"**: cria um Layout de Impressão do QGIS
   (mapa + título + escala + rodapé) já pronto, e abre o Compositor de
   Impressão para você ajustar e exportar como PDF/imagem. Se houver
   bacias/coletores **selecionados** no mapa, o layout usa a área deles;
   senão, usa a vista atual.

### Passo 4b (opcional) — Vazão por micromedição

Se você tem os pontos de consumo medido de cada imóvel (com coordenadas),
pode usar a soma real em vez da estimativa por área/densidade, bacia por
bacia:

1. Clique em **"Importar CSV de micromedição"** — escolha o arquivo, e
   indique qual coluna é o ID do imóvel, X, Y e consumo (L/s). O plugin
   tenta adivinhar sozinho pelo nome das colunas.
2. Ele cruza automaticamente cada ponto com a bacia onde ele cai, e cria
   uma camada de pontos no mapa pra você conferir visualmente.
3. Selecione a(s) bacia(s) que devem usar essa vazão medida e clique em
   **"Usar micromedição na(s) bacia(s) selecionada(s)"**. Pra voltar a
   usar área/densidade, use o botão **"Voltar para área/densidade"**.
4. Rode "Calcular tudo" — as bacias marcadas usam `Q = consumo_medido x C
   x k1 x k2`; as demais continuam usando a estimativa por densidade
   normalmente.

### Sobre as verificações NBR 9649

Além do critério original (DN calculado x DN existente), o cálculo agora
também confere, por trecho:

- **Declividade mínima** (autolimpeza) — coluna "Imin!" na tabela do
  painel e campo `OK_IMIN` na camada, se a declividade adotada estiver
  abaixo da mínima recomendada.
- **Tensão trativa** — coluna "Trat!" e campo `OK_TRATC`, se a tensão
  trativa (calculada com o DN adotado) ficar abaixo de 1,0 Pa.
- **Velocidade final x crítica** — coluna "Vel!" e campo `OK_VELC`. Se a
  velocidade final ultrapassar a crítica, o plugin **já ajusta sozinho**
  (reduz a lâmina para 50% e recalcula) — "Vel!" só aparece se, mesmo
  depois desse ajuste, ainda não resolver. O aviso "(lam.50%)" mostra
  quando esse ajuste automático foi aplicado.
- **Espaçamento entre poços de visita** — coluna "Espac!" e campo
  `OK_ESPAC`, se o trecho for mais longo que o espaçamento máximo (80m
  por padrão).
- **DN mínimo de projeto** (150mm por padrão) — o "DN adotado" (campo
  `DN_ADOT`) nunca fica menor que esse mínimo, mesmo que o cálculo
  hidráulico bruto sugira um diâmetro menor. É o DN adotado, não o
  calculado bruto, que decide se um trecho é crítico.
- **Vazão de infiltração e vazão mínima de projeto** já entram
  automaticamente na vazão total de cada trecho (não precisa fazer nada
  a mais, mas dá pra ajustar os coeficientes em "Editar parâmetros
  globais" se o seu projeto usar valores diferentes dos padrão do SAMAE).

Ver `FORMULAS_E_PARAMETROS.md` para o detalhamento completo de cada
fórmula.

---

## Perguntas frequentes / problemas comuns

**Uma bacia grande "engoliu" o clique de uma bacia menor por cima dela.**
O plugin já trata isso: quando o clique cai em mais de uma feição
sobreposta, ele escolhe a de menor área (a mais específica/visível).

**Cliquei "Recarregar camadas do projeto" e a camada certa trocou
sozinha.** Isso foi corrigido — se já existe um banco aberto com
configuração válida, ela tem prioridade sobre a detecção automática por
nome.

**Reabri o banco e um campo/camada não veio como esperado.** O plugin
avisa explicitamente o que conseguiu e o que não conseguiu restaurar.
Confira se a camada/campo com aquele nome ainda está carregada no
projeto atual.

**O rótulo de algum campo não aparece, mesmo com o dado certo na
tabela de atributos.** Confira se o nome do campo não passou de 10
caracteres — Shapefile (.shp) trunca nomes maiores que isso, e o plugin
detecta e avisa quando isso acontece.

**A janela de "Definir declividade por trecho" não deixa eu mexer no
mapa.** Ela é não-modal de propósito — dá pra arrastar/dar zoom no mapa
com ela aberta, pra conferir a cota do outro lado do trecho.

**Depois de atualizar os arquivos do plugin, algo continua com
comportamento antigo.** Feche e reabra o QGIS por completo (não só
desmarcar/marcar o plugin) — o Python às vezes mantém o código antigo em
memória até reiniciar de verdade.
