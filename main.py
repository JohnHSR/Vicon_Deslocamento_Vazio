import sessions as s
from variaveis import TELEGRAM_TOKEN
from api import api
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import time
import re, os, shutil
import ROTAS.geo2 as geo2

"""
Exemplo do TELEGRAM_TOKEN

TELEGRAM_TOKEN = "NI71H2D812BD918HS2H0S12HS12H"
"""

confirmacao = ["sim", "s",]
negacao = ["não", "n", "nao"]

bot = TeleBot(TELEGRAM_TOKEN)

## Debug mode permite que apenas administradores possam iniciar uma sessão, útil para testes e desenvolvimento
DEBUG_MODE = False
TEMPO_SESSAO = timedelta(minutes=2)

## Função que capta qualquer mensagem e trata conforme a sessão do usuário
@bot.message_handler(func=lambda message: True)
def handle_message(message):

    ## Coletar os dados do usuário como ID, nome e sessão
    id_usuario = message.from_user.id
    nome_usuario = message.from_user.first_name
    sessao = s.get_sessao(id_usuario)
    mensagem = message.text.strip().lower()

    #s.atualizar_sessao(id_usuario, "ultima_atividade", datetime.now())

    ## Caso o usuário não tenha permissão (Não esteja na lista de usuários)
    if sessao == "Sem Permissão":
        bot.send_message(id_usuario, "Você não tem permissão para acessar este bot.")
        bot.send_message(id_usuario, "Por favor, informe o seu ID de usuário a um administrador.")
        bot.send_message(id_usuario, f"Seu ID de usuário é: {id_usuario}")
        return
    
    ## Caso o usuário tenha permissão, mas não tenha uma sessão ativa
    elif sessao is None:

        ## Verifica se o DEBUG_MODE está ativo, caso sim, apenas administradores podem iniciar uma sessão
        ## O Debug Mode é usado para testes e desenvolvimento
        usuario = s.usuarios.get(id_usuario)
        perm_lvl = usuario["perm_lvl"] if usuario else "user"
        if DEBUG_MODE and perm_lvl != "admin":
            return
        
        ## Inicia uma nova sessão para o usuário e envia uma mensagem de boas-vindas
        s.nova_sessao(id_usuario)
        sessao = s.get_sessao(id_usuario)
        user_perm = s.usuarios.get(id_usuario, {}).get("perm_lvl", "user")
        print(f"Usuário {nome_usuario} iniciou uma nova sessão.")

        hora_dia = "Bom dia" if datetime.now().hour >= 5 and datetime.now().hour < 12 else \
                   "Boa tarde" if datetime.now().hour >= 12 and datetime.now().hour < 18 else \
                   "Boa noite"
        
        bot.send_message(id_usuario, f"{hora_dia}, {nome_usuario}! \nVamos iniciar este deslocamento.")
        bot.send_message(id_usuario, "Digite Sair a qualquer momento para encerrar a sessão.")
        bot.send_message(id_usuario, "Por favor, informe a placa do veículo.")
        s.atualizar_sessao(id_usuario, "passo", "informando_placa")

    else:
        if mensagem == 'sair':
            s.limpar_sessao(id_usuario)
            bot.send_message(id_usuario, "Sessão encerrada. Até logo.")
            return

        passo = sessao["passo"]
        funcao = globals().get(passo, None)

        if callable(funcao):
            funcao(id_usuario, message, sessao)
        else:
            bot.send_message(id_usuario, "Erro: Passo desconhecido ou não implementado.")
            s.limpar_sessao(id_usuario)

## Função que trata os callbacks dos botões inline
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    id_usuario = call.from_user.id
    sessao = s.get_sessao(id_usuario)

    s.atualizar_sessao(id_usuario, "ultima_atividade", datetime.now())


    if sessao is None:
        bot.answer_callback_query(call.id, "Sessão não encontrada. Por favor, inicie uma nova sessão.")
        return

    passo = sessao["passo"]
    funcao = globals().get(passo, None)

    if callable(funcao):
        funcao(id_usuario, call, sessao, call)
    else:
        bot.answer_callback_query(call.id, "Erro: Passo desconhecido ou não implementado.")
        s.limpar_sessao(id_usuario)

## Função que coloca o usuário em um estado de espera, para evitar que ele envie mensagens enquanto o bot está processando uma ação ou aguardando uma resposta.
def aguardando(id_usuario, retorno, sessao, call=None):
    bot.send_message(id_usuario, "Por favor, aguarde.")
    return

## Função para tratar o retorno da placa do veículo e demais consultas
def informando_placa(id_usuario, message, sessao, call=None):
    s.atualizar_sessao(id_usuario, "passo", "aguardando")

    # Verifica se o message é um callback
    if call:
        pass
    ## Definição da placa em letras maiúsculas.
    placa_deslocamento = message.text.upper()

    ## Validar a placa sem traços, e formatos: AAA1A11, AAA1111
    validar_placa = re.match(r'^[A-Z]{3}[0-9]{1}[A-Z]{1}[0-9]{2}$|^[A-Z]{3}[0-9]{4}$', placa_deslocamento)
    if not validar_placa:
        bot.send_message(id_usuario, "Placa inválida. Por favor, informe uma nos formatos XXX1A11 ou XXX1111.")
        s.atualizar_sessao(id_usuario, "passo", "informando_placa")
        return
    
    ## Consultar se a placa existe no sistema, caso exista, retorna alguns dados importantes, como situação do veículo, e motorista vinculado
    bot.send_message(id_usuario, "Consultando veículo...")
    try:
        consulta_placa = api("GET", F"SELECT SITUAC, ISNULL(CODMOT, 0) AS CODMOT, ULTKMT, PLACA2 FROM RODVEI WHERE CODVEI = '{placa_deslocamento}'")
    except:
        print("Erro ao consultar a placa no sistema.")
        bot.send_message(id_usuario, "Erro ao consultar a placa no sistema. Por favor, tente novamente mais tarde.")
        consulta_placa = None

    ## Caso a placa não exista no sistema, retorna uma mensagem de erro
    if len(consulta_placa) == 0:
        bot.send_message(id_usuario, "Placa não encontrada no sistema. Por favor, verifique a placa e tente novamente.")
        s.atualizar_sessao(id_usuario, "passo", "informando_placa")
        return
    
    ## Caso a placa exista, coleta os dados do veículo e motorista vinculado
    situacao_veiculo = consulta_placa[0]['SITUAC']
    cod_motorista = consulta_placa[0]['CODMOT']
    km_veiculo = consulta_placa[0]['ULTKMT']
    placa_carreta = consulta_placa[0]['PLACA2']

    ## Verifica se o veículo possui quilometragem registrada, caso não possua, define como 0
    try:
        km_veiculo = int(km_veiculo)
    except:
        km_veiculo = 0

    ## Verifica se o veículo está ativo no sistema, caso não esteja, retorna uma mensagem de erro
    if situacao_veiculo != "1":
        bot.send_message(id_usuario, "Veículo não está ativo no sistema. Por favor, verifique a situação do veículo.")
        return
    
    ## Consulta o último destino do veículo, no sistema
    consulta_ultimo_destino_veiculo = api("GET", F"""SELECT TOP 1 REPLACE(ISNULL(VIAVAZ, ''), '', LINVIA) AS LINVIA 
                                                    FROM RODHOP WHERE CODVEI = '{placa_deslocamento}' AND 
                                                    TIPDOC <> 'CAN' 
                                                    ORDER BY DATREF DESC""")
    
    if not consulta_ultimo_destino_veiculo or consulta_ultimo_destino_veiculo[0]['LINVIA'] is None:
        s.atualizar_sessao(id_usuario, "dados", {"ultimo_destino": None})
    else:
        ultimo_destino = consulta_ultimo_destino_veiculo[0]['LINVIA']
        ultimo_destino = ultimo_destino[-3:]

        consulta_destino = api("GET", F"SELECT CODMUN, DESCRI, ESTADO FROM RODMUN WHERE CODITN = '{ultimo_destino}'")[0]

        cod_municipio = consulta_destino['CODMUN']
        nome_municipio = consulta_destino['DESCRI'].capitalize()
        estado_municipio = consulta_destino['ESTADO'].upper()

        s.atualizar_sessao(id_usuario, "dados", {"ultimo_destino": {"codigo": cod_municipio, "cidade": nome_municipio, "estado": estado_municipio}})
        bot.send_message(id_usuario, f"Último destino do veículo:\n {nome_municipio} - {estado_municipio}")


    
    if cod_motorista == 0:
        bot.send_message(id_usuario, "Veículo não está vinculado a um motorista. Digite o nome do motorista que deseja buscar.")
        s.atualizar_sessao(id_usuario, "passo", "buscar_motorista")
        s.atualizar_sessao(id_usuario, "dados", {"placa": placa_deslocamento})
        s.atualizar_sessao(id_usuario, "dados", {"km_veiculo": km_veiculo})
        s.atualizar_sessao(id_usuario, "dados", {"placa_carreta": placa_carreta})
        return
    consulta_nome_motorista = api("GET", F"SELECT NOMMOT, SITUAC FROM RODMOT WHERE CODMOT = {cod_motorista}")
    if not consulta_nome_motorista:
        bot.send_message(id_usuario, "Motorista não encontrado no sistema. Por favor, verifique a situação do motorista.")
        return
    
    consulta_nome_motorista = consulta_nome_motorista[0]
    nome_motorista = consulta_nome_motorista['NOMMOT']
    situacao_motorista = consulta_nome_motorista['SITUAC']

    if situacao_motorista != "A":
        bot.send_message(id_usuario, "Motorista não está ativo no sistema. Por favor, verifique a situação do motorista.")
        return
    
    ## Consulta se deseja continuar com o motorista vinculado
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Sim", callback_data="Sim"),
               InlineKeyboardButton("Não", callback_data="Não"))
    bot.send_message(id_usuario, f"O motorista vinculado é: \n{nome_motorista}. \nDeseja continuar com este motorista?", reply_markup=markup)
    s.atualizar_sessao(id_usuario, "dados", {"placa": placa_deslocamento, "motorista": {"nome": nome_motorista, "codigo": cod_motorista}})
    s.atualizar_sessao(id_usuario, "dados", {"km_veiculo": km_veiculo})
    s.atualizar_sessao(id_usuario, "dados", {"placa_carreta": placa_carreta})
    s.atualizar_sessao(id_usuario, "passo", "confirmar_motorista")

## Função que confirma o motorista vinculado ao veículo, ou busca um novo motorista
def confirmar_motorista(id_usuario, retorno, sessao, call=None):
    resposta = None
    if call:
        resposta = call.data
    else:
        resposta = retorno.text

    if resposta.lower() in confirmacao:
        
        bot.send_message(id_usuario, "Motorista confirmado. \nAgora me diga a cidade de ORIGEM do deslocamento.")
        s.atualizar_sessao(id_usuario, "passo", "informar_origem")

    elif resposta.lower() in negacao:
        bot.send_message(id_usuario, """Por favor, digite o nome do motorista que deseja buscar.
(Lembrando que esta busca só retorna motoristas ativos no sistema)""")
        s.atualizar_sessao(id_usuario, "passo", "buscar_motorista")
    
    else:
        bot.send_message(id_usuario, "Resposta inválida. Por favor, responda com 'Sim' ou 'Não'.")
    
    return

## Função que busca um motorista pelo nome informado pelo usuário
def buscar_motorista(id_usuario, message, sessao, call=None):

    # Verifica se o message é um callback
    if call:
        pass
    
    nome_motorista = message.text.upper()

    consulta_motorista = api("GET", F"SELECT CODMOT, NOMMOT FROM RODMOT WHERE NOMMOT LIKE '%{nome_motorista}%' AND SITUAC = 'A'")
    if not consulta_motorista:
        bot.send_message(id_usuario, "Nenhum motorista encontrado com esse nome. Por favor, tente novamente.")
        return
    
    if len(consulta_motorista) > 1:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Buscar novamente", callback_data="buscar_novo_motorista"))
        for motorista in consulta_motorista:
            codigo = motorista['CODMOT']
            nome = motorista['NOMMOT'].capitalize()
            string = f"{codigo} - {nome}"
            markup.add(InlineKeyboardButton(string, callback_data=f"codmot:{codigo}"))
        bot.send_message(id_usuario, "Mais de um motorista encontrado. Por favor, selecione o motorista desejado.", reply_markup=markup)
    else:
        cod_motorista = consulta_motorista[0]['CODMOT']
        nome_motorista = consulta_motorista[0]['NOMMOT']
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Sim", callback_data=f"codmot:{cod_motorista}"),
                   InlineKeyboardButton("Não", callback_data="buscar_novo_motorista"))
        bot.send_message(id_usuario, f"Confirma o motorista: {nome_motorista}?", reply_markup=markup)
    s.atualizar_sessao(id_usuario, "passo", "confirmar_motorista_busca")

## Função que solicita a confirmação do motorista buscado, ou busca um novo motorista caso o usuário deseje
def confirmar_motorista_busca(id_usuario, retorno, sessao, call=None):
    resposta = None
    if call:
        resposta = call.data
    else:
        resposta = retorno.text

    if resposta.startswith("codmot:"):
        cod_motorista = int(resposta.split(":")[1])
        consulta_motorista = api("GET", F"SELECT NOMMOT FROM RODMOT WHERE CODMOT = {cod_motorista} AND SITUAC = 'A'")
        
        if not consulta_motorista:
            bot.send_message(id_usuario, "Motorista não encontrado. Por favor, tente novamente.")
            return
        
        nome_motorista = consulta_motorista[0]['NOMMOT'].capitalize()
        s.atualizar_sessao(id_usuario, "dados", {"motorista": {"nome": nome_motorista, "codigo": cod_motorista}})
        bot.send_message(id_usuario, f"{nome_motorista}. Agora me diga a cidade de ORIGEM do deslocamento.")
        s.atualizar_sessao(id_usuario, "passo", "informar_origem")
    
    elif resposta == "buscar_novo_motorista":
        bot.send_message(id_usuario, "Digite o nome do motorista que deseja buscar.")
        s.atualizar_sessao(id_usuario, "passo", "buscar_motorista")
    
    else:
        bot.send_message(id_usuario, "Resposta inválida. Por favor, utilize os botões.")

## Função para tratar e consultar a cidade de origem do deslocamento digitada pelo usuário
def informar_origem(id_usuario, message, sessao, call=None):
    
    # Verifica se o message é um callback
    if call:
        pass

    cidade_origem = message.text.upper()

    if not cidade_origem or len(cidade_origem) < 3:
        bot.send_message(id_usuario, "Cidade de origem inválida. Por favor, informe uma cidade válida.")
        return
    
    consulta_origem = api("GET", F"SELECT CODMUN, DESCRI, ESTADO FROM RODMUN WHERE DESCRI LIKE '%{cidade_origem}%'")
    if not consulta_origem:
        bot.send_message(id_usuario, "Cidade de origem não encontrada no sistema. Por favor, verifique a cidade e tente novamente.")
        return
    
    if len(consulta_origem) > 1:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Buscar novamente", callback_data="buscar_nova_origem"))
        for cidade in consulta_origem:
            cod_origem = cidade['CODMUN']
            nome_cidade = cidade['DESCRI'].capitalize()
            estado = cidade['ESTADO']
            string = f"{nome_cidade} - {estado}"
            markup.add(InlineKeyboardButton(string, callback_data=f"codmun:{cod_origem}"))
        bot.send_message(id_usuario, "Mais de uma cidade encontrada. \n Por favor, selecione a cidade desejada.", reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_origem")
    else:
        cod_origem = consulta_origem[0]['CODMUN']
        nome_origem = consulta_origem[0]['DESCRI'].capitalize()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Sim", callback_data=f"codmun:{cod_origem}"),
                   InlineKeyboardButton("Não", callback_data="buscar_nova_origem"))
        bot.send_message(id_usuario, f"Confirma a cidade de origem: \n {nome_origem} - {consulta_origem[0]['ESTADO']}?", reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_origem")
        s.atualizar_sessao(id_usuario, "dados", {"origem": {"cidade": consulta_origem[0]['DESCRI'], "codigo": cod_origem}})

## Função que confirma a cidade de origem do deslocamento, ou busca uma nova origem caso o usuário deseje
def confirmar_origem(id_usuario, retorno, sessao, call=None):
    if call:
        resposta = call.data
    else:
        resposta = retorno.text

    
    if resposta.startswith("codmun:"):
        cod_origem = int(resposta.split(":")[1])
        consulta_municipio = api("GET", F"SELECT DESCRI, ESTADO, CODITN FROM RODMUN WHERE CODMUN = {cod_origem}")

        if not consulta_municipio:
            bot.send_message(id_usuario, "Cidade de origem não encontrada. Por favor, tente novamente.")
            return

        nome_cidade = consulta_municipio[0]['DESCRI'].capitalize()
        estado = consulta_municipio[0]['ESTADO']
        cod_itinerario = consulta_municipio[0]['CODITN']

        ## Validar a origem com o ultimo destino
        ultimo_destino = sessao["dados"].get("ultimo_destino", None)

        ## Permissão do usuario
        user_perm = s.usuarios.get(id_usuario, {}).get("perm_lvl", "user")

        if ultimo_destino is not None:
            ultimo_codigo = ultimo_destino["codigo"]
            s.atualizar_sessao(id_usuario, "dados", {"ultimo_destino": ultimo_destino})
            if user_perm == 'user' and cod_origem != ultimo_codigo:
                bot.send_message(id_usuario, "A origem não pode ser diferente do último destino do veículo.")
                s.atualizar_sessao(id_usuario, "passo", "informar_origem")
                return


        s.atualizar_sessao(id_usuario, "dados", {"origem": {"cidade": nome_cidade, "codigo": cod_origem, "estado": estado, "itinerario": cod_itinerario}})
        bot.send_message(id_usuario, "Agora me diga a cidade de DESTINO do deslocamento.")
        s.atualizar_sessao(id_usuario, "passo", "informar_destino")

    elif resposta == "buscar_nova_origem":
        bot.send_message(id_usuario, "Digite o nome da nova cidade de origem.")
        s.atualizar_sessao(id_usuario, "passo", "informar_origem")

    else:
        bot.send_message(id_usuario, "Resposta inválida.")

## Função que trata a cidade de destino do deslocamento digitada pelo usuário
def informar_destino(id_usuario, message, sessao, call=None):

    # Verifica se o message é um callback
    if call:
        pass

    cidade_destino = message.text.upper()

    if not cidade_destino or len(cidade_destino) < 3:
        bot.send_message(id_usuario, "Cidade de destino inválida. Por favor, informe uma cidade válida.")
        return
    
    consulta_destino = api("GET", F"SELECT CODMUN, DESCRI, ESTADO FROM RODMUN WHERE DESCRI LIKE '%{cidade_destino}%'")
    if not consulta_destino:
        bot.send_message(id_usuario, "Cidade de destino não encontrada no sistema. Por favor, verifique a cidade e tente novamente.")
        return
    
    if len(consulta_destino) > 1:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Buscar novamente", callback_data="buscar_novo_destino"))
        for cidade in consulta_destino:
            cod_destino = cidade['CODMUN']
            nome_cidade = cidade['DESCRI'].capitalize()
            estado = cidade['ESTADO']
            string = f"{nome_cidade} - {estado}"
            markup.add(InlineKeyboardButton(string, callback_data=f"codmun:{cod_destino}"))
        bot.send_message(id_usuario, "Mais de uma cidade encontrada. Por favor, selecione a cidade desejada.", reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_destino")
    else:
        cod_destino = consulta_destino[0]['CODMUN']
        nome_destino = consulta_destino[0]['DESCRI'].capitalize()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Sim", callback_data=f"codmun:{cod_destino}"),
                   InlineKeyboardButton("Não", callback_data="buscar_novo_destino"))
        bot.send_message(id_usuario, f"Confirma a cidade de destino: \n {nome_destino} - {consulta_destino[0]['ESTADO']}?", reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_destino")
        s.atualizar_sessao(id_usuario, "dados", {"destino": {"cidade": consulta_destino[0]['DESCRI'], "codigo": cod_destino}})

## Função que confirma a cidade de destino do deslocamento, ou busca uma nova origem caso o usuário deseje
def confirmar_destino(id_usuario, retorno, sessao, call=None):
    if retorno.data.startswith("codmun:"):

        s.atualizar_sessao(id_usuario, "passo", "aguardando")

        cod_destino = int(retorno.data.split(":")[1])
        consulta_destino = api("GET", F"SELECT DESCRI, ESTADO, CODITN FROM RODMUN WHERE CODMUN = {cod_destino}")

        if not consulta_destino:
            bot.send_message(id_usuario, "Cidade de destino não encontrada. Por favor, tente novamente.")
            s.atualizar_sessao(id_usuario, "passo", "informar_destino")
            return

        nome_destino = consulta_destino[0]['DESCRI'].capitalize()
        estado = consulta_destino[0]['ESTADO']
        cod_itinerario = consulta_destino[0]['CODITN']

        s.atualizar_sessao(id_usuario, "dados", {"destino": {"cidade": nome_destino, "codigo": cod_destino, "estado": estado, "itinerario": cod_itinerario}})
        bot.send_message(id_usuario, f"Um momento...")

        dados = sessao["dados"]
        placa = dados["placa"]
        motorista = dados["motorista"]["nome"]
        origem = dados["origem"]["cidade"]
        estado_origem = dados["origem"]["estado"]
        itn_origem = dados["origem"]["itinerario"]
        destino = dados["destino"]["cidade"]
        estado_destino = dados["destino"]["estado"]
        itn_destino = dados["destino"]["itinerario"]
        nome_usuario = s.usuarios.get(id_usuario, {}).get("nome", f"{id_usuario}")

        cidade_origem = f"{origem} - {estado_origem}"
        cidade_destino = f"{destino} - {estado_destino}"

        consultar_linha = f"SELECT CODLIN FROM RODLIN WHERE PONINI = '{itn_origem}' AND PONFIM = '{itn_destino}'"
        linha = api("GET", consultar_linha)

        if not linha:
            
            try:
                km_rota = geo2.gerar_rota_km(cidade_origem, cidade_destino)
                km_rota = int(km_rota)
            except Exception as e:
                km_rota = 0

            codlinha = f"{itn_origem}{itn_destino}"
            ## Verifica se a linha já existe no sistema
            verificar_linha = api("GET", f"SELECT CODLIN FROM RODLIN WHERE CODLIN = '{codlinha}'")

            while len(verificar_linha) > 0:
                # Muda uma letra da linha por 1
                import random
                codlinha = f"{codlinha[:-1]}{random.randint(1, 9)}"
                verificar_linha = api("GET", f"SELECT CODLIN FROM RODLIN WHERE CODLIN = '{codlinha}'")

            query_inserir_linha = f"""
            EXEC SP_INS_RODLIN
                @CODLIN = '{codlinha}',
                @ITN_ORIG = '{itn_origem}',
                @ITN_DEST = '{itn_destino}',
                @KM_ROTA = {km_rota},
                @NOME_USUARIO = '{nome_usuario}'
            """

            try:
                resultado = api("POST", query_inserir_linha)
            except Exception as e:
                bot.send_message(id_usuario, "Erro ao inserir a linha no sistema. Por favor, tente novamente mais tarde.")
                bot.send_message(id_usuario, "Sessão encerrada.")
                s.limpar_sessao(id_usuario)
                return

            ### Cadastrar código horário

            query_inserir_codigo_horario = f"""
            EXEC SP_INS_RODHOR
                @CODLIN = '{codlinha}',
                @ORIGEM_DESTINO = "Horário de {origem} - {destino}",
                @KM_ROTA = {km_rota},
                @NOME_USUARIO = '{nome_usuario}'
            """
            try:
                resultado = api("POST", query_inserir_codigo_horario)
            except Exception as e:
                bot.send_message(id_usuario, "Erro ao inserir o código de horário no sistema. Por favor, tente novamente mais tarde.")
                bot.send_message(id_usuario, "Sessão encerrada.")
                s.limpar_sessao(id_usuario)
                return
            
            consultar_linha = f"SELECT CODLIN FROM RODLIN WHERE PONINI = '{itn_origem}' AND PONFIM = '{itn_destino}'"
            linha = api("GET", consultar_linha)
            linha = linha[0]['CODLIN']
            s.atualizar_sessao(id_usuario, "dados", {"linha": linha})

        else:
            linha = linha[0]['CODLIN']
            s.atualizar_sessao(id_usuario, "dados", {"linha": linha})


        ## Verifica se a linha já existe na pasta ROTAS
        if not os.path.exists(f"ROTAS/{linha}.png"):
            try:
                km_rota = geo2.gerar_rota_png(cidade_origem, cidade_destino, linha)
                os.remove(f"{linha}.html")
                shutil.move(f"{linha}.png", f"ROTAS/{linha}.png")
                s.atualizar_sessao(id_usuario, "dados", {"imagem_gerada": True})
            except Exception as e:
                print(e)
                s.atualizar_sessao(id_usuario, "dados", {"imagem_gerada": False})
                try:
                    km_rota = api("GET", f"SELECT KMTPLA FROM RODLIN WHERE CODLIN = '{linha}'")[0]['KMTPLA']
                except Exception as e:
                    try:
                        km_rota = geo2.gerar_rota_km(cidade_origem, cidade_destino)
                    except Exception as e:
                        print(km_rota)
                        print(e)
                        km_rota = 0
        else:
            try:
                km_rota = api("GET", f"SELECT KMTPLA FROM RODLIN WHERE CODLIN = '{linha}'")[0]['KMTPLA']
            except Exception as e:
                try:
                    km_rota = geo2.gerar_rota_km(cidade_origem, cidade_destino)
                except Exception as e:
                    print(km_rota)
                    print(e)
                    km_rota = 0
            s.atualizar_sessao(id_usuario, "dados", {"imagem_gerada": True})

        try:
            km_rota = int(km_rota)
        except Exception as e:
            km_rota = 0



        consulta_codigo_horario = api("GET", f"SELECT CODHOR FROM RODHOR WHERE CODLIN = '{linha}'")

        if not consulta_codigo_horario:
            bot.send_message(id_usuario, "Não foi possível encontrar um código de horário para a linha. Por favor, verifique a linha e tente novamente.")
            bot.send_message(id_usuario, "Sessão encerrada.")
            s.limpar_sessao(id_usuario)
            return

        codigo_horario = consulta_codigo_horario[0]['CODHOR']

        cod_cidade_origem = dados["origem"]["codigo"]
        cod_ultima_cidade = dados["ultimo_destino"]["codigo"] if dados.get("ultimo_destino") else cod_cidade_origem

        if cod_cidade_origem == cod_ultima_cidade:
            tipo_deslocamento = "Deslocamento Vazio"
        else:
            tipo_deslocamento = "Deslocamento Fictício"

        mensagem_confirmacao = (f"◾ {tipo_deslocamento}\n\n"
                                f"🚚 Placa: {placa}\n"
                                f"👤 Motorista: {motorista}\n"
                                f"🏙 Origem: {origem}-{estado_origem}\n"
                                f"🌆 Destino: {destino}-{estado_destino}\n"
                                f"📏 Distância: {km_rota} km\n\n"
                                "Confirma os dados do deslocamento?")

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Sim", callback_data="confirmar_deslocamento"),
                InlineKeyboardButton("Não", callback_data="cancelar_deslocamento"))
        
        imagem_gerada = sessao["dados"].get("imagem_gerada", False)

        if imagem_gerada:
            bot.send_photo(id_usuario, open(f"ROTAS/{linha}.png", "rb"), caption=mensagem_confirmacao, reply_markup=markup)
        else:
            bot.send_message(id_usuario, mensagem_confirmacao, reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "finalizar_deslocamento")
        s.atualizar_sessao(id_usuario, "dados", {"km_rota": km_rota})
        s.atualizar_sessao(id_usuario, "dados", {"codigo_horario": codigo_horario})

    else:
        bot.send_message(id_usuario, "Resposta inválida. Por favor, selecione uma cidade válida.")

## Função que finaliza o deslocamento, verificando se há manifesto em aberto para o veículo
def verificar_manifesto(id_usuario, sessao):
    dados = sessao["dados"]
    placa = dados["placa"]
    motorista = dados["motorista"]["codigo"]
    origem = dados["origem"]["codigo"]
    estado_origem = dados["origem"]["estado"]
    destino = dados["destino"]["codigo"]
    estado_destino = dados["destino"]["estado"]
    linha = dados["linha"]
    km_rota = dados["km_rota"]

    query_manifesto = f"""
    SELECT CODFIL, SERMAN, CODMAN FROM RODMAN WHERE PLACA = '{placa}' AND SITUAC NOT IN ('B', 'C')
    """
    manifestos = api("GET", query_manifesto)

    if len(manifestos) == 0:
        finalizar_deslocamento(id_usuario, retorno="Sem Manifesto", sessao=sessao)
        return

    elif len(manifestos) == 1:
        manifesto = manifestos[0]
        codigo_manifesto = manifesto['CODMAN']
        serie_manifesto = manifesto['SERMAN']
        filial_manifesto = manifesto['CODFIL']

        mensagem = f"""
Encontrei um manifesto em aberto:

Código do Manifesto: {codigo_manifesto}
Série do Manifesto: {serie_manifesto}
Filial do Manifesto: {filial_manifesto}

Deseja encerrar o manifesto para prosseguir com o deslocamento?
        """
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Sim", callback_data="confirmar_baixa_manifesto"),
                     InlineKeyboardButton("Não", callback_data="cancelar_deslocamento"))    
        bot.send_message(id_usuario, mensagem, reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_baixa_manifesto")
        s.atualizar_sessao(id_usuario, "dados", {"manifesto": {"codigo": codigo_manifesto, "serie": serie_manifesto, "filial": filial_manifesto}})
    
    else:
        bot.send_message(id_usuario, "Encontrei os seguintes manifestos em aberto:")
        markup = InlineKeyboardMarkup()
        mensagem = ""
        for manifesto in manifestos:
            mensagem += f"Manifesto: {manifesto['CODMAN']} - Série: {manifesto['SERMAN']} - Filial: {manifesto['CODFIL']}\n"

        markup.add(InlineKeyboardButton("Encerrar manifestos", callback_data="confirmar_baixa_manifesto"),
                     InlineKeyboardButton("Cancelar deslocamento", callback_data="cancelar_deslocamento"))
        bot.send_message(id_usuario, mensagem)
        bot.send_message(id_usuario, "Deseja encerrar os manifestos para prosseguir com o deslocamento?", reply_markup=markup)
        s.atualizar_sessao(id_usuario, "passo", "confirmar_baixa_manifesto")
        s.atualizar_sessao(id_usuario, "dados", {"manifestos": manifestos})

## Função que confirma a baixa do manifesto, encerrando-o no sistema e prosseguindo com o deslocamento
def confirmar_baixa_manifesto(id_usuario, retorno, sessao, call=None):
    

    if retorno.data == "confirmar_baixa_manifesto":
        nome_usuario = s.usuarios.get(id_usuario, {}).get("nome", f"{id_usuario}")


        ## Verifica se a chave é manifesto ou manifestos
        if "manifesto" in sessao["dados"]:
            manifesto = sessao["dados"]["manifesto"]
            codigo_manifesto = manifesto["codigo"]
            serie_manifesto = manifesto["serie"]
            filial_manifesto = manifesto["filial"]

            query_encerrar_manifesto = F"""
            EXEC SP_BAIXA_MANIFESTO
            @CODFIL = {filial_manifesto},
            @SERMAN = '{serie_manifesto}',
            @CODMAN = {codigo_manifesto},
            @NOME_USUARIO = '{nome_usuario}'
            """

            try:
                resultado = api("POST", query_encerrar_manifesto)
            except Exception as e:
                bot.send_message(id_usuario, f"Erro ao encerrar o manifesto {codigo_manifesto}: {e}")
                s.limpar_sessao(id_usuario)
                return

            bot.send_message(id_usuario, f"Manifesto encerrado com sucesso!")
            s.atualizar_sessao(id_usuario, "passo", "finalizar_deslocamento")
            finalizar_deslocamento(id_usuario, retorno="Sem Manifesto", sessao=sessao)
        
        elif "manifestos" in sessao["dados"]:
            manifestos = sessao["dados"]["manifestos"]
            for manifesto in manifestos:
                codigo_manifesto = manifesto['CODMAN']
                serie_manifesto = manifesto['SERMAN']
                filial_manifesto = manifesto['CODFIL']

                query_encerrar_manifesto = F"""
                EXEC SP_BAIXA_MANIFESTO
                @CODFIL = {filial_manifesto},
                @SERMAN = '{serie_manifesto}',
                @CODMAN = {codigo_manifesto},
                @NOME_USUARIO = '{nome_usuario}'
                """

                try:
                    resultado = api("POST", query_encerrar_manifesto)
                except Exception as e:
                    bot.send_message(id_usuario, f"Erro ao encerrar o manifesto {codigo_manifesto}: {e}")
                    s.limpar_sessao(id_usuario)
                    return

            bot.send_message(id_usuario, f"Manifestos encerrados com sucesso!")
            s.atualizar_sessao(id_usuario, "passo", "finalizar_deslocamento")
            finalizar_deslocamento(id_usuario, retorno="Sem Manifesto", sessao=sessao)
        else:
            bot.send_message(id_usuario, "Nenhum manifesto encontrado para encerrar.")
            finalizar_deslocamento(id_usuario, retorno="cancelar_deslocamento", sessao=sessao)

    elif retorno.data == "cancelar_deslocamento":
        bot.send_message(id_usuario, "Deslocamento cancelado. Você pode iniciar uma nova sessão a qualquer momento.")
        s.limpar_sessao(id_usuario)
    else:
        bot.send_message(id_usuario, "Resposta inválida. Por favor, responda com 'Sim' ou 'Não'.")

## Função que finaliza o deslocamento, registrando os dados no sistema e atualizando o status do veículo
def finalizar_deslocamento(id_usuario, retorno, sessao, call=None):
    s.atualizar_sessao(id_usuario, "passo", "aguardando")
    if (getattr(retorno, "data", None) == "confirmar_deslocamento") or (retorno == "Sem Manifesto"):
        
        ## Verifica se já foi validado o manifesto
        if retorno != "Sem Manifesto":
            verificar_manifesto(id_usuario, sessao)
            return

        dados = sessao["dados"]
        placa = dados["placa"]
        km_veiculo = dados["km_veiculo"]
        placa_carreta = dados["placa_carreta"]
        motorista = dados["motorista"]["codigo"]
        estado_destino = dados["destino"]["estado"]
        linha = dados["linha"]
        codigo_horario = dados["codigo_horario"]
        km_rota = dados["km_rota"]
        nome_usuario = s.usuarios.get(id_usuario, {}).get("nome", f"{id_usuario}")

        cod_cidade_origem = dados["origem"]["codigo"]
        cod_ultima_cidade = dados["ultimo_destino"]["codigo"] if dados.get("ultimo_destino") else cod_cidade_origem

        if cod_cidade_origem != cod_ultima_cidade:
            ficticio = 5
            tipo_deslocamento = "Deslocamento fictício"
        else:
            ficticio = 1
            tipo_deslocamento = "Deslocamento vazio"

        try:
            km_final_veiculo = int(km_veiculo) + int(km_rota)
        except:
            km_final_veiculo = km_veiculo
        
        try:
            tempo_estimado_chegada = (km_rota / 60) ** 60  # Tempo estimado em minutos. Considerando uma velocidade média de 60 km/h
            tempo_estimado_chegada = datetime.now() + timedelta(minutes=tempo_estimado_chegada)
            data_estimada_chegada = tempo_estimado_chegada.strftime("%Y-%m-%d %H:%M:%S")
        except:
            data_estimada_chegada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        ## SITUAC 'D' - CADASTRADO 'B' - BAIXADO 'C' - CANCELADO 'I' - INCONSISTENTE
        try:
            ultimo_deslocamento = api("POST", F"""
            EXEC SP_INS_DESLOCAMENTO_VAZIO
            @FICTICIO = {ficticio},
            @PLACA = '{placa}',
            @CODMOT = {motorista},
            @LINHA = '{linha}',
            @CODHOR = '{codigo_horario}',
            @KM_VEICULO = {km_veiculo},
            @KM_FINAL_VEICULO = {km_final_veiculo},
            @NOME_USUARIO = '{nome_usuario}',
            @DATCHE = '{data_estimada_chegada}',
            @KMROTA = {km_rota},
            @ESTADO_DESTINO = '{estado_destino}'
            """)
        except Exception as e:
            bot.send_message(id_usuario, f"Erro ao registrar deslocamento: {e}")
            s.limpar_sessao(id_usuario)
            return
        

        try:
            linhas_afetadas = ultimo_deslocamento['linhas_afetadas']
            if linhas_afetadas == 1:
                ultimo_deslocamento = api("GET", F"SELECT TOP 1 CODVAZ FROM RODVAZ WHERE CODVEI = '{placa}' ORDER BY DATINC DESC")[0]['CODVAZ']

                bot.send_message(id_usuario, f"""✅ {tipo_deslocamento} gerado!\nCódigo do Deslocamento: {ultimo_deslocamento}
                """)
        except Exception as e:
            bot.send_message(id_usuario, f"Erro ao registrar deslocamento: {e}")
            s.limpar_sessao(id_usuario)
            return
        ## Finaliza a sessão do usuário
        bot.send_message(id_usuario, "Sessão finalizada.")
        s.limpar_sessao(id_usuario)
        return

    elif retorno.data == "cancelar_deslocamento":
        bot.send_message(id_usuario, "Deslocamento cancelado. Sessão finalizada.")
        s.limpar_sessao(id_usuario)
    else:
        bot.send_message(id_usuario, "Resposta inválida. Por favor, responda com 'Sim' ou 'Não'.")

# Loop para manter o bot ativo
while True:
    try:
        #threading.Thread(target=limpa_sessoes_expiradas, daemon=True).start()
        bot.polling(non_stop=True, timeout=30, long_polling_timeout=5, skip_pending=True)
    except Exception as e:
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{datetime.now()} - Erro: {e}\n")
        time.sleep(5)  # Aguardar 5 segundos antes de reiniciar o bot