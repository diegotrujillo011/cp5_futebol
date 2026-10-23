# pip install requests

from datetime import date

import requests
import banco


URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard'


def buscar_partidas(ano):
    try:
        requisicao = requests.get(URL, params={'dates': ano, 'limit': 500}, timeout=10)

        if requisicao.status_code == 200:
            dados = requisicao.json()
            return dados['events']
        elif requisicao.status_code == 400:
            print('Consulta inválida.')
        elif requisicao.status_code == 403:
            print('Acesso negado pela ESPN.')
        elif requisicao.status_code == 404:
            print('Campeonato não encontrado.')
        elif requisicao.status_code == 429:
            print('Limite de consultas da ESPN atingido.')
        elif requisicao.status_code >= 500:
            print('Servidor da ESPN fora do ar.')
        else:
            print(f'Erro: {requisicao.status_code}')

    except requests.ConnectionError as erro:
        print(f'Erro de conexão: {erro}')
    except Exception as erro:
        print(f'Erro: {erro}')

    return None


def normalizar_partida(evento, ano):
    competicao = evento['competitions'][0]
    mandante = None
    visitante = None

    for equipe in competicao['competitors']:
        if equipe['homeAway'] == 'home':
            mandante = equipe
        elif equipe['homeAway'] == 'away':
            visitante = equipe

    if mandante is None or visitante is None:
        return None

    situacao = evento.get('status') or competicao.get('status', {})
    status = situacao.get('type', {})
    if status.get('completed') is not True and status.get('state') != 'post':
        return None

    try:
        gols_mandante = int(mandante['score'])
        gols_visitante = int(visitante['score'])
    except (KeyError, TypeError, ValueError):
        return None

    if gols_mandante > gols_visitante:
        resultado = 'VITORIA_MANDANTE'
        pontos_mandante = 3
        pontos_visitante = 0
    elif gols_visitante > gols_mandante:
        resultado = 'VITORIA_VISITANTE'
        pontos_mandante = 0
        pontos_visitante = 3
    else:
        resultado = 'EMPATE'
        pontos_mandante = 1
        pontos_visitante = 1

    total_gols = gols_mandante + gols_visitante
    return {
        'id_espn': evento['id'],
        'ano': ano,
        'data': evento['date'],
        'mandante': mandante['team'].get('displayName') or mandante['team']['name'],
        'gols_mandante': gols_mandante,
        'visitante': visitante['team'].get('displayName') or visitante['team']['name'],
        'gols_visitante': gols_visitante,
        'total_gols': total_gols,
        'diferenca_gols': abs(gols_mandante - gols_visitante),
        'resultado': resultado,
        'categoria': 'POUCOS_GOLS' if total_gols <= 2 else 'MUITOS_GOLS',
        'pontos_mandante': pontos_mandante,
        'pontos_visitante': pontos_visitante,
    }


def processar_partidas(eventos, ano):
    partidas = []

    for evento in eventos:
        partida = normalizar_partida(evento, ano)
        if partida is not None:
            partidas.append(partida)

    return partidas


def importar_brasileirao(ano):
    eventos = buscar_partidas(ano)
    if eventos is None:
        return

    partidas = processar_partidas(eventos, ano)
    banco.salvar_partidas(partidas)


def gerar_classificacao(ano):
    partidas = banco.consultar_partidas(ano)
    if partidas is None:
        return None

    classificacao = {}

    for partida in partidas:
        for nome, gols_feitos, gols_sofridos in (
            (partida[0], partida[1], partida[3]),
            (partida[2], partida[3], partida[1]),
        ):
            if nome not in classificacao:
                classificacao[nome] = {
                    'equipe': nome, 'jogos': 0, 'vitorias': 0, 'empates': 0,
                    'derrotas': 0, 'gols_marcados': 0, 'gols_sofridos': 0, 'pontos': 0,
                }

            equipe = classificacao[nome]
            equipe['jogos'] += 1
            equipe['gols_marcados'] += gols_feitos
            equipe['gols_sofridos'] += gols_sofridos

            if gols_feitos > gols_sofridos:
                equipe['vitorias'] += 1
                equipe['pontos'] += 3
            elif gols_feitos == gols_sofridos:
                equipe['empates'] += 1
                equipe['pontos'] += 1
            else:
                equipe['derrotas'] += 1

    for equipe in classificacao.values():
        equipe['saldo_gols'] = equipe['gols_marcados'] - equipe['gols_sofridos']

    return sorted(
        classificacao.values(),
        key=lambda equipe: (
            -equipe['pontos'], -equipe['vitorias'],
            -equipe['saldo_gols'], -equipe['gols_marcados'],
        ),
    )


LARGURA_NOME = 22
FORMATO_TABELA = '{:>3}  {:<22} {:>3} {:>3} {:>3} {:>3} {:>3} {:>3} {:>3} {:>4}'


def exibir_menu(ano):
    print()
    print('=' * 60)
    print('              CHECKPOINT 5 | BRASILEIRÃO')
    print('=' * 60)
    print(f'  Temporada selecionada: {ano}')
    print('-' * 60)
    print('  1 - Navegar pelas rodadas')
    print('  2 - Ver uma rodada específica')
    print('  3 - Buscar partidas por time')
    print('  4 - Ver classificação')
    print('  5 - Trocar temporada')
    print('  0 - Sair')
    print('-' * 60)


def ler_ano():
    ano_atual = date.today().year
    while True:
        try:
            ano = int(input('Digite o ano da temporada: '))
        except ValueError:
            print('Digite um ano válido.')
            continue

        if 2000 <= ano <= ano_atual:
            return ano
        print(f'Digite um ano entre 2000 e {ano_atual}.')


def agrupar_rodadas(partidas):
    # Cada rodada tem (número de times / 2) jogos. As partidas já chegam
    # ordenadas por data, então cada bloco de jogos forma uma rodada.
    times = set()
    for partida in partidas:
        times.add(partida[0])
        times.add(partida[2])

    jogos_por_rodada = max(1, len(times) // 2)
    rodadas = {}

    for indice, partida in enumerate(partidas):
        numero = indice // jogos_por_rodada + 1
        rodadas.setdefault(numero, []).append(partida)

    return rodadas


def formatar_data(valor):
    if not valor:
        return '--/--/----'
    try:
        ano, mes, dia = str(valor).split('T')[0].split('-')
        return f'{dia}/{mes}/{ano}'
    except ValueError:
        return str(valor)[:10]


def cabecalho_partidas():
    return f"{'Data':<10}  {'Mandante':>{LARGURA_NOME}}  {'Placar':^7}  {'Visitante':<{LARGURA_NOME}}"


def formatar_partida(partida):
    data = formatar_data(partida[4])
    mandante = partida[0][:LARGURA_NOME]
    visitante = partida[2][:LARGURA_NOME]
    placar = f'{partida[1]} x {partida[3]}'
    return f'{data}  {mandante:>{LARGURA_NOME}}  {placar:^7}  {visitante:<{LARGURA_NOME}}'


def exibir_rodada(numero, jogos, total_rodadas):
    cabecalho = cabecalho_partidas()
    print()
    print(f' RODADA {numero} de {total_rodadas} '.center(len(cabecalho), '='))
    print(cabecalho)
    print('-' * len(cabecalho))
    for partida in jogos:
        print(formatar_partida(partida))
    print('-' * len(cabecalho))


def exibir_partidas(ano):
    partidas = banco.consultar_partidas(ano)
    if partidas is None:
        return
    if not partidas:
        print(f'Não há partidas salvas para {ano}.')
        return

    rodadas = agrupar_rodadas(partidas)
    ultima = max(rodadas)
    atual = 1

    while True:
        exibir_rodada(atual, rodadas[atual], ultima)
        comando = input('[Enter] próxima | [p] anterior | [número] ir para a rodada | [s] sair: ').strip().lower()

        if comando in ('', 'n'):
            if atual < ultima:
                atual += 1
            else:
                print('Você já está na última rodada.')
        elif comando == 'p':
            if atual > 1:
                atual -= 1
            else:
                print('Você já está na primeira rodada.')
        elif comando == 's':
            break
        elif comando.isdigit() and int(comando) in rodadas:
            atual = int(comando)
        else:
            print(f'Comando inválido. Digite uma rodada entre 1 e {ultima}.')


def exibir_rodada_especifica(ano):
    partidas = banco.consultar_partidas(ano)
    if partidas is None:
        return
    if not partidas:
        print(f'Não há partidas salvas para {ano}.')
        return

    rodadas = agrupar_rodadas(partidas)
    ultima = max(rodadas)

    try:
        numero = int(input(f'Digite o número da rodada (1 a {ultima}): '))
    except ValueError:
        print('Digite um número válido.')
        return

    if numero not in rodadas:
        print(f'Rodada inválida. Escolha entre 1 e {ultima}.')
        return

    exibir_rodada(numero, rodadas[numero], ultima)


def exibir_partidas_por_time(ano):
    partidas = banco.consultar_partidas(ano)
    if partidas is None:
        return
    if not partidas:
        print(f'Não há partidas salvas para {ano}.')
        return

    time = input('Digite o nome do time: ').strip().casefold()
    if not time:
        print('Digite o nome de um time.')
        return

    rodadas = agrupar_rodadas(partidas)
    encontrou = False

    for numero, jogos in rodadas.items():
        for partida in jogos:
            if time in partida[0].casefold() or time in partida[2].casefold():
                if not encontrou:
                    print()
                    print('Rod ' + cabecalho_partidas())
                    print('-' * (4 + len(cabecalho_partidas())))
                    encontrou = True
                print(f'{numero:<3} {formatar_partida(partida)}')

    if not encontrou:
        print('Nenhuma partida encontrada para esse time.')


def exibir_classificacao(ano):
    classificacao = gerar_classificacao(ano)
    if classificacao is None:
        return
    if not classificacao:
        print(f'Não há partidas salvas para {ano}.')
        return

    print()
    print(f'CLASSIFICAÇÃO DO BRASILEIRÃO {ano}')
    cabecalho = FORMATO_TABELA.format('Pos', 'Equipe', 'P', 'J', 'V', 'E', 'D', 'GP', 'GC', 'SG')
    print(cabecalho)
    print('-' * len(cabecalho))
    for posicao, equipe in enumerate(classificacao, start=1):
        print(FORMATO_TABELA.format(
            posicao, equipe['equipe'][:LARGURA_NOME],
            equipe['pontos'], equipe['jogos'], equipe['vitorias'],
            equipe['empates'], equipe['derrotas'], equipe['gols_marcados'],
            equipe['gols_sofridos'], equipe['saldo_gols'],
        ))


def main():
    if not banco.criar_tabela():
        return

    ano = ler_ano()
    importar_brasileirao(ano)

    while True:
        exibir_menu(ano)
        opcao = input('Escolha uma opção: ').strip()

        if opcao == '1':
            exibir_partidas(ano)
        elif opcao == '2':
            exibir_rodada_especifica(ano)
        elif opcao == '3':
            exibir_partidas_por_time(ano)
        elif opcao == '4':
            exibir_classificacao(ano)
        elif opcao == '5':
            ano = ler_ano()
            importar_brasileirao(ano)
        elif opcao == '0':
            print('Programa encerrado.')
            break
        else:
            print('Opção inválida. Tente novamente.')


if __name__ == '__main__':
    main()