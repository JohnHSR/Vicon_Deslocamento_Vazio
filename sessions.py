from variaveis import usuarios
status_usuario = {}

"""
Exemplo de usuarios
usuarios = {
    123456789: {"nome": "JOHN", "perm_lvl": "admin", "status": "ativo"},
    987654321: {"nome": "JACKSON", "perm_lvl": "manager", "status": "ativo"},
    109876543: {"nome": "JOAOVICTOR", "perm_lvl": "user", "status": "ativo"},
}
"""

def get_sessao(usuario_id):
    if usuario_id not in usuarios:
        return "Sem Permissão"
    if usuario_id not in status_usuario:
        return None
    return status_usuario.setdefault(usuario_id, {"passo": None, "dados": {}})

def nova_sessao(usuario_id):
    status_usuario[usuario_id] = {"passo": None, "dados": {}}

def atualizar_sessao(usuario_id, campo, valor):
    # Garante que a sessão sempre exista
    if usuario_id not in status_usuario:
        nova_sessao(usuario_id)
    if campo == "dados":
        status_usuario[usuario_id]["dados"].update(valor)
    else:
        status_usuario[usuario_id][campo] = valor


def limpar_sessao(usuario_id):
    if usuario_id in status_usuario:
        nome_usuario = usuarios.get(usuario_id, {}).get("nome", "Desconhecido")
        print(f"Sessão finalizada para o usuário: {nome_usuario}")
        del status_usuario[usuario_id]
    else:
        return "Sessão não encontrada"
