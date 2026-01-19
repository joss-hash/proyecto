from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB = 'alumnos.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alumnos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    numero_control TEXT NOT NULL,
                    curp TEXT NOT NULL,
                    turno TEXT NOT NULL,
                    fecha_registro TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

def get_db_rows(query, args=(), fetchone=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, args)
    rows = c.fetchone() if fetchone else c.fetchall()
    conn.close()
    return rows

@app.route('/')
def index():
    alumnos = get_db_rows('SELECT id, nombre, numero_control, curp, turno, fecha_registro FROM alumnos ORDER BY id DESC')
    return render_template('index.html', alumnos=alumnos, alumno=None)

@app.route('/add', methods=['POST'])
def add():
    nombre = request.form.get('nombre','').strip()
    numero = request.form.get('numero','').strip()
    curp = request.form.get('curp','').strip()
    turno = request.form.get('turno','').strip()
    if nombre and numero and curp and turno:
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('INSERT INTO alumnos (nombre, numero_control, curp, turno, fecha_registro) VALUES (?, ?, ?, ?, ?)',
                  (nombre, numero, curp, turno, fecha))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if request.method == 'GET':
        row = get_db_rows('SELECT id, nombre, numero_control, curp, turno, fecha_registro FROM alumnos WHERE id=?', (id,), fetchone=True)
        if not row:
            return redirect(url_for('index'))
        # send the selected alumno to template to fill the form
        alumno = {
            'id': row[0],
            'nombre': row[1],
            'numero_control': row[2],
            'curp': row[3],
            'turno': row[4],
            'fecha_registro': row[5]
        }
        alumnos = get_db_rows('SELECT id, nombre, numero_control, curp, turno, fecha_registro FROM alumnos ORDER BY id DESC')
        return render_template('index.html', alumnos=alumnos, alumno=alumno)
    else:
        # POST - update
        nombre = request.form.get('nombre','').strip()
        numero = request.form.get('numero','').strip()
        curp = request.form.get('curp','').strip()
        turno = request.form.get('turno','').strip()
        if nombre and numero and curp and turno:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute('UPDATE alumnos SET nombre=?, numero_control=?, curp=?, turno=? WHERE id=?',
                      (nombre, numero, curp, turno, id))
            conn.commit()
            conn.close()
        return redirect(url_for('index'))

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('DELETE FROM alumnos WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)