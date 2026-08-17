# -*- coding: utf-8 -*-
"""
Banco auxiliar (SQLite) do plugin.

Nao duplicamos geometria das camadas do usuario. Este banco guarda apenas:
- vinculos bacia -> coletor
- vinculos coletor -> coletor (cascata)
- parametros globais e excecoes por trecho
- tabela de densidades (hab/ha) editavel
- resultados calculados (vazao acumulada, diametro calculado etc)

As chaves (bacia_id, coletor_id) sao o valor do campo de ID escolhido pelo
usuario nas camadas originais (ex: NOME, SIGLA, id) - sempre como texto.
"""

import sqlite3
import os

SCHEMA = """
CREATE TABLE IF NOT EXISTS bacia_dados (
    bacia_id TEXT PRIMARY KEY,
    densidade_hab_ha REAL,
    area_ha_manual REAL,
    usar_micromedicao INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bacia_coletor (
    bacia_id TEXT PRIMARY KEY,
    coletor_id TEXT
);

CREATE TABLE IF NOT EXISTS coletor_coletor (
    coletor_id TEXT PRIMARY KEY,
    coletor_destino_id TEXT
);

CREATE TABLE IF NOT EXISTS parametros (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS excecoes (
    coletor_id TEXT,
    parametro TEXT,
    valor REAL,
    PRIMARY KEY (coletor_id, parametro)
);

CREATE TABLE IF NOT EXISTS densidades (
    nome TEXT PRIMARY KEY,
    hab_ha REAL
);

CREATE TABLE IF NOT EXISTS resultados (
    coletor_id TEXT PRIMARY KEY,
    vazao_acumulada REAL,
    dn_calculado REAL,
    dn_existente REAL,
    critico INTEGER,
    inclinacao_usada REAL,
    declividade_minima REAL,
    atende_declividade_minima INTEGER,
    tensao_trativa_calc_pa REAL,
    atende_tensao_trativa_calc INTEGER,
    tensao_trativa_exist_pa REAL,
    atende_tensao_trativa_exist INTEGER,
    vazao_domestica REAL,
    vazao_infiltracao REAL,
    dn_adotado REAL,
    velocidade_final_calc REAL,
    velocidade_critica_calc REAL,
    excede_velocidade_critica_calc INTEGER,
    velocidade_final_exist REAL,
    velocidade_critica_exist REAL,
    excede_velocidade_critica_exist INTEGER,
    lamina_reduzida_calc INTEGER,
    lamina_reduzida_exist INTEGER,
    comprimento_trecho_m REAL,
    excede_espacamento_pv INTEGER
);

CREATE TABLE IF NOT EXISTS configuracao (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS cotas (
    coletor_id TEXT PRIMARY KEY,
    cota_inicio REAL,
    cota_final REAL,
    comprimento_m REAL
);

CREATE TABLE IF NOT EXISTS pontos_micromedicao (
    ponto_id TEXT PRIMARY KEY,
    x REAL,
    y REAL,
    consumo_ls REAL,
    bacia_id TEXT
);
"""

PARAMETROS_PADRAO = {
    "qf": "150",          # L/hab.dia
    "C": "0.8",            # coeficiente de retorno
    "k1": "1.2",            # coef dia de maior consumo
    "k2": "1.5",            # coef hora de maior consumo
    "inclinacao": "0.004",  # m/m
    "lamina_relativa": "0.7",  # h/D -> f(h/D)
    "rugosidade": "0.013",  # Manning n
    # Formula do diametro calculado (m), editavel pelo usuario.
    # Variaveis disponiveis: Q (m3/s), n, S (inclinacao), f (f de h/D)
    # Transcrita direto da planilha do usuario:
    # =((4*(Q/1000))*n)/(PI()*f*(S^(1/2))*0,3969))^(3/8)
    "formula_diametro": "((4*Q*n)/(math.pi*f*(S**0.5)*0.3969))**(3/8)",
    # Parametros das verificacoes complementares (NBR 9649):
    "razao_h_d": "0.75",     # lamina relativa h/D geometrica (0 a 1), usada
                              # so na tensao trativa/raio hidraulico - NAO
                              # e o mesmo que 'lamina_relativa' (f) acima,
                              # que e usado na formula do diametro
    "peso_especifico": "10000",  # N/m3, peso especifico do esgoto p/ tensao trativa
    "c_inf": "0.0005",        # L/s/m, coeficiente de infiltracao (NBR 9649: 0,00005 a 0,001)
    "vazao_minima": "1.5",    # L/s, vazao minima de projeto por trecho (NBR 9649)
    "dn_minimo": "0.15",      # m (150mm), diametro minimo de projeto (SAMAE)
    "n_pvc": "0.010",         # rugosidade de Manning do PVC, so p/ velocidade final/critica
    "razao_h_d_reduzida": "0.50",  # h/D aplicado automaticamente quando vf > vc (SAMAE item 6.4.7)
    "espacamento_max_pv": "80",    # m, espacamento maximo entre pocos de visita (SAMAE)
}

# formula antiga (v1.0-v1.9), usada so pra migrar automaticamente bancos
# ja criados que ainda estao com o valor padrao antigo (sem o 0.3969)
_FORMULA_DIAMETRO_ANTIGA = "((4*Q*n)/(3.1415926536*(S**0.5)*f))**(3/8)"

DENSIDADES_PADRAO = [
    ("Residencial de luxo (lote 800 m2)", 100),
    ("Residencial medio (lote 450 m2)", 120),
    ("Misto popular (lote 250 m2)", 150),
    ("Misto residencial/comercial central (predios 3-4 pav.)", 300),
    ("Misto residencial/comercial central (edificios 10-12 pav.)", 450),
    ("Misto residencial-comercial-industrial (comercio/industria leve)", 600),
    ("Comercial da zona central (edificios de escritorio)", 1000),
]


class RedeDB:
    def __init__(self, path):
        self.path = path
        novo = not os.path.exists(path)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrar_colunas_novas()
        if novo:
            self._popular_padroes()
        else:
            self._migrar_formula_antiga()

    def _migrar_colunas_novas(self):
        """Adiciona colunas/parametros novos em bancos criados por versoes
        antigas do plugin (CREATE TABLE IF NOT EXISTS nao altera tabelas ja
        existentes, e INSERT OR IGNORE nao roda de novo em banco existente)."""
        cur = self.conn.execute("PRAGMA table_info(resultados)")
        colunas_resultados = {linha["name"] for linha in cur.fetchall()}
        colunas_novas_resultados = {
            "inclinacao_usada": "REAL",
            "declividade_minima": "REAL",
            "atende_declividade_minima": "INTEGER",
            "tensao_trativa_calc_pa": "REAL",
            "atende_tensao_trativa_calc": "INTEGER",
            "tensao_trativa_exist_pa": "REAL",
            "atende_tensao_trativa_exist": "INTEGER",
            "vazao_domestica": "REAL",
            "vazao_infiltracao": "REAL",
            "dn_adotado": "REAL",
            "velocidade_final_calc": "REAL",
            "velocidade_critica_calc": "REAL",
            "excede_velocidade_critica_calc": "INTEGER",
            "velocidade_final_exist": "REAL",
            "velocidade_critica_exist": "REAL",
            "excede_velocidade_critica_exist": "INTEGER",
            "lamina_reduzida_calc": "INTEGER",
            "lamina_reduzida_exist": "INTEGER",
            "comprimento_trecho_m": "REAL",
            "excede_espacamento_pv": "INTEGER",
        }
        for nome, tipo in colunas_novas_resultados.items():
            if nome not in colunas_resultados:
                self.conn.execute(f"ALTER TABLE resultados ADD COLUMN {nome} {tipo}")

        cur = self.conn.execute("PRAGMA table_info(bacia_dados)")
        colunas_bacia = {linha["name"] for linha in cur.fetchall()}
        if "usar_micromedicao" not in colunas_bacia:
            self.conn.execute(
                "ALTER TABLE bacia_dados ADD COLUMN usar_micromedicao INTEGER DEFAULT 0"
            )

        # parametros novos (razao_h_d, peso_especifico, c_inf, vazao_minima) -
        # insere o padrao se o banco for de uma versao anterior a essas
        # verificacoes existirem
        for chave in (
            "razao_h_d", "peso_especifico", "c_inf", "vazao_minima", "dn_minimo",
            "n_pvc", "razao_h_d_reduzida", "espacamento_max_pv",
        ):
            self.conn.execute(
                "INSERT OR IGNORE INTO parametros (chave, valor) VALUES (?, ?)",
                (chave, PARAMETROS_PADRAO[chave]),
            )

        self.conn.commit()

    def _migrar_formula_antiga(self):
        """Se o banco ja existia com a formula padrao antiga (sem o fator
        0.3969), atualiza sozinho para a formula corrigida. Se o usuario ja
        tiver customizado a formula manualmente, nao mexe."""
        cur = self.conn.execute(
            "SELECT valor FROM parametros WHERE chave='formula_diametro'"
        )
        row = cur.fetchone()
        if row and row["valor"].strip() == _FORMULA_DIAMETRO_ANTIGA:
            self.set_parametro("formula_diametro", PARAMETROS_PADRAO["formula_diametro"])

    def _popular_padroes(self):
        cur = self.conn.cursor()
        for chave, valor in PARAMETROS_PADRAO.items():
            cur.execute(
                "INSERT OR IGNORE INTO parametros (chave, valor) VALUES (?, ?)",
                (chave, valor),
            )
        for nome, hab_ha in DENSIDADES_PADRAO:
            cur.execute(
                "INSERT OR IGNORE INTO densidades (nome, hab_ha) VALUES (?, ?)",
                (nome, hab_ha),
            )
        self.conn.commit()

    # ---------- vinculos ----------
    def set_bacia_coletor(self, bacia_id, coletor_id):
        self.conn.execute(
            "INSERT INTO bacia_coletor (bacia_id, coletor_id) VALUES (?, ?) "
            "ON CONFLICT(bacia_id) DO UPDATE SET coletor_id=excluded.coletor_id",
            (str(bacia_id), str(coletor_id)),
        )
        self.conn.commit()

    def remove_bacia_coletor(self, bacia_id):
        self.conn.execute("DELETE FROM bacia_coletor WHERE bacia_id=?", (str(bacia_id),))
        self.conn.commit()

    def set_coletor_destino(self, coletor_id, coletor_destino_id):
        if str(coletor_id) == str(coletor_destino_id):
            raise ValueError("Um coletor nao pode apontar para ele mesmo.")
        self.conn.execute(
            "INSERT INTO coletor_coletor (coletor_id, coletor_destino_id) VALUES (?, ?) "
            "ON CONFLICT(coletor_id) DO UPDATE SET coletor_destino_id=excluded.coletor_destino_id",
            (str(coletor_id), str(coletor_destino_id)),
        )
        self.conn.commit()

    def remove_coletor_destino(self, coletor_id):
        self.conn.execute("DELETE FROM coletor_coletor WHERE coletor_id=?", (str(coletor_id),))
        self.conn.commit()

    def get_bacia_coletor_map(self):
        cur = self.conn.execute("SELECT bacia_id, coletor_id FROM bacia_coletor")
        return {r["bacia_id"]: r["coletor_id"] for r in cur.fetchall()}

    def get_coletor_destino_map(self):
        cur = self.conn.execute("SELECT coletor_id, coletor_destino_id FROM coletor_coletor")
        return {r["coletor_id"]: r["coletor_destino_id"] for r in cur.fetchall()}

    # ---------- dados da bacia ----------
    def set_bacia_densidade(self, bacia_id, hab_ha, area_manual=None):
        self.conn.execute(
            "INSERT INTO bacia_dados (bacia_id, densidade_hab_ha, area_ha_manual) VALUES (?, ?, ?) "
            "ON CONFLICT(bacia_id) DO UPDATE SET densidade_hab_ha=excluded.densidade_hab_ha, "
            "area_ha_manual=excluded.area_ha_manual",
            (str(bacia_id), hab_ha, area_manual),
        )
        self.conn.commit()

    def set_bacia_usar_micromedicao(self, bacia_id, usar):
        self.conn.execute(
            "INSERT INTO bacia_dados (bacia_id, usar_micromedicao) VALUES (?, ?) "
            "ON CONFLICT(bacia_id) DO UPDATE SET usar_micromedicao=excluded.usar_micromedicao",
            (str(bacia_id), 1 if usar else 0),
        )
        self.conn.commit()

    def get_bacia_dados(self, bacia_id):
        cur = self.conn.execute(
            "SELECT densidade_hab_ha, area_ha_manual, usar_micromedicao "
            "FROM bacia_dados WHERE bacia_id=?",
            (str(bacia_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def get_all_bacia_dados(self):
        cur = self.conn.execute("SELECT * FROM bacia_dados")
        return {r["bacia_id"]: dict(r) for r in cur.fetchall()}

    # ---------- micromedicao (pontos importados de CSV) ----------
    def substituir_pontos_micromedicao(self, pontos):
        """Substitui TODOS os pontos de micromedicao pelos da lista nova
        (uma nova importacao de CSV apaga a anterior). `pontos` e uma
        lista de dicts: ponto_id, x, y, consumo_ls, bacia_id (bacia_id
        pode vir None, preenchido depois pelo cruzamento espacial)."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM pontos_micromedicao")
        for p in pontos:
            cur.execute(
                "INSERT INTO pontos_micromedicao (ponto_id, x, y, consumo_ls, bacia_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(p["ponto_id"]), p.get("x"), p.get("y"), p.get("consumo_ls"), p.get("bacia_id")),
            )
        self.conn.commit()

    def atualizar_bacia_dos_pontos(self, mapa_ponto_bacia):
        """Atualiza o bacia_id de cada ponto (resultado do cruzamento
        espacial ponto-dentro-do-poligono). `mapa_ponto_bacia`: dict
        ponto_id -> bacia_id (ou None se nao caiu em nenhuma bacia)."""
        cur = self.conn.cursor()
        for ponto_id, bacia_id in mapa_ponto_bacia.items():
            cur.execute(
                "UPDATE pontos_micromedicao SET bacia_id=? WHERE ponto_id=?",
                (bacia_id, str(ponto_id)),
            )
        self.conn.commit()

    def get_pontos_micromedicao(self):
        cur = self.conn.execute("SELECT * FROM pontos_micromedicao")
        return [dict(r) for r in cur.fetchall()]

    def get_soma_consumo_por_bacia(self):
        """dict bacia_id -> soma de consumo_ls dos pontos dentro dela."""
        cur = self.conn.execute(
            "SELECT bacia_id, SUM(consumo_ls) AS soma FROM pontos_micromedicao "
            "WHERE bacia_id IS NOT NULL GROUP BY bacia_id"
        )
        return {r["bacia_id"]: r["soma"] for r in cur.fetchall() if r["soma"] is not None}

    # ---------- parametros ----------
    def get_parametros(self):
        cur = self.conn.execute("SELECT chave, valor FROM parametros")
        return {r["chave"]: r["valor"] for r in cur.fetchall()}

    def set_parametro(self, chave, valor):
        self.conn.execute(
            "INSERT INTO parametros (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, str(valor)),
        )
        self.conn.commit()

    def get_excecoes(self, coletor_id):
        cur = self.conn.execute(
            "SELECT parametro, valor FROM excecoes WHERE coletor_id=?", (str(coletor_id),)
        )
        return {r["parametro"]: r["valor"] for r in cur.fetchall()}

    def get_all_excecoes(self):
        cur = self.conn.execute("SELECT coletor_id, parametro, valor FROM excecoes")
        out = {}
        for r in cur.fetchall():
            out.setdefault(r["coletor_id"], {})[r["parametro"]] = r["valor"]
        return out

    def set_excecao(self, coletor_id, parametro, valor):
        self.conn.execute(
            "INSERT INTO excecoes (coletor_id, parametro, valor) VALUES (?, ?, ?) "
            "ON CONFLICT(coletor_id, parametro) DO UPDATE SET valor=excluded.valor",
            (str(coletor_id), parametro, valor),
        )
        self.conn.commit()

    def remove_excecao(self, coletor_id, parametro):
        self.conn.execute(
            "DELETE FROM excecoes WHERE coletor_id=? AND parametro=?",
            (str(coletor_id), parametro),
        )
        self.conn.commit()

    # ---------- densidades ----------
    def get_densidades(self):
        cur = self.conn.execute("SELECT nome, hab_ha FROM densidades ORDER BY hab_ha")
        return [(r["nome"], r["hab_ha"]) for r in cur.fetchall()]

    def add_densidade(self, nome, hab_ha):
        self.conn.execute(
            "INSERT OR REPLACE INTO densidades (nome, hab_ha) VALUES (?, ?)", (nome, hab_ha)
        )
        self.conn.commit()

    # ---------- resultados ----------
    def salvar_resultados(self, resultados):
        """resultados: lista de dicts com coletor_id, vazao_acumulada, dn_calculado,
        dn_existente, critico, inclinacao_usada, declividade_minima,
        atende_declividade_minima, tensao_trativa_calc_pa,
        atende_tensao_trativa_calc, tensao_trativa_exist_pa,
        atende_tensao_trativa_exist, vazao_domestica, vazao_infiltracao,
        dn_adotado, velocidade_final_calc, velocidade_critica_calc,
        excede_velocidade_critica_calc, velocidade_final_exist,
        velocidade_critica_exist, excede_velocidade_critica_exist,
        lamina_reduzida_calc, lamina_reduzida_exist, comprimento_trecho_m,
        excede_espacamento_pv"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM resultados")

        def _bool_ou_none(v):
            return None if v is None else (1 if v else 0)

        for r in resultados:
            cur.execute(
                "INSERT INTO resultados (coletor_id, vazao_acumulada, dn_calculado, "
                "dn_existente, critico, inclinacao_usada, declividade_minima, "
                "atende_declividade_minima, tensao_trativa_calc_pa, "
                "atende_tensao_trativa_calc, tensao_trativa_exist_pa, "
                "atende_tensao_trativa_exist, vazao_domestica, vazao_infiltracao, "
                "dn_adotado, velocidade_final_calc, velocidade_critica_calc, "
                "excede_velocidade_critica_calc, velocidade_final_exist, "
                "velocidade_critica_exist, excede_velocidade_critica_exist, "
                "lamina_reduzida_calc, lamina_reduzida_exist, comprimento_trecho_m, "
                "excede_espacamento_pv) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(r["coletor_id"]),
                    r.get("vazao_acumulada"),
                    r.get("dn_calculado"),
                    r.get("dn_existente"),
                    1 if r.get("critico") else 0,
                    r.get("inclinacao_usada"),
                    r.get("declividade_minima"),
                    _bool_ou_none(r.get("atende_declividade_minima")),
                    r.get("tensao_trativa_calc_pa"),
                    _bool_ou_none(r.get("atende_tensao_trativa_calc")),
                    r.get("tensao_trativa_exist_pa"),
                    _bool_ou_none(r.get("atende_tensao_trativa_exist")),
                    r.get("vazao_domestica"),
                    r.get("vazao_infiltracao"),
                    r.get("dn_adotado"),
                    r.get("velocidade_final_calc"),
                    r.get("velocidade_critica_calc"),
                    _bool_ou_none(r.get("excede_velocidade_critica_calc")),
                    r.get("velocidade_final_exist"),
                    r.get("velocidade_critica_exist"),
                    _bool_ou_none(r.get("excede_velocidade_critica_exist")),
                    _bool_ou_none(r.get("lamina_reduzida_calc")),
                    _bool_ou_none(r.get("lamina_reduzida_exist")),
                    r.get("comprimento_trecho_m"),
                    _bool_ou_none(r.get("excede_espacamento_pv")),
                ),
            )
        self.conn.commit()

    def get_resultados(self):
        cur = self.conn.execute("SELECT * FROM resultados")
        return [dict(r) for r in cur.fetchall()]

    # ---------- configuracao (lembra camadas/campos usados) ----------
    def get_config(self):
        cur = self.conn.execute("SELECT chave, valor FROM configuracao")
        return {r["chave"]: r["valor"] for r in cur.fetchall()}

    def set_config(self, chave, valor):
        self.conn.execute(
            "INSERT INTO configuracao (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, str(valor) if valor is not None else None),
        )
        self.conn.commit()

    # ---------- cotas por trecho (pra calcular a declividade sozinho) ----------
    def set_cotas(self, coletor_id, cota_inicio, cota_final, comprimento_m):
        self.conn.execute(
            "INSERT INTO cotas (coletor_id, cota_inicio, cota_final, comprimento_m) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(coletor_id) DO UPDATE SET "
            "cota_inicio=excluded.cota_inicio, cota_final=excluded.cota_final, "
            "comprimento_m=excluded.comprimento_m",
            (str(coletor_id), cota_inicio, cota_final, comprimento_m),
        )
        self.conn.commit()

    def get_cotas(self, coletor_id):
        cur = self.conn.execute(
            "SELECT cota_inicio, cota_final, comprimento_m FROM cotas WHERE coletor_id=?",
            (str(coletor_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def close(self):
        self.conn.close()
