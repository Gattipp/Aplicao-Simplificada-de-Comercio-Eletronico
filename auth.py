from flask_bcrypt import Bcrypt
import sqlite3
import os

bcrypt = Bcrypt()

def get_db_connection():
    conn = sqlite3.connect('loja_online.db')
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

def buscar_itens_carrinho(cliente_id):
    """
    Busca itens do carrinho adaptado para a tabela 'carrinho_compras'.
    Faz o JOIN pelo 'nome_produto' pois a tabela não tem 'produto_id'.
    """
    conn = get_db_connection()
    
    # ADAPTAÇÃO CRÍTICA:
    # 1. Tabela mudou de 'ItensCarrinho' para 'carrinho_compras'
    # 2. JOIN mudou de 'id' para 'nome' (cc.nome_produto = p.nome)
    itens = conn.execute(
        """
        SELECT 
            p.id AS produto_id, 
            p.nome AS nome_produto, 
            p.preco, 
            cc.quantidade, 
            (p.preco * cc.quantidade) AS subtotal,
            p.imagem_url
        FROM carrinho_compras cc
        JOIN produtos p ON cc.nome_produto = p.nome
        WHERE cc.cliente_id = ?
        """,
        (cliente_id,)
    ).fetchall()
    
    conn.close()
    
    itens_formatados = []
    
    for item in itens:
        item_dict = dict(item)
        
        # Garante que tenha uma imagem válida para exibir
        if not item_dict.get('imagem_url'):
            item_dict['imagem_url'] = DEFAULT_IMAGE_URL 
        
        itens_formatados.append(item_dict)
        
    return itens_formatados

def buscar_produtos_em_destaque():
    """
    Busca um número limitado de produtos do banco de dados para a página inicial.
    """
    conn = get_db_connection() # Reutilize ou crie sua função de conexão
    produtos = conn.execute(
        """
        SELECT 
            id, nome, preco, descricao, estoque, imagem_url
        FROM Produtos
        """
    ).fetchall()
    
    conn.close()
    
    # Converte os objetos Row em dicionários simples para fácil uso no Flask
    return [dict(produto) for produto in produtos]

# auth.py

# ... (Funções existentes) ...

def buscar_produto_por_id(produto_id):
    """Busca um único produto pelo ID para a página de detalhes."""
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
        # Retorna o objeto Row (que se comporta como dicionário)
        return dict(produto) 
    return None

# ... (Resto das funções) ...

def init_db():
    db_path = 'loja_online.db'
    script_path = 'script_ddl_sqlite.sql'

    # cria as tabelas se o banco estiver vazio
    conn = get_db_connection()

    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        conn.executescript(sql_script)
        print("Tabelas criadas/validadas via script SQL.")
    
    # cria um usuário de teste
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
