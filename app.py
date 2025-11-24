from flask import Flask, render_template, request, redirect, url_for, session, flash
from auth import (
    criar_cliente, autenticar_cliente, buscar_cliente_por_id, 
    get_db_connection, buscar_produtos_em_destaque, init_db, bcrypt,
    buscar_produto_por_id 
)
from functools import wraps
from auth import criar_cliente, autenticar_cliente, buscar_cliente_por_id, get_db_connection, buscar_produtos_em_destaque,init_db, bcrypt

app = Flask(__name__)
app.secret_key = '123456'
bcrypt.init_app(app)

#DECORATORS
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'cliente_id' not in session:
            flash("Login necessário.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#ROTAS
@app.route('/')
def index():
    produtos_destaque = buscar_produtos_em_destaque()
    return render_template('indexProdutos.html', produtos=produtos_destaque)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        telefone = request.form['telefone']
        
        #VALIDAÇÕES
        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres!', 'error')
            return render_template('registrar.html')
        
        if criar_cliente(nome, email, senha, telefone):
            flash('Cadastrado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email já existe!', 'error')
    
    return render_template('registrar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        cliente = autenticar_cliente(email, senha)
        if cliente:
            session['cliente_id'] = cliente['id']
            session['cliente_nome'] = cliente['nome']
            session['cliente_email'] = cliente['email']
            flash(f'Bem-vindo(a), {cliente["nome"]}!', 'success')
            return redirect(url_for('perfil'))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('login.html')

@app.route('/perfil')
@login_required
def perfil():
    cliente = buscar_cliente_por_id(session['cliente_id'])
    return render_template('perfil.html', cliente=cliente)


@app.route('/produto/<int:produto_id>')
def detalhes_produto(produto_id):
    produto = buscar_produto_por_id(produto_id)

    if produto is None:
        flash("Produto não encontrado.", "error")
        return redirect(url_for('index'))

    return render_template('detalhes_produto.html', produto=produto)


@app.route('/carrinho')
@login_required
def carrinho():
    client_id = session['client_id']
    itens_carrinho = buscar_itens_carrinho(cliente_id)
    
    total = sum(item['subtotal'] for item in itens_carrinho)

    return render_template('carrinho.html', itens=itens_carrinho, total=total)

# CHECKOUT
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    from auth import (
        buscar_produto_por_id,
        criar_pedido,
        criar_item_pedido,
        registrar_pagamento
    )

    carrinho = get_carrinho()

    if not carrinho:
        flash("Seu carrinho está vazio!", "warning")
        return redirect(url_for('carrinho'))

    itens = []
    total = 0

    # Validar estoque
    for pid, qtd in carrinho.items():
        produto = buscar_produto_por_id(int(pid))
        if not produto:
            flash("Produto não encontrado.", "error")
            return redirect(url_for('carrinho'))

        if produto["estoque"] < qtd:
            flash(f"Estoque insuficiente para {produto['nome']}.", "error")
            return redirect(url_for('carrinho'))

        subtotal = produto["preco"] * qtd
        itens.append({
            "produto": produto,
            "qtd": qtd,
            "subtotal": subtotal
        })
        total += subtotal

    # POST → FINALIZAR COMPRA
    if request.method == "POST":
        cliente_id = session["cliente_id"]

        # Criar pedido
        pedido_id = criar_pedido(cliente_id, total)

        # Criar itens do pedido
        for item in itens:
            criar_item_pedido(
                pedido_id,
                item["produto"]["id"],
                item["qtd"],
                item["produto"]["preco"]
            )

        # Registrar pagamento simulado
        registrar_pagamento(
            pedido_id,
            total,
            status="SUCESSO"
        )

        # Limpar carrinho
        session["carrinho"] = {}
        session.modified = True

        flash("Pedido concluído com sucesso!", "success")
        return redirect(url_for('pedido_recebido', pedido_id=pedido_id))

    return render_template('checkout.html', itens=itens, total=total)

@app.route('/logout')
def logout():
    session.clear()
    flash('Conta deslogada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # init_db()
    app.run(port=5000, host='0.0.0.0', debug=True)