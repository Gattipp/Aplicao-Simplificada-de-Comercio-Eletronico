from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from auth import criar_cliente, autenticar_cliente, buscar_cliente_por_id, init_db, bcrypt

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
    return render_template('index.html')

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

@app.route('/carrinho')
@login_required
def carrinho():
    return "Carrinho Hipotético"

@app.route('/logout')
def logout():
    session.clear()
    flash('Conta deslogada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(port=5000, host='0.0.0.0')