from flask import Flask, flash, render_template, request, redirect, url_for, session
import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
conn = sqlite3.connect(DB_PATH)

app = Flask(__name__)
app.secret_key = 'testesegredo'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    pontos = 0
    if treinou_qtd >= 4:
        pontos += 1
    if treinou_qtd >= 4 and fez_dieta:
        pontos += 2
    if bebeu:
        pontos -= 2
    return pontos

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

        # Conectar ao banco de dados
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Buscar o usuário no banco
        c.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
        user = c.fetchone()
        
        conn.close()

        # Verificando se o usuário foi encontrado
        if user:
            print("Usuário encontrado:", user)  # Verificar se o usuário foi encontrado
            # Verificar a senha
            if user and user[3] == senha:  # Supondo que a senha esteja no índice 3
                session['usuario_id'] = user[0]  # Armazenar o id do usuário
                print("Login bem-sucedido:", session['usuario_id'])
                return redirect(url_for('dashboard'))
            else:
                print("Senha incorreta")  # Senha não bate
        else:
            print("Usuário não encontrado2")
        
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

    # Buscar nome do usuário logado
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT nome FROM usuarios WHERE id = ?", (session['usuario_id'],))
    user = c.fetchone()
    conn.close()
    nome_usuario = user[0] if user else 'Usuário'

    if request.method == 'POST':
        treinou_qtd = int(request.form.get('treinou_qtd', 0))
        fez_dieta = 'fez_dieta' in request.form
        bebeu = 'bebeu' in request.form

        pontos = calcular_pontos(treinou_qtd, fez_dieta, bebeu)

        semana = datetime.now().strftime('%Y-%m-%d')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO registros (usuario_id, semana, treinou_qtd, fez_dieta, bebeu, pontos) VALUES (?, ?, ?, ?, ?, ?)",
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

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Buscar nome do usuário junto com os registros
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
    conn = sqlite3.connect(DB_PATH)
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
    if not os.path.exists('banco.db'):
        init_db()

from flask import request, flash

@app.route('/deletar_registro/<int:registro_id>', methods=['POST'])
def deletar_registro(registro_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Deleta apenas se o registro pertence ao usuário logado
    c.execute("DELETE FROM registros WHERE id = ? AND usuario_id = ?", (registro_id, session['usuario_id']))
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

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Verifica se já existe usuário com o mesmo email
        c.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        if c.fetchone():
            conn.close()
            flash('Email já cadastrado!', 'error')
            return render_template('register.html')
        # Insere novo usuário
        c.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha))
        conn.commit()
        conn.close()
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)
