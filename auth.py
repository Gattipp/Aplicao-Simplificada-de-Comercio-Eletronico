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

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            telefone TEXT,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    #TESTE
    try:
        senha_hash = bcrypt.generate_password_hash('654321').decode('utf-8')
        conn.execute(
            'INSERT OR IGNORE INTO clientes (nome, email, senha_hash, telefone) VALUES (?, ?, ?, ?)',
            ('Cliente Teste', 'teste@email.com', senha_hash, '(31) 99999-9999')
        )
        print("CLIENTE TESTE CRIADO: teste@email.com / 654321")
    except:
        pass
    
    conn.commit()
    conn.close()