import os
import sqlite3
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import auth  # noqa: E402
from app import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Cria um banco SQLite temporário a partir do script DDL, com 2 produtos."""
    db = tmp_path / 'teste.db'
    conn = sqlite3.connect(db)
    with open(os.path.join(RAIZ, 'script_ddl_sqlite.sql'), encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.executemany(
        'INSERT INTO produtos (id, nome, descricao, preco, estoque, imagem_url) VALUES (?, ?, ?, ?, ?, ?)',
        [(1, 'Caneca', 'Caneca branca', 29.9, 5, None),
         (2, 'Boné', 'Boné preto', 39.9, 1, None)],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(auth, 'DB_PATH', str(db))
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def logar(client):
    client.post('/api/auth/registrar', json={'nome': 'Ana', 'email': 'ana@x.com', 'senha': '123456'})
    return client.post('/api/auth/login', json={'email': 'ana@x.com', 'senha': '123456'})


def test_listar_e_buscar_produtos(client):
    r = client.get('/api/produtos')
    assert r.status_code == 200
    assert [p['nome'] for p in r.get_json()] == ['Caneca', 'Boné']

    assert client.get('/api/produtos?busca=can').get_json()[0]['id'] == 1
    assert client.get('/api/produtos/2').get_json()['preco'] == 39.9
    assert client.get('/api/produtos/99').status_code == 404


def test_registro_e_login(client):
    r = client.post('/api/auth/registrar', json={'nome': 'Ana', 'email': 'ana@x.com', 'senha': '123456'})
    assert r.status_code == 201
    r = client.post('/api/auth/registrar', json={'nome': 'Ana', 'email': 'ana@x.com', 'senha': '123456'})
    assert r.status_code == 409
    assert client.post('/api/auth/registrar', json={'nome': 'B', 'email': 'b@x.com', 'senha': '123'}).status_code == 400

    assert client.post('/api/auth/login', json={'email': 'ana@x.com', 'senha': 'errada'}).status_code == 401
    r = client.post('/api/auth/login', json={'email': 'ana@x.com', 'senha': '123456'})
    assert r.status_code == 200 and 'senha_hash' not in r.get_json()
    assert client.get('/api/auth/me').get_json()['email'] == 'ana@x.com'

    assert client.post('/api/auth/logout').status_code == 204
    assert client.get('/api/auth/me').status_code == 401


def test_carrinho_exige_login(client):
    assert client.get('/api/carrinho').status_code == 401
    assert client.post('/api/carrinho/itens', json={'produto_id': 1}).status_code == 401


def test_fluxo_carrinho(client):
    logar(client)
    r = client.post('/api/carrinho/itens', json={'produto_id': 1, 'quantidade': 2})
    assert r.status_code == 201
    assert r.get_json()['total'] == 59.8

    assert client.post('/api/carrinho/itens', json={'produto_id': 1, 'quantidade': 0}).status_code == 400
    assert client.post('/api/carrinho/itens', json={'produto_id': 'x'}).status_code == 400
    assert client.post('/api/carrinho/itens', json={'produto_id': 99}).status_code == 404
    assert client.post('/api/carrinho/itens', json={'produto_id': 2, 'quantidade': 2}).status_code == 409

    r = client.patch('/api/carrinho/itens/1', json={'quantidade': 3})
    assert r.get_json()['itens'][0]['quantidade'] == 3
    assert client.patch('/api/carrinho/itens/1', json={'quantidade': 50}).status_code == 409

    assert client.delete('/api/carrinho/itens/1').status_code == 204
    assert client.delete('/api/carrinho/itens/1').status_code == 404
    assert client.get('/api/carrinho').get_json() == {'itens': [], 'total': 0.0}


def test_finalizar_pedido_grava_e_baixa_estoque(client):
    logar(client)
    assert client.post('/api/pedidos').status_code == 400  # carrinho vazio

    client.post('/api/carrinho/itens', json={'produto_id': 1, 'quantidade': 2})
    client.post('/api/carrinho/itens', json={'produto_id': 2, 'quantidade': 1})
    r = client.post('/api/pedidos', json={'tipo_pagamento': 'pix'})
    assert r.status_code == 201
    pedido = r.get_json()
    assert pedido['total'] == 99.7
    assert pedido['pagamento'] == {'tipo': 'pix', 'status': 'aprovado'}
    assert r.headers['Location'] == f"/api/pedidos/{pedido['id']}"

    assert client.get('/api/produtos/1').get_json()['estoque'] == 3
    assert client.get('/api/produtos/2').get_json()['estoque'] == 0
    assert client.get('/api/carrinho').get_json()['itens'] == []
    assert len(client.get('/api/pedidos').get_json()) == 1
    assert client.get(f"/api/pedidos/{pedido['id']}").status_code == 200


def test_pedido_sem_estoque_nao_grava_nada(client, monkeypatch):
    logar(client)
    client.post('/api/carrinho/itens', json={'produto_id': 1, 'quantidade': 1})
    client.post('/api/carrinho/itens', json={'produto_id': 2, 'quantidade': 1})
    # Outro cliente compra o último boné antes do checkout
    conn = sqlite3.connect(auth.DB_PATH)
    conn.execute('UPDATE produtos SET estoque = 0 WHERE id = 2')
    conn.commit()
    conn.close()

    assert client.post('/api/pedidos').status_code == 409
    assert client.get('/api/produtos/1').get_json()['estoque'] == 5  # transação desfeita
    assert client.get('/api/pedidos').get_json() == []


def test_cliente_nao_ve_pedido_de_outro(client):
    logar(client)
    client.post('/api/carrinho/itens', json={'produto_id': 1})
    pedido_id = client.post('/api/pedidos').get_json()['id']
    client.post('/api/auth/logout')

    client.post('/api/auth/registrar', json={'nome': 'Bia', 'email': 'bia@x.com', 'senha': '123456'})
    client.post('/api/auth/login', json={'email': 'bia@x.com', 'senha': '123456'})
    assert client.get(f'/api/pedidos/{pedido_id}').status_code == 404


def test_rotas_desconhecidas_respondem_json(client):
    r = client.get('/api/nao-existe')
    assert r.status_code == 404 and r.get_json() == {'erro': 'Recurso não encontrado.'}
    assert client.delete('/api/produtos/1').status_code == 405


def test_checkout_do_site_salva_pedido(client):
    logar(client)
    client.post('/carrinho/adicionar/1', data={'quantidade': '2'})
    r = client.post('/checkout')
    assert r.status_code == 302
    pedidos = client.get('/api/pedidos').get_json()
    assert len(pedidos) == 1 and pedidos[0]['total'] == 59.8
    assert 'Caneca' in client.get('/perfil').get_data(as_text=True)
