from flask import Flask,render_template,request,redirect,url_for,flash 
import mysql.connector
app = Flask (__name__)

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password ="",
    database =""
)
#Mostrar la lista de orientador
@app.route ('/')
def index():
    cursor=conexion.cursor(dictionary=True)
    cursor.execute("SELECT*FROM orientadores")
    orientadores = cursor.fetchall()
    cursor.close()
    return render_template('index.html',orientadores=orientadores)
#Formulario para agregar orientador
@app.route('/agregar')
def agregar ():
     return render_template('agregar.html')

# Guardar nuevo orientador
@app.route('/guardar', methods=['POST'])
def guardar():
    no_empleado = request.form['no_empleado']
    nombre = request.form['nombre']
    apellido_paterno = request.form['apellido_paterno']
    apellido_materno = request.form['apellido_materno']
    correo = request.form['correo']
    contrasena = request.form['contrasena']
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO orientadores (no_empleado, nombre, apellido_paterno, apellido_materno, correo, contrasena)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (no_empleado, nombre, apellido_paterno, apellido_materno, correo, contrasena))
    conexion.commit()
    cursor.close()
    flash('✅ Orientador agregado correctamente')
    return redirect(url_for('index'))

# Formulario para editar orientador
@app.route('/editar/<int:id>')
def editar(id):
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orientadores WHERE id = %s", (id,))
    orientador = cursor.fetchone()
    cursor.close()
    return render_template('editar.html', orientador= orientador)

# Actualizar orientador
@app.route('/actualizar/<int:id>', methods=['POST'])
def actualizar(id):
    no_empleado = request.form['no_empleado']
    nombre = request.form['nombre']
    apellido_paterno = request.form['apellido_paterno']
    apellido_materno = request.form['apellido_materno']
    correo = request.form['correo']
    contrasena = request.form['contrasena']
    cursor = conexion.cursor()
    cursor.execute("""
        UPDATE orientador
        SET no_empleado=%s, nombre=%s, apellido_paterno=%s, apellido_materno=%s, correo=%s, contrasena=%s
        WHERE id=%s
    """, (no_empleado, nombre, apellido_paterno, apellido_materno, correo, contrasena, id))
    conexion.commit()
    cursor.close()
    flash('✏ Orientador actualizado correctamente')
    return redirect(url_for('index'))

# Eliminar a Orientador
@app.route('/eliminar/<int:id>')
def eliminar(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM orientador WHERE id = %s", (id,))
    conexion.commit()
    cursor.close()
    flash('🗑 Orientador eliminado correctamente')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)