from flask import Flask, flash, render_template, request, redirect, url_for, session
import os
from datetime import datetime
import psycopg2
from urllib.parse import urlparse

def get_connection():
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        raise ValueError("DATABASE_URL não configurada nas variáveis de ambiente")

    result = urlparse(database_url)

    conn = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )

    return conn

app = Flask(__name__)
app.secret_key = 'testesegredo'

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER,
                    semana TEXT,
                    treinou_qtd INTEGER,
                    fez_dieta INTEGER,
                    bebeu INTEGER,
                    pontos INTEGER,
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    conn.commit()
    conn.close()

def calcular_pontos(treinou_qtd, fez_dieta, bebeu):
    if bebeu and treinou_qtd < 4:
        return -3
    if bebeu:
        return -2
    if treinou_qtd >= 4 and fez_dieta:
        return 2
    if treinou_qtd >= 4:
        return 1
    return -1

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = c.fetchone()
        conn.close()

        if user:
            if user and user[3] == senha:
                session['usuario_id'] = user[0]
                return redirect(url_for('dashboard'))
            else:
                flash("Senha incorreta", 'error')
        else:
            flash("Usuário não encontrado", 'error')
        flash("Email ou senha inválidos", 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT nome FROM usuarios WHERE id = %s", (session['usuario_id'],))
    user = c.fetchone()
    conn.close()
    nome_usuario = user[0] if user else 'Usuário'

    if request.method == 'POST':
        treinou_qtd = int(request.form.get('treinou_qtd', 0))
        fez_dieta = 'fez_dieta' in request.form
        bebeu = 'bebeu' in request.form

        pontos = calcular_pontos(treinou_qtd, fez_dieta, bebeu)
        semana = datetime.now().strftime('%Y-%m-%d')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO registros (usuario_id, semana, treinou_qtd, fez_dieta, bebeu, pontos) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['usuario_id'], semana, treinou_qtd, int(fez_dieta), int(bebeu), pontos)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('ranking'))

    return render_template('dashboard.html', nome_usuario=nome_usuario)

@app.route('/registros')
def registros():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT r.id, r.usuario_id, u.nome, r.semana, r.treinou_qtd, r.fez_dieta, r.bebeu, r.pontos
        FROM registros r
        JOIN usuarios u ON r.usuario_id = u.id
        ORDER BY r.semana DESC
    """)
    registros = [
        {
            'id': row[0],
            'id_usuario': row[1],
            'nome_usuario': row[2],
            'semana': row[3],
            'qtd_treinos': row[4],
            'fez_dieta': bool(row[5]),
            'bebeu': bool(row[6]),
            'pontos': row[7]
        }
        for row in c.fetchall()
    ]
    conn.close()

    return render_template('registros.html', registros=registros, usuario_id=session['usuario_id'])

@app.route('/ranking')
def ranking():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.nome, COALESCE(SUM(r.pontos), 0) AS total_pontos
        FROM usuarios u
        LEFT JOIN registros r ON u.id = r.usuario_id
        GROUP BY u.id
        ORDER BY total_pontos DESC
    """)
    ranking = c.fetchall()
    conn.close()
    return render_template('ranking.html', ranking=ranking)

@app.before_request
def setup():
    # No PostgreSQL, não precisa checar arquivo, mas pode garantir que as tabelas existem
    init_db()

@app.route('/deletar_registro/<int:registro_id>', methods=['POST'])
def deletar_registro(registro_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM registros WHERE id = %s AND usuario_id = %s", (registro_id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash('Registro deletado com sucesso!', 'success')
    return redirect(url_for('registros'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        if c.fetchone():
            conn.close()
            flash('Email já cadastrado!', 'error')
            return render_template('register.html')
        c.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)", (nome, email, senha))
        conn.commit()
        conn.close()
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/admin/usuarios')
def admin_usuarios():
    if 'usuario_id' not in session or session['usuario_id'] != 1:
        return redirect(url_for('dashboard'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nome, email FROM usuarios")
    usuarios = c.fetchall()
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
def editar_usuario(usuario_id):
    if 'usuario_id' not in session or session['usuario_id'] != 1:
        flash('Acesso restrito!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    c = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        c.execute("UPDATE usuarios SET nome = %s, email = %s WHERE id = %s", (nome, email, usuario_id))
        conn.commit()
        conn.close()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    else:
        c.execute("SELECT nome, email FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = c.fetchone()
        conn.close()
        return render_template('editar_usuario.html', usuario=usuario, usuario_id=usuario_id)

@app.route('/admin/usuarios/excluir/<int:usuario_id>', methods=['POST'])
def excluir_usuario(usuario_id):
    if 'usuario_id' not in session or session['usuario_id'] != 1:
        flash('Acesso restrito!', 'error')
        return redirect(url_for('dashboard'))
    if usuario_id == 1:
        flash('Não é permitido excluir o usuário administrador.', 'error')
        return redirect(url_for('admin_usuarios'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
    conn.commit()
    conn.close()
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))

if __name__ == '__main__':
    app.run(debug=True)
