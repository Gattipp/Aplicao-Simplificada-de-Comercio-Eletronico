from flask_bcrypt import Bcrypt
import sqlite3
import os

bcrypt = Bcrypt()

# Caminho do banco configurável por variável de ambiente (útil para testes e deploy)
DB_PATH = os.environ.get('DB_PATH', 'loja_online.db')


class EstoqueInsuficiente(Exception):
    pass


class ProdutoNaoEncontrado(Exception):
    pass


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def criar_cliente(nome, email, senha, telefone):
    conn = get_db_connection()
    senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
    try:
        conn.execute(
            'INSERT INTO clientes (nome, email, senha_hash, telefone) VALUES (?, ?, ?, ?)',
            (nome, email, senha_hash, telefone)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def autenticar_cliente(email, senha):
    conn = get_db_connection()
    cliente = conn.execute(
        'SELECT * FROM clientes WHERE email = ?', (email,)
    ).fetchone()
    conn.close()
    
    if cliente and bcrypt.check_password_hash(cliente['senha_hash'], senha):
        return {
            'id': cliente['id'],
            'nome': cliente['nome'], 
            'email': cliente['email'],
            'telefone': cliente['telefone']
        }
    return None

def buscar_cliente_por_id(id):
    conn = get_db_connection()
    cliente = conn.execute(
        'SELECT * FROM clientes WHERE id = ?', (id,)
    ).fetchone()
    conn.close()
    
    if cliente:
        return {
            'id': cliente['id'],
            'nome': cliente['nome'],
            'email': cliente['email'], 
            'telefone': cliente['telefone']
        }
    return None

def buscar_produtos_em_destaque():
    conn = get_db_connection()
    produtos = conn.execute(
        """
        SELECT 
            id, nome, preco, descricao, estoque, imagem_url
        FROM produtos
        """
    ).fetchall()
    
    conn.close()
    
    return [dict(produto) for produto in produtos]

def buscar_produto_por_id(produto_id):
    conn = get_db_connection()
    produto = conn.execute(
        """
        SELECT 
            id, nome, preco, descricao, estoque, imagem_url
        FROM produtos 
        WHERE id = ?
        """, 
        (produto_id,)
    ).fetchone()
    conn.close()

    if produto:
        return dict(produto) 
    return None

def listar_produtos():
    conn = get_db_connection()
    produtos = conn.execute(
        """
        SELECT 
            id, nome, preco, descricao, estoque, imagem_url
        FROM produtos
        """
    ).fetchall()
    conn.close()
    return [dict(produto) for produto in produtos]

def criar_pedido(cliente_id, carrinho, tipo_pagamento='cartao'):
    """Cria o pedido, seus itens e o pagamento, e dá baixa no estoque.

    `carrinho` é um dict {produto_id: quantidade}. Tudo acontece em uma única
    transação: se algum produto não existir ou não tiver estoque, nada é gravado.
    Retorna o id do pedido criado.
    """
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        itens = []
        for pid, qtd in carrinho.items():
            produto = conn.execute(
                'SELECT id, nome, preco, estoque FROM produtos WHERE id = ?', (int(pid),)
            ).fetchone()
            if produto is None:
                raise ProdutoNaoEncontrado(f'Produto {pid} não encontrado.')
            if produto['estoque'] < qtd:
                raise EstoqueInsuficiente(f"Estoque insuficiente para {produto['nome']}.")
            itens.append((produto, qtd))

        cur = conn.execute(
            "INSERT INTO pedidos (cliente_id, data, status) VALUES (?, datetime('now', 'localtime'), ?)",
            (cliente_id, 'confirmado')
        )
        pedido_id = cur.lastrowid

        for produto, qtd in itens:
            conn.execute(
                'INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)',
                (pedido_id, produto['id'], qtd, produto['preco'])
            )
            conn.execute(
                'UPDATE produtos SET estoque = estoque - ? WHERE id = ?', (qtd, produto['id'])
            )

        conn.execute(
            'INSERT INTO pagamentos (pedido_id, tipo, status) VALUES (?, ?, ?)',
            (pedido_id, tipo_pagamento, 'aprovado')
        )
        conn.commit()
        return pedido_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _montar_pedido(conn, pedido):
    itens = conn.execute(
        """
        SELECT i.produto_id, p.nome, i.quantidade, i.preco_unitario
        FROM itens_pedido i JOIN produtos p ON p.id = i.produto_id
        WHERE i.pedido_id = ?
        """, (pedido['id'],)
    ).fetchall()
    pagamento = conn.execute(
        'SELECT tipo, status FROM pagamentos WHERE pedido_id = ?', (pedido['id'],)
    ).fetchone()
    itens = [
        {
            'produto_id': i['produto_id'],
            'nome': i['nome'],
            'quantidade': i['quantidade'],
            'preco_unitario': i['preco_unitario'],
            'subtotal': round(i['quantidade'] * i['preco_unitario'], 2),
        }
        for i in itens
    ]
    return {
        'id': pedido['id'],
        'data': pedido['data'],
        'status': pedido['status'],
        'pagamento': dict(pagamento) if pagamento else None,
        'itens': itens,
        'total': round(sum(i['subtotal'] for i in itens), 2),
    }


def listar_pedidos_do_cliente(cliente_id):
    conn = get_db_connection()
    pedidos = conn.execute(
        'SELECT id, data, status FROM pedidos WHERE cliente_id = ? ORDER BY id DESC', (cliente_id,)
    ).fetchall()
    resultado = [_montar_pedido(conn, p) for p in pedidos]
    conn.close()
    return resultado


def buscar_pedido_do_cliente(pedido_id, cliente_id):
    conn = get_db_connection()
    pedido = conn.execute(
        'SELECT id, data, status FROM pedidos WHERE id = ? AND cliente_id = ?', (pedido_id, cliente_id)
    ).fetchone()
    resultado = _montar_pedido(conn, pedido) if pedido else None
    conn.close()
    return resultado


def init_db():
    script_path = 'script_ddl_sqlite.sql'

    conn = get_db_connection()

    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        conn.executescript(sql_script)
        print("Tabelas criadas/validadas via script SQL.")
    
    try:
        senha_hash = bcrypt.generate_password_hash('654321').decode('utf-8')
        conn.execute(
            'INSERT OR IGNORE INTO clientes (nome, email, senha_hash, telefone) VALUES (?, ?, ?, ?)',
            ('Cliente Teste', 'teste@email.com', senha_hash, '(31) 99999-9999')
        )
        print("Cliente teste criado!")
    except:
        pass

    conn.commit()
    conn.close()