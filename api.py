"""API REST da Loja Online.

Todas as rotas ficam sob /api e respondem em JSON. A autenticação usa a mesma
sessão (cookie) do site: faça POST /api/auth/login e reutilize o cookie.
"""
from functools import wraps

from flask import Blueprint, jsonify, request, session

from auth import (
    autenticar_cliente, buscar_cliente_por_id, buscar_produto_por_id,
    buscar_pedido_do_cliente, criar_cliente, criar_pedido, listar_pedidos_do_cliente,
    listar_produtos, EstoqueInsuficiente, ProdutoNaoEncontrado,
)

api = Blueprint('api', __name__, url_prefix='/api')


def erro(mensagem, status):
    return jsonify({'erro': mensagem}), status


def login_obrigatorio(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'cliente_id' not in session:
            return erro('Autenticação necessária.', 401)
        return f(*args, **kwargs)
    return wrapper


def corpo_json():
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else None


def ler_quantidade(valor):
    """Aceita apenas inteiros positivos (bool não conta como inteiro)."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        return None
    return valor


def carrinho_sessao():
    if 'carrinho' not in session:
        session['carrinho'] = {}
    return session['carrinho']


def carrinho_detalhado():
    itens, total = [], 0.0
    for pid, qtd in carrinho_sessao().items():
        produto = buscar_produto_por_id(int(pid))
        if produto is None:
            continue
        subtotal = round(produto['preco'] * qtd, 2)
        itens.append({
            'produto_id': produto['id'],
            'nome': produto['nome'],
            'preco_unitario': produto['preco'],
            'quantidade': qtd,
            'subtotal': subtotal,
        })
        total += subtotal
    return {'itens': itens, 'total': round(total, 2)}


# ---------------------------------------------------------------- Produtos

@api.get('/produtos')
def api_listar_produtos():
    produtos = listar_produtos()
    busca = request.args.get('busca', '').strip().lower()
    if busca:
        produtos = [p for p in produtos if busca in p['nome'].lower()]
    return jsonify(produtos)


@api.get('/produtos/<int:produto_id>')
def api_detalhar_produto(produto_id):
    produto = buscar_produto_por_id(produto_id)
    if produto is None:
        return erro('Produto não encontrado.', 404)
    return jsonify(produto)


# ---------------------------------------------------------------- Autenticação

@api.post('/auth/registrar')
def api_registrar():
    dados = corpo_json()
    if dados is None:
        return erro('Envie um JSON no corpo da requisição.', 400)
    nome, email, senha = dados.get('nome'), dados.get('email'), dados.get('senha')
    if not nome or not email or not senha:
        return erro('Campos obrigatórios: nome, email, senha.', 400)
    if len(senha) < 6:
        return erro('A senha deve ter pelo menos 6 caracteres.', 400)
    if not criar_cliente(nome, email, senha, dados.get('telefone')):
        return erro('Email já cadastrado.', 409)
    return jsonify({'mensagem': 'Cliente cadastrado com sucesso.'}), 201


@api.post('/auth/login')
def api_login():
    dados = corpo_json()
    if dados is None or not dados.get('email') or not dados.get('senha'):
        return erro('Campos obrigatórios: email, senha.', 400)
    cliente = autenticar_cliente(dados['email'], dados['senha'])
    if cliente is None:
        return erro('Email ou senha incorretos.', 401)
    session['cliente_id'] = cliente['id']
    session['cliente_nome'] = cliente['nome']
    session['cliente_email'] = cliente['email']
    return jsonify(cliente)


@api.post('/auth/logout')
def api_logout():
    session.clear()
    return '', 204


@api.get('/auth/me')
@login_obrigatorio
def api_me():
    return jsonify(buscar_cliente_por_id(session['cliente_id']))


# ---------------------------------------------------------------- Carrinho

@api.get('/carrinho')
@login_obrigatorio
def api_ver_carrinho():
    return jsonify(carrinho_detalhado())


@api.post('/carrinho/itens')
@login_obrigatorio
def api_adicionar_item():
    dados = corpo_json()
    if dados is None:
        return erro('Envie um JSON no corpo da requisição.', 400)
    produto_id = dados.get('produto_id')
    qtd = ler_quantidade(dados.get('quantidade', 1))
    if not isinstance(produto_id, int) or isinstance(produto_id, bool):
        return erro('produto_id deve ser um número inteiro.', 400)
    if qtd is None:
        return erro('quantidade deve ser um inteiro maior que zero.', 400)
    produto = buscar_produto_por_id(produto_id)
    if produto is None:
        return erro('Produto não encontrado.', 404)

    carrinho = carrinho_sessao()
    nova_qtd = carrinho.get(str(produto_id), 0) + qtd
    if nova_qtd > produto['estoque']:
        return erro(f"Estoque insuficiente para {produto['nome']}.", 409)
    carrinho[str(produto_id)] = nova_qtd
    session.modified = True
    return jsonify(carrinho_detalhado()), 201


@api.patch('/carrinho/itens/<int:produto_id>')
@login_obrigatorio
def api_atualizar_item(produto_id):
    dados = corpo_json()
    carrinho = carrinho_sessao()
    if str(produto_id) not in carrinho:
        return erro('Produto não está no carrinho.', 404)
    qtd = ler_quantidade(dados.get('quantidade') if dados else None)
    if qtd is None:
        return erro('quantidade deve ser um inteiro maior que zero.', 400)
    produto = buscar_produto_por_id(produto_id)
    if produto is None or qtd > produto['estoque']:
        return erro('Estoque insuficiente.', 409)
    carrinho[str(produto_id)] = qtd
    session.modified = True
    return jsonify(carrinho_detalhado())


@api.delete('/carrinho/itens/<int:produto_id>')
@login_obrigatorio
def api_remover_item(produto_id):
    carrinho = carrinho_sessao()
    if carrinho.pop(str(produto_id), None) is None:
        return erro('Produto não está no carrinho.', 404)
    session.modified = True
    return '', 204


# ---------------------------------------------------------------- Pedidos

@api.post('/pedidos')
@login_obrigatorio
def api_finalizar_pedido():
    carrinho = carrinho_sessao()
    if not carrinho:
        return erro('O carrinho está vazio.', 400)
    dados = corpo_json() or {}
    tipo = dados.get('tipo_pagamento', 'cartao')
    if tipo not in ('cartao', 'pix', 'boleto'):
        return erro('tipo_pagamento deve ser cartao, pix ou boleto.', 400)
    try:
        pedido_id = criar_pedido(session['cliente_id'], carrinho, tipo)
    except ProdutoNaoEncontrado as e:
        return erro(str(e), 404)
    except EstoqueInsuficiente as e:
        return erro(str(e), 409)
    session['carrinho'] = {}
    session.modified = True
    pedido = buscar_pedido_do_cliente(pedido_id, session['cliente_id'])
    return jsonify(pedido), 201, {'Location': f'/api/pedidos/{pedido_id}'}


@api.get('/pedidos')
@login_obrigatorio
def api_listar_pedidos():
    return jsonify(listar_pedidos_do_cliente(session['cliente_id']))


@api.get('/pedidos/<int:pedido_id>')
@login_obrigatorio
def api_detalhar_pedido(pedido_id):
    pedido = buscar_pedido_do_cliente(pedido_id, session['cliente_id'])
    if pedido is None:
        return erro('Pedido não encontrado.', 404)
    return jsonify(pedido)


# ---------------------------------------------------------------- Erros em JSON

@api.errorhandler(404)
def nao_encontrado(_):
    return erro('Recurso não encontrado.', 404)


@api.errorhandler(405)
def metodo_nao_permitido(_):
    return erro('Método não permitido para este recurso.', 405)
