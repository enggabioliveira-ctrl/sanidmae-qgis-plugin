# -*- coding: utf-8 -*-
"""
Motor de calculo do plugin.

Formulas usadas (mesmas do fluxo em Excel que o usuario ja usava):

    Hab = area_ha * densidade_hab_ha
    Q (L/s) = Hab * qf * C * k1 * k2 / 86400

onde qf esta em L/hab.dia.

Vazao acumulada de um coletor = soma das vazoes proprias das bacias
vinculadas diretamente a ele + soma das vazoes acumuladas dos coletores
de montante que apontam para ele (cascata), respeitando a topologia
definida pelo usuario (bacia -> coletor -> coletor -> ...).

Diametro calculado: formula editavel (Manning), avaliada com eval() em um
ambiente restrito (apenas nomes Q, n, S, f e operadores matematicos).

Verificacoes complementares (NBR 9649) - declividade minima e tensao
trativa: ver funcoes `declividade_minima_m_m`, `raio_hidraulico_m` e
`tensao_trativa_pa` abaixo. Sao verificacoes NOVAS, adicionadas por cima
do que ja existia - o campo "critico" (DN calculado > DN existente)
continua funcionando exatamente igual, essas sao checagens extras
expostas em campos separados (ver FORMULAS_E_PARAMETROS.md, secao 11,
pra detalhes e ressalvas de interpretacao).
"""

import math


class ErroTopologia(Exception):
    pass


def calcular_vazao_bacia(area_ha, densidade_hab_ha, qf, C, k1, k2):
    hab = area_ha * densidade_hab_ha
    q_ls = hab * qf * C * k1 * k2 / 86400.0
    return hab, q_ls


def calcular_vazao_micromedicao(soma_consumo_ls, C, k1, k2):
    """Vazao de projeto a partir da soma dos pontos de micromedicao
    (consumo medido, ja em L/s) dentro da bacia: aplica os mesmos
    coeficientes de retorno e pico usados na estimativa por area/
    densidade, so que sobre o consumo medido real em vez do consumo per
    capita estimado."""
    return soma_consumo_ls * C * k1 * k2


def calcular_vazao_infiltracao(comprimento_m, c_inf):
    """Vazao de infiltracao de um trecho: Qinf (L/s) = Lt (m) * Cinf
    (L/s/m). Formula direta do Termo de Referencia SAMAE (item 6.3.1) -
    a NBR 9649 recomenda Cinf entre 0,05 e 1,0 L/s.km (= 0,00005 a
    0,001 L/s/m), a ser justificado; o SAMAE adota 0,0005 L/s/m como
    padrao (tubulacao com junta elastica, sem lencol freatico raso)."""
    if comprimento_m is None or c_inf is None:
        return 0.0
    return comprimento_m * c_inf


def raio_hidraulico_m(diametro_m, razao_h_d):
    """Raio hidraulico (m) de uma secao circular parcialmente cheia.

    `razao_h_d` e a lamina relativa geometrica h/D (0 a 1) - um
    parametro PROPRIO desta verificacao (separado do parametro
    'lamina_relativa'/f(h/D) usado na formula do diametro calculado, que
    e um fator empirico da planilha original do usuario, nao a razao
    h/D em si - ver FORMULAS_E_PARAMETROS.md secao 4/5 pra nao confundir
    os dois).

    Formula geometrica padrao (angulo central theta a partir de h/D):
        theta = 2*acos(1 - 2*(h/D))
        Rh = (D/4) * (1 - sen(theta)/theta)
    """
    if diametro_m is None or diametro_m <= 0 or razao_h_d is None:
        return None
    r = max(0.0, min(1.0, razao_h_d))
    if r <= 0:
        return 0.0
    if r >= 1:
        return diametro_m / 4.0  # secao cheia
    theta = 2 * math.acos(1 - 2 * r)
    if theta == 0:
        return 0.0
    return (diametro_m / 4.0) * (1 - math.sin(theta) / theta)


def tensao_trativa_pa(diametro_m, razao_h_d, declividade_m_m, peso_especifico=10000.0):
    """Tensao trativa (Pa): sigma_t = peso_especifico (N/m3) * Rh (m) *
    declividade (m/m). NBR 9649 recomenda sigma_t >= 1,0 Pa (auto-limpeza
    da tubulacao). `peso_especifico` default 10000 N/m3 (agua/esgoto
    diluido, valor usual de projeto), editavel."""
    if diametro_m is None or declividade_m_m is None:
        return None
    rh = raio_hidraulico_m(diametro_m, razao_h_d)
    if rh is None:
        return None
    return peso_especifico * rh * declividade_m_m


def declividade_minima_m_m(vazao_inicial_ls):
    """NBR 9649: Imin (m/m) = 0,0055 * Qi^(-0,47), com Qi em L/s.

    IMPORTANTE - simplificacao assumida aqui: a NBR distingue "vazao
    inicial de plano" (Qi, no inicio do horizonte de projeto) da vazao
    final; este plugin nao modela fases temporais separadas, entao usa a
    vazao acumulada calculada (Q_acumulado do trecho) tanto pra Qi quanto
    pra dimensionamento. Se seu projeto trabalha com vazao inicial e
    final distintas, use o campo de excecao pra ajustar manualmente onde
    precisar."""
    if vazao_inicial_ls is None or vazao_inicial_ls <= 0:
        return None
    return 0.0055 * (vazao_inicial_ls ** -0.47)


def velocidade_final_ms(diametro_m, razao_h_d, declividade_m_m, n_pvc=0.010):
    """Velocidade final do efluente (m/s), Termo de Referencia SAMAE item
    6.4.6: vf = (1/n) * Rh^(2/3) * Io^0,5. Repare que aqui o coeficiente
    de Manning e o do PVC (n_pvc, padrao 0,010) - DIFERENTE do 'rugosidade'
    (n=0,013) usado na formula do diametro/fator hidraulico. Sao dois
    coeficientes distintos no mesmo memorial de calculo, mantidos
    separados aqui de proposito."""
    if diametro_m is None or declividade_m_m is None or declividade_m_m <= 0:
        return None
    rh = raio_hidraulico_m(diametro_m, razao_h_d)
    if rh is None or rh <= 0:
        return None
    return (1.0 / n_pvc) * (rh ** (2.0 / 3.0)) * (declividade_m_m ** 0.5)


def velocidade_critica_ms(diametro_m, razao_h_d, gravidade=9.81):
    """Velocidade critica (m/s), Termo de Referencia SAMAE item 6.4.7:
    vc = 6 * (g * Rh)^0,5."""
    if diametro_m is None:
        return None
    rh = raio_hidraulico_m(diametro_m, razao_h_d)
    if rh is None or rh < 0:
        return None
    return 6.0 * ((gravidade * rh) ** 0.5)


def verificar_lamina_velocidade_tensao(
    diametro_m, razao_h_d, razao_h_d_reduzida, declividade_m_m, n_pvc, peso_especifico
):
    """Calcula velocidade final/critica e tensao trativa para um trecho,
    aplicando a REDUCAO AUTOMATICA da lamina quando a velocidade final
    excede a critica - a norma (Termo de Referencia SAMAE, item 6.4.7)
    manda reduzir a lamina maxima de projeto pra 50% do diametro nesse
    caso, entao o plugin recalcula tudo com essa lamina reduzida e usa
    esses valores "ajustados" como o resultado final, em vez de so
    sinalizar o problema sem resolver.

    Retorna um dict com velocidade_final, velocidade_critica,
    excede_velocidade_critica (apos o eventual ajuste - deveria dar
    sempre False, a nao ser que nem com a lamina reduzida resolva),
    lamina_reduzida_aplicada (bool - se precisou reduzir), tensao_trativa
    e atende_tensao_trativa (recalculados com a lamina final adotada)."""
    if diametro_m is None:
        return {
            "velocidade_final": None,
            "velocidade_critica": None,
            "excede_velocidade_critica": None,
            "lamina_reduzida_aplicada": False,
            "tensao_trativa": None,
            "atende_tensao_trativa": None,
        }

    lamina = razao_h_d
    vf = velocidade_final_ms(diametro_m, lamina, declividade_m_m, n_pvc)
    vc = velocidade_critica_ms(diametro_m, lamina)
    excede = (vf > vc) if (vf is not None and vc is not None) else None
    reducao_aplicada = False

    if excede:
        lamina_reduzida = razao_h_d_reduzida
        vf2 = velocidade_final_ms(diametro_m, lamina_reduzida, declividade_m_m, n_pvc)
        vc2 = velocidade_critica_ms(diametro_m, lamina_reduzida)
        if vf2 is not None and vc2 is not None:
            vf, vc = vf2, vc2
            excede = vf > vc
            lamina = lamina_reduzida
            reducao_aplicada = True

    tensao = tensao_trativa_pa(diametro_m, lamina, declividade_m_m, peso_especifico)
    atende_tensao = (tensao >= 1.0) if tensao is not None else None

    return {
        "velocidade_final": vf,
        "velocidade_critica": vc,
        "excede_velocidade_critica": excede,
        "lamina_reduzida_aplicada": reducao_aplicada,
        "tensao_trativa": tensao,
        "atende_tensao_trativa": atende_tensao,
    }


def _parametro_efetivo(nome, coletor_id, parametros_globais, excecoes_por_coletor):
    excecoes = excecoes_por_coletor.get(str(coletor_id), {})
    if nome in excecoes:
        return float(excecoes[nome])
    return float(parametros_globais[nome])


_EVAL_NOMES_PERMITIDOS = {"Q", "n", "S", "f", "math"}


def calcular_diametro(formula, Q, n, S, f):
    """Avalia a formula do diametro calculado (m) em ambiente restrito."""
    ambiente = {"__builtins__": {}, "math": math, "Q": Q, "n": n, "S": S, "f": f}
    try:
        valor = eval(formula, ambiente)
    except Exception as exc:
        raise ValueError(f"Erro ao avaliar formula do diametro: {exc}")
    return float(valor)


def montar_grafo(bacia_coletor_map, coletor_destino_map):
    """Retorna dict coletor_id -> {'bacias': [...], 'coletores_montante': [...]}"""
    grafo = {}

    def _no(cid):
        return grafo.setdefault(str(cid), {"bacias": [], "coletores_montante": []})

    for bacia_id, coletor_id in bacia_coletor_map.items():
        if coletor_id is None:
            continue
        _no(coletor_id)["bacias"].append(bacia_id)

    for coletor_id, destino_id in coletor_destino_map.items():
        if destino_id is None:
            continue
        _no(destino_id)["coletores_montante"].append(coletor_id)
        _no(coletor_id)  # garante que o coletor de montante tambem existe no grafo

    return grafo


def _detectar_ciclo(coletor_destino_map):
    """Levanta ErroTopologia se houver ciclo coletor -> coletor."""
    cor = {}  # 0 = nao visitado, 1 = em progresso, 2 = concluido

    def dfs(no, caminho):
        cor[no] = 1
        caminho.append(no)
        destino = coletor_destino_map.get(no)
        if destino is not None:
            if cor.get(destino, 0) == 1:
                ciclo = " -> ".join(caminho + [destino])
                raise ErroTopologia(f"Ciclo detectado na cascata de coletores: {ciclo}")
            if cor.get(destino, 0) == 0:
                dfs(destino, caminho)
        cor[no] = 2
        caminho.pop()

    for no in list(coletor_destino_map.keys()):
        if cor.get(no, 0) == 0:
            dfs(no, [])


def calcular_tudo(
    bacias_area_densidade,   # dict bacia_id -> (area_ha, densidade_hab_ha)
    bacia_coletor_map,       # dict bacia_id -> coletor_id
    coletor_destino_map,     # dict coletor_id -> coletor_destino_id
    dn_existente_map,        # dict coletor_id -> dn existente (m)
    parametros_globais,      # dict com qf, C, k1, k2, inclinacao, lamina_relativa,
                              #     rugosidade, formula_diametro, razao_h_d,
                              #     peso_especifico, c_inf, vazao_minima
    excecoes_por_coletor,    # dict coletor_id -> {parametro: valor}
    bacias_micromedicao=None,       # dict bacia_id -> soma_consumo_ls (opcional)
    bacias_usar_micromedicao=None,  # set/lista de bacia_id que devem usar micromedicao (opcional)
    comprimentos_trecho=None,       # dict coletor_id -> comprimento_m (opcional, p/ infiltracao)
):
    """
    Retorna lista de dicts, um por coletor presente no grafo:
        coletor_id, vazao_acumulada, vazao_domestica, vazao_infiltracao,
        dn_calculado, dn_adotado, dn_existente, critico, inclinacao_usada,
        rugosidade_usada, lamina_usada, declividade_minima,
        atende_declividade_minima, tensao_trativa_calc_pa,
        atende_tensao_trativa_calc, tensao_trativa_exist_pa,
        atende_tensao_trativa_exist, velocidade_final_calc,
        velocidade_critica_calc, excede_velocidade_critica_calc,
        velocidade_final_exist, velocidade_critica_exist,
        excede_velocidade_critica_exist
    Levanta ErroTopologia se detectar ciclo.

    `dn_adotado` = max(dn_calculado, dn_minimo) - o DN calculado bruto e
    mantido separado (pra auditoria), mas quem decide se o trecho e
    "critico" e o dn_adotado (dn_minimo padrao 0,15 m = DN150, conforme
    Termo de Referencia SAMAE item 7.3.3), ja que na pratica ninguem
    especifica uma tubulacao menor que o minimo de norma mesmo que o
    calculo hidraulico bruto sugira algo menor.

    Cada bacia usa vazao por AREA/DENSIDADE por padrao. Se o id da bacia
    estiver em `bacias_usar_micromedicao` E tiver soma de consumo em
    `bacias_micromedicao`, usa a vazao por micromedicao no lugar (ver
    `calcular_vazao_micromedicao`) - escolha manual por bacia, feita na
    interface do plugin.

    A vazao total de cada trecho e a soma de tres parcelas (conforme
    Termo de Referencia SAMAE, item 6.3.3 - Q = Qd + Qinf + Qc):
      - Qd: vazao domestica acumulada (das bacias, por area/densidade ou
        micromedicao)
      - Qinf: vazao de infiltracao, acumulada ao longo da cascata a
        partir do comprimento de CADA trecho (se `comprimentos_trecho`
        for informado) - cada coletor contribui com Lt*Cinf, que soma
        junto com o que vem de montante, igual a vazao domestica
      - Qc: vazao concentrada/singular - nao modelada automaticamente
        neste plugin (contribuicoes pontuais especificas); se precisar,
        use "Aplicar densidade" numa bacia fict­icia ou ajuste via
        excecao
    Depois de somado, se o total ficar abaixo da vazao minima de projeto
    (parametro 'vazao_minima', padrao 1,5 L/s pela NBR 9649), o valor
    minimo e adotado no lugar.
    """
    _detectar_ciclo(coletor_destino_map)

    qf = float(parametros_globais["qf"])
    C = float(parametros_globais["C"])
    k1 = float(parametros_globais["k1"])
    k2 = float(parametros_globais["k2"])
    razao_h_d = float(parametros_globais.get("razao_h_d", 0.75))
    peso_especifico = float(parametros_globais.get("peso_especifico", 10000.0))
    c_inf = float(parametros_globais.get("c_inf", 0.0005))
    vazao_minima = float(parametros_globais.get("vazao_minima", 1.5))
    dn_minimo = float(parametros_globais.get("dn_minimo", 0.15))
    n_pvc = float(parametros_globais.get("n_pvc", 0.010))
    razao_h_d_reduzida = float(parametros_globais.get("razao_h_d_reduzida", 0.50))
    espacamento_max_pv = float(parametros_globais.get("espacamento_max_pv", 80.0))

    bacias_micromedicao = bacias_micromedicao or {}
    bacias_usar_micromedicao = set(bacias_usar_micromedicao or [])
    comprimentos_trecho = comprimentos_trecho or {}

    # vazao propria de cada bacia (por area/densidade OU por micromedicao,
    # conforme escolha manual do usuario por bacia)
    vazao_bacia = {}
    for bacia_id, (area_ha, densidade) in bacias_area_densidade.items():
        usa_micro = bacia_id in bacias_usar_micromedicao and bacia_id in bacias_micromedicao
        if usa_micro:
            vazao_bacia[bacia_id] = calcular_vazao_micromedicao(
                bacias_micromedicao[bacia_id], C, k1, k2
            )
        elif area_ha is not None and densidade is not None:
            _, q = calcular_vazao_bacia(area_ha, densidade, qf, C, k1, k2)
            vazao_bacia[bacia_id] = q
    # bacias que so tem micromedicao (sem densidade/area definida) tambem entram
    for bacia_id in bacias_usar_micromedicao:
        if bacia_id not in vazao_bacia and bacia_id in bacias_micromedicao:
            vazao_bacia[bacia_id] = calcular_vazao_micromedicao(
                bacias_micromedicao[bacia_id], C, k1, k2
            )

    grafo = montar_grafo(bacia_coletor_map, coletor_destino_map)

    memo_domestica = {}
    memo_infiltracao = {}

    def vazao_domestica_acumulada(coletor_id):
        coletor_id = str(coletor_id)
        if coletor_id in memo_domestica:
            return memo_domestica[coletor_id]
        no = grafo.get(coletor_id, {"bacias": [], "coletores_montante": []})
        total = sum(vazao_bacia.get(b, 0.0) for b in no["bacias"])
        for montante in no["coletores_montante"]:
            total += vazao_domestica_acumulada(montante)
        memo_domestica[coletor_id] = total
        return total

    def vazao_infiltracao_acumulada(coletor_id):
        coletor_id = str(coletor_id)
        if coletor_id in memo_infiltracao:
            return memo_infiltracao[coletor_id]
        no = grafo.get(coletor_id, {"bacias": [], "coletores_montante": []})
        proprio = calcular_vazao_infiltracao(comprimentos_trecho.get(coletor_id), c_inf)
        total = proprio
        for montante in no["coletores_montante"]:
            total += vazao_infiltracao_acumulada(montante)
        memo_infiltracao[coletor_id] = total
        return total

    resultados = []
    for coletor_id in grafo.keys():
        q_domestica = vazao_domestica_acumulada(coletor_id)
        q_infiltracao = vazao_infiltracao_acumulada(coletor_id)
        q_bruta = q_domestica + q_infiltracao
        q_acum = max(q_bruta, vazao_minima) if q_bruta > 0 else q_bruta

        n = _parametro_efetivo("rugosidade", coletor_id, parametros_globais, excecoes_por_coletor)
        S = _parametro_efetivo("inclinacao", coletor_id, parametros_globais, excecoes_por_coletor)
        f = _parametro_efetivo(
            "lamina_relativa", coletor_id, parametros_globais, excecoes_por_coletor
        )

        dn_calc = None
        if q_acum > 0:
            try:
                dn_calc = calcular_diametro(
                    parametros_globais["formula_diametro"], q_acum / 1000.0, n, S, f
                )
            except ValueError:
                dn_calc = None

        # DN adotado = maior entre o calculado e o minimo de norma (SAMAE
        # adota DN 150mm como piso, item 7.3.3 do Termo de Referencia) -
        # e esse valor "realista" que compara com o DN existente pra
        # decidir se o trecho e critico, nao o DN calculado bruto (que as
        # vezes da um valor menor que o minimo permitido, o que nao seria
        # o diametro de fato especificado num projeto real)
        dn_adotado = max(dn_calc, dn_minimo) if dn_calc is not None else None

        dn_exist = dn_existente_map.get(coletor_id)
        critico = False
        if dn_adotado is not None and dn_exist is not None:
            critico = dn_adotado > dn_exist

        # --- verificacoes complementares NBR 9649 ---
        declividade_min = declividade_minima_m_m(q_acum) if q_acum > 0 else None
        atende_decliv_min = (S >= declividade_min) if declividade_min is not None else None

        # tensao trativa + velocidade final/critica, com reducao
        # automatica da lamina pra 50% quando vf excede vc (a norma manda
        # ajustar, nao so avisar) - calculado separado pro DN adotado e
        # pro DN existente, ja que cada um pode precisar (ou nao) da
        # reducao
        verif_calc = verificar_lamina_velocidade_tensao(
            dn_adotado, razao_h_d, razao_h_d_reduzida, S, n_pvc, peso_especifico
        )
        verif_exist = verificar_lamina_velocidade_tensao(
            dn_exist, razao_h_d, razao_h_d_reduzida, S, n_pvc, peso_especifico
        )

        # espacamento maximo entre pocos de visita (checagem geometrica -
        # cada trecho e o segmento entre dois PVs consecutivos, entao o
        # comprimento do proprio trecho e o espacamento a conferir)
        comprimento_trecho = comprimentos_trecho.get(coletor_id)
        excede_espacamento = (
            (comprimento_trecho > espacamento_max_pv) if comprimento_trecho is not None else None
        )

        resultados.append(
            {
                "coletor_id": coletor_id,
                "vazao_acumulada": q_acum,
                "vazao_domestica": q_domestica,
                "vazao_infiltracao": q_infiltracao,
                "dn_calculado": dn_calc,
                "dn_adotado": dn_adotado,
                "dn_existente": dn_exist,
                "critico": critico,
                "inclinacao_usada": S,       # m/m
                "rugosidade_usada": n,
                "lamina_usada": f,
                "declividade_minima": declividade_min,
                "atende_declividade_minima": atende_decliv_min,
                "tensao_trativa_calc_pa": verif_calc["tensao_trativa"],
                "atende_tensao_trativa_calc": verif_calc["atende_tensao_trativa"],
                "tensao_trativa_exist_pa": verif_exist["tensao_trativa"],
                "atende_tensao_trativa_exist": verif_exist["atende_tensao_trativa"],
                "velocidade_final_calc": verif_calc["velocidade_final"],
                "velocidade_critica_calc": verif_calc["velocidade_critica"],
                "excede_velocidade_critica_calc": verif_calc["excede_velocidade_critica"],
                "lamina_reduzida_calc": verif_calc["lamina_reduzida_aplicada"],
                "velocidade_final_exist": verif_exist["velocidade_final"],
                "velocidade_critica_exist": verif_exist["velocidade_critica"],
                "excede_velocidade_critica_exist": verif_exist["excede_velocidade_critica"],
                "lamina_reduzida_exist": verif_exist["lamina_reduzida_aplicada"],
                "comprimento_trecho_m": comprimento_trecho,
                "excede_espacamento_pv": excede_espacamento,
            }
        )

    return resultados
