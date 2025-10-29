import requests
import os

def api(metodo, query):
    try:
        dados_api = os.environ.get('API')
        url, usuario, senha = dados_api.split(';')
        auth = (usuario, senha)
    except:
        print('Erro ao obter as credenciais da API')
        return None

    headers = {'Content-Type': 'application/json'}
    payload = {'query': query}
    if metodo == 'GET':
        url = f"{url}/consulta"
        response = requests.get(url, headers=headers, auth=auth, json=payload)
    elif metodo == 'POST':
        url = f"{url}/executar"
        response = requests.post(url, headers=headers, auth=auth, json=payload)
    else:
        return None

    if response.status_code == 200:
        return response.json()
    else:
        return response.raise_for_status()
    