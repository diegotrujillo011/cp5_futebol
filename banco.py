# pip install oracledb

import os
from getpass import getpass

import oracledb

# Usa as variáveis de ambiente DB_USER, DB_PASSWORD e DB_DSN.
# Se DB_USER ou DB_PASSWORD não existirem, o programa pede na hora.
DB_USER = os.getenv("DB_USER") or input("Usuário Oracle: ").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD") or getpass("Senha Oracle: ")
# DSN (Data Source Name) do Oracle da FIAP
DB_DSN = os.getenv("DB_DSN", "oracle.fiap.com.br:1521/ORCL")


def obter_conexao():
    try:
        # Corrigido: password (com dois 's') e dsn em vez de dns
        conexao = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        return conexao
    except oracledb.Error as e:
        print(f"Erro ao conectar com Oracle DB: {e}")
        return None


def criar_tabela():
    sql = """
    CREATE TABLE PARTIDAS_BRASILEIRAO (
        ID_PARTIDA NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        ID_ESPN VARCHAR2(30) UNIQUE NOT NULL,
        ANO NUMBER(4) NOT NULL,
        DATA_PARTIDA VARCHAR2(35),
        MANDANTE VARCHAR2(100) NOT NULL,
        GOLS_MANDANTE NUMBER(2) NOT NULL,
        VISITANTE VARCHAR2(100) NOT NULL,
        GOLS_VISITANTE NUMBER(2) NOT NULL,
        TOTAL_GOLS NUMBER(2) NOT NULL,
        DIFERENCA_GOLS NUMBER(2) NOT NULL,
        RESULTADO VARCHAR2(30) NOT NULL,
        CATEGORIA VARCHAR2(20) NOT NULL,
        PONTOS_MANDANTE NUMBER(1) NOT NULL,
        PONTOS_VISITANTE NUMBER(1) NOT NULL
    )
    """

    conexao = obter_conexao()
    if conexao:
        cursor = conexao.cursor()
        try:
            cursor.execute(
                'SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME = :1',
                ('PARTIDAS_BRASILEIRAO',),
            )

            if cursor.fetchone():
                print('A tabela já existe.')
                return True

            cursor.execute(sql)
            print('Tabela criada com sucesso.')
            return True
        except oracledb.Error as erro:
            print(f'Erro ao criar a tabela: {erro}')
            return False
        finally:
            cursor.close()
            conexao.close()
    return False


def salvar_partidas(partidas):
    conexao = obter_conexao()
    if conexao:
        try:
            cursor = conexao.cursor()
            inseridas = 0
            ignoradas = 0

            for partida in partidas:
                cursor.execute(
                    'SELECT ID_PARTIDA FROM PARTIDAS_BRASILEIRAO WHERE ID_ESPN = :1',
                    (partida['id_espn'],),
                )
                existente = cursor.fetchone()

                if existente:
                    ignoradas += 1
                else:
                    cursor.execute(
                        'INSERT INTO PARTIDAS_BRASILEIRAO '
                        '(ID_ESPN, ANO, DATA_PARTIDA, MANDANTE, GOLS_MANDANTE, VISITANTE, '
                        'GOLS_VISITANTE, TOTAL_GOLS, DIFERENCA_GOLS, RESULTADO, CATEGORIA, '
                        'PONTOS_MANDANTE, PONTOS_VISITANTE) '
                        'VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13)',
                        (partida['id_espn'], partida['ano'], partida['data'],
                         partida['mandante'], partida['gols_mandante'], partida['visitante'],
                         partida['gols_visitante'], partida['total_gols'],
                         partida['diferenca_gols'], partida['resultado'], partida['categoria'],
                         partida['pontos_mandante'], partida['pontos_visitante']),
                    )
                    inseridas += 1

            conexao.commit()
            print(f'Partidas inseridas: {inseridas}')
            print(f'Partidas já cadastradas: {ignoradas}')
        except oracledb.Error as erro:
            conexao.rollback()
            print(f'Erro ao salvar partidas: {erro}')
        finally:
            conexao.close()


def consultar_partidas(ano):
    conexao = obter_conexao()
    if conexao:
        try:
            cursor = conexao.cursor()
            cursor.execute(
                'SELECT MANDANTE, GOLS_MANDANTE, VISITANTE, GOLS_VISITANTE, DATA_PARTIDA '
                'FROM PARTIDAS_BRASILEIRAO WHERE ANO = :1 ORDER BY DATA_PARTIDA',
                (ano,),
            )
            return cursor.fetchall()
        except oracledb.Error as erro:
            print(f'Erro ao consultar partidas: {erro}')
            return None
        finally:
            conexao.close()
    return None

