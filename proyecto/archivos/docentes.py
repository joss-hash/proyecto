from flask import Flask, render_template, request, redirect
import mysql.connector  # Librería para conectar a MySQL

app = Flask(__name__)

# Conexión a la base de datos
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="docentes"
)

# Ruta para GUARDAR datos en la tabla DOCENTES
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            id = request.form['id']
            no_empleado = request.form['no_empleado']
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form['apellido_materno']
            correo = request.form['correo']
            contraseña = request.form['contraseña']
            cursor = db.cursor()
            sql = """INSERT INTO docentes 
                     (id, no_empleado, apellido_paterno, apellido_materno, correo, contraseña) 
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (id, no_empleado, apellido_paterno, apellido_materno, correo, contraseña))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al guardar: {e}"

    # Mostrar los registros de la tabla docentes
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, no_empleado, apellido_paterno, apellido_materno, correo, contraseña FROM docentes")
    docentes = cursor.fetchall()
    cursor.close()
    return render_template('docentes.html', docentes=docentes)

# Ruta para editar y actualizar docentes
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        try:
            no_empleado = request.form['no_empleado']
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form['apellido_materno']
            correo = request.form['correo']
            contraseña = request.form['contraseña']

            sql = """UPDATE docentes 
                     SET no_empleado=%s, apellido_paterno=%s, apellido_materno=%s, correo=%s, contraseña=%s 
                     WHERE id=%s"""
            cursor.execute(sql, (no_empleado, apellido_paterno, apellido_materno, correo, contraseña, id))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al actualizar: {e}"
    else:
        cursor.execute("SELECT * FROM docentes WHERE id=%s", (id,))
        docente = cursor.fetchone()
        cursor.close()
        return render_template('editardocente.html', docente=docente)

# Ruta para eliminar docentes
@app.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    try:
        cursor = db.cursor()
        sql = "DELETE FROM docentes WHERE id=%s"
        cursor.execute(sql, (id,))
        db.commit()
        cursor.close()
        return redirect('/')
    except Exception as e:
        return f"Error al eliminar: {e}"

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)