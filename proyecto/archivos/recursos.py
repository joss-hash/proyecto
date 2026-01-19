from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date

app = Flask(__name__)

# --- Crear base de datos y tabla si no existe ---
def init_db():
    conn = sqlite3.connect("recursos.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS recursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            control TEXT NOT NULL,
            fecha TEXT NOT NULL,
            nombre TEXT NOT NULL,
            estadisticas TEXT,
            materia TEXT,
            tipo TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Mostrar todos los registros ---
@app.route('/')
def index():
    conn = sqlite3.connect("recursos.db")
    c = conn.cursor()
    c.execute("SELECT * FROM recursos")
    datos = c.fetchall()
    conn.close()
    return render_template('/templates/index.html', recursos=datos)

# --- Agregar nuevo recurso ---
@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if request.method == 'POST':
        control = request.form['control']
        fecha = request.form['fecha']
        nombre = request.form['nombre']
        estadisticas = request.form['estadisticas']
        materia = request.form['materia']
        tipo = request.form['tipo']

        conn = sqlite3.connect("recursos.db")
        c = conn.cursor()
        c.execute("INSERT INTO recursos (control, fecha, nombre, estadisticas, materia, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                  (control, fecha, nombre, estadisticas, materia, tipo))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('agregar.html', hoy=date.today())

# --- Editar un recurso ---
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    conn = sqlite3.connect("recursos.db")
    c = conn.cursor()

    if request.method == 'POST':
        control = request.form['control']
        fecha = request.form['fecha']
        nombre = request.form['nombre']
        estadisticas = request.form['estadisticas']
        materia = request.form['materia']
        tipo = request.form['tipo']

        c.execute("""UPDATE recursos SET 
                        control=?, fecha=?, nombre=?, estadisticas=?, materia=?, tipo=? 
                     WHERE id=?""",
                  (control, fecha, nombre, estadisticas, materia, tipo, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    c.execute("SELECT * FROM recursos WHERE id=?", (id,))
    recurso = c.fetchone()
    conn.close()
    return render_template('editar.html', recurso=recurso)

# --- Eliminar un recurso ---
@app.route('/eliminar/<int:id>')
def eliminar(id):
    conn = sqlite3.connect("recursos.db")
    c = conn.cursor()
    c.execute("DELETE FROM recursos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)