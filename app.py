from flask import Flask, render_template, request, redirect, url_for, session, flash
from auth import (
    criar_cliente, autenticar_cliente, buscar_cliente_por_id, 
    get_db_connection, buscar_produtos_em_destaque, init_db, bcrypt,
    buscar_produto_por_id, listar_produtos 
)
from functools import wraps

app = Flask(__name__)
app.secret_key = '123456'
bcrypt.init_app(app)

def get_carrinho():
    if "carrinho" not in session:
        session["carrinho"] = {}
    return session["carrinho"]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'cliente_id' not in session:
            flash("Login necessário.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
            return redirect(url_for('index'))
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
    carrinho_session = get_carrinho()
    produtos = listar_produtos()
    itens = []
    total = 0

    for produto_id, qtd in carrinho_session.items():
        for p in produtos:
            if p["id"] == int(produto_id):
                subtotal = p["preco"] * qtd
                itens.append({
                    "produto": p,
                    "qtd": qtd,
                    "subtotal": subtotal
                })
                total += subtotal

    return render_template('carrinho.html', itens=itens, total=total)

@app.route('/carrinho/adicionar/<int:produto_id>', methods=['POST'])
@login_required
def adicionar_carrinho(produto_id):
    qtd = int(request.form.get("quantidade", 1))
    carrinho_session = get_carrinho()

    carrinho_session[str(produto_id)] = carrinho_session.get(str(produto_id), 0) + qtd
    session.modified = True

    flash("Produto adicionado ao carrinho!", "success")
    return redirect(url_for('carrinho')) 

@app.route('/carrinho/remover/<int:produto_id>')
@login_required
def remover_do_carrinho(produto_id):
    carrinho_session = get_carrinho()
    carrinho_session.pop(str(produto_id), None)
    session.modified = True

    flash("Item removido.", "info")
    return redirect(url_for('carrinho'))

@app.route('/carrinho/atualizar/<int:produto_id>', methods=['POST'])
@login_required
def atualizar_quantidade(produto_id):
    qtd_str = request.form.get("quantidade")
    carrinho_session = get_carrinho()
    
    if qtd_str is None or not qtd_str.isdigit():
        flash("Quantidade inválida.", "error")
        return redirect(url_for('carrinho'))

    qtd = int(qtd_str)
    produto_id_str = str(produto_id)

    if qtd > 0:
        carrinho_session[produto_id_str] = qtd
        flash(f"Quantidade do produto {produto_id} atualizada para {qtd}.", "success")
    else:
        # Se a quantidade for 0, remove o item
        carrinho_session.pop(produto_id_str, None)
        flash("Item removido do carrinho.", "info")

    session.modified = True
    return redirect(url_for('carrinho'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    from auth import (
        buscar_produto_por_id,
    )

    carrinho_session = get_carrinho()

    if not carrinho_session:
        flash("Seu carrinho está vazio!", "warning")
        return redirect(url_for('carrinho'))

    itens = []
    total = 0

    for pid, qtd in carrinho_session.items():
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

    if request.method == "POST":
        session["carrinho"] = {}
        session.modified = True

        flash("Pedido concluído com sucesso! Detalhes em seu perfil.", "success")
        return redirect(url_for('perfil'))

    return render_template('checkout.html', itens=itens, total=total)

@app.route('/logout')
def logout():
    session.clear()
    flash('Conta deslogada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)