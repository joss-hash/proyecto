from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime
import pandas as pd
from datetime import timedelta
import bcrypt
import os
import mysql.connector

app = Flask(__name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)
# Configuración de intentos de login
MAX_INTENTOS = 4
TIEMPO_BLOQUEO_MINUTOS = 5

# Diccionario en memoria para guardar intentos (se reinicia al reiniciar el servidor)
intentos_login = {}

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


app.secret_key = "clave_segura_2025"  # Cambia por algo más seguro
app.permanent_session_lifetime = timedelta(seconds=120)  # Sesión válida por 2 min

# Decorador para verificar sesión
def login_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash("Debes iniciar sesión primero", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Reemplaza la sección de login en apps.py (desde la línea ~60 hasta ~120)
# con este código:

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        password = request.form["password"]
        ip_address = request.remote_addr
        
        # Clave única por usuario + IP
        clave_intento = f"{user}_{ip_address}"
        
        # Verificar si está bloqueado
        if clave_intento in intentos_login:
            datos_intento = intentos_login[clave_intento]
            
            # Verificar si el bloqueo sigue activo
            if 'bloqueado_hasta' in datos_intento:
                tiempo_actual = datetime.now()
                if tiempo_actual < datos_intento['bloqueado_hasta']:
                    tiempo_restante = (datos_intento['bloqueado_hasta'] - tiempo_actual).seconds // 60
                    flash(f"⛔ Cuenta bloqueada por seguridad. Intenta nuevamente en {tiempo_restante} minutos.", "error")
                    return redirect(url_for('login'))
                else:
                    # El bloqueo expiró, eliminar registro
                    del intentos_login[clave_intento]
            
            # Verificar intentos fallidos
            elif datos_intento.get('intentos', 0) >= MAX_INTENTOS:
                # Bloquear usuario
                intentos_login[clave_intento]['bloqueado_hasta'] = datetime.now() + timedelta(minutes=TIEMPO_BLOQUEO_MINUTOS)
                flash(f"⛔ Demasiados intentos fallidos. Cuenta bloqueada por {TIEMPO_BLOQUEO_MINUTOS} minutos.", "error")
                
                # Redirigir a recuperar cuenta después de 4 intentos
                return redirect(url_for('recuperar'))
        
        cursor = db.cursor(dictionary=True)
        login_exitoso = False
        
        # 🔎 BUSCAR EN ORIENTADORES
        cursor.execute("SELECT * FROM orientadores WHERE nombre=%s AND no_empleado=%s", (user, password))
        result = cursor.fetchone()
        if result:
            session.permanent = True
            session['usuario'] = user
            session['nombre_completo'] = f"{result['nombre']} {result['apellido_paterno']} {result['apellido_materno']}"
            session['rol'] = 'Orientador'
            login_exitoso = True
            destino = "/dash_orientadores"
            rol = 'Orientador'

        # 🔎 BUSCAR EN DIRECTIVOS
        if not login_exitoso:
            cursor.execute("SELECT * FROM directivos WHERE nombre=%s AND no_empleado=%s", (user, password))
            result = cursor.fetchone()
            if result:
                session.permanent = True
                session['usuario'] = user
                session['nombre_completo'] = f"{result['nombre']} {result['apellido_paterno']} {result['apellido_materno']}"
                session['rol'] = 'Directivo'
                login_exitoso = True
                destino = "/dash_directivos"
                rol = 'Directivo'

        # 🔎 BUSCAR EN DOCENTES
        if not login_exitoso:
            cursor.execute("SELECT * FROM docentes WHERE nombre=%s AND no_empleado=%s", (user, password))
            result = cursor.fetchone()
            if result:
                session.permanent = True
                session['usuario'] = user
                session['nombre_completo'] = f"{result['nombre']} {result['apellido_paterno']} {result['apellido_materno']}"
                session['rol'] = 'Docente'
                login_exitoso = True
                destino = "/docentes_dash"
                rol = 'Docente'

        # 🔎 BUSCAR EN ALUMNOS
        if not login_exitoso:
            cursor.execute("SELECT * FROM alumnos WHERE nombre=%s AND NumeroControl=%s", (user, password))
            result = cursor.fetchone()
            if result:
                session.permanent = True
                session['usuario'] = user
                session['nombre_completo'] = f"{result['Nombre']} {result['Paterno']} {result['Materno']}"
                session['rol'] = 'Alumno'
                login_exitoso = True
                destino = "/alumnitos"
                rol = 'Alumno'

        cursor.close()
        
        if login_exitoso:
            # Login exitoso: eliminar intentos fallidos
            if clave_intento in intentos_login:
                del intentos_login[clave_intento]
            
            print(f"✅ Ingreso exitoso: {user} | Rol: {rol}")
            flash(f"Bienvenido {session.get('nombre_completo', user)} - Rol: {rol}", "success")
            return redirect(destino)
        else:
            # Login fallido: registrar intento
            if clave_intento not in intentos_login:
                intentos_login[clave_intento] = {'intentos': 0, 'primer_intento': datetime.now()}
            
            intentos_login[clave_intento]['intentos'] += 1
            intentos_login[clave_intento]['ultimo_intento'] = datetime.now()
            
            intentos_actuales = intentos_login[clave_intento]['intentos']
            intentos_restantes = MAX_INTENTOS - intentos_actuales
            
            print(f"❌ Intento fallido de login: {user} desde IP: {ip_address} - Intento {intentos_actuales}/{MAX_INTENTOS}")
            
            if intentos_restantes > 0:
                flash(f"❌ Usuario o contraseña incorrectos. Te quedan {intentos_restantes} intentos.", "error")
                return redirect(url_for('login'))
            else:
                # Bloquear y redirigir a recuperar
                intentos_login[clave_intento]['bloqueado_hasta'] = datetime.now() + timedelta(minutes=TIEMPO_BLOQUEO_MINUTOS)
                flash(f"⛔ Demasiados intentos fallidos. Serás redirigido a recuperación de cuenta.", "error")
                
                # Esperar 2 segundos antes de redirigir
                import time
                time.sleep(2)
                return redirect(url_for('recuperar'))

    return render_template("login_principal.html")
#--------------------------------Regresar al los dashboard-----------------------------
@app.route("/volver_dashboard")
def volver_dashboard():
    rol = session.get("rol")

    if rol == "Alumno":
        return redirect("/alumnitos")
    elif rol == "Docente":
        return redirect("/docentes_dash")
    elif rol == "Directivo":
        return redirect("/dash_directivos")
    elif rol == "Orientador":
        return redirect("/dash_orientadores")
    else:
        return redirect("/login")

# ------------------- RUTAS PROTEGIDAS -------------------

@app.route('/alumnitos')
@login_requerido
def alumnitos():
    
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docentes")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orientadores")
    total_orientadores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM directivos")
    total_directivos = cursor.fetchone()[0]

    cursor.close()
    return render_template(
        'alumno.html',
        alumnos=total_alumnos,
        docentes=total_docentes,
        orientadores=total_orientadores,
        directivos=total_directivos
    )

#----------------------- RUTA REDIRECCION PROFES-----------
@app.route('/docentes_dash')
@login_requerido
def docentes_dash():

    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docentes")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orientadores")
    total_orientadores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM directivos")
    total_directivos = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'dashboard_docentes.html',
        alumnos=total_alumnos,
        docentes=total_docentes,
        orientadores=total_orientadores,
        directivos=total_directivos
    )
#-------------------------- RUTA DIRECTIVOS------------------------
@app.route('/dash_directivos')
@login_requerido
def dash_directivos():

    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docentes")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orientadores")
    total_orientadores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM directivos")
    total_directivos = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'dash_directivos.html',
        alumnos=total_alumnos,
        docentes=total_docentes,
        orientadores=total_orientadores,
        directivos=total_directivos
    )


#-------------------------- RUTA ORIENTADORES------------------------
@app.route('/dash_orientadores')
@login_requerido
def dash_orientadores():

    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docentes")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orientadores")
    total_orientadores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM directivos")
    total_directivos = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'dash_orientadores.html',
        alumnos=total_alumnos,
        docentes=total_docentes,
        orientadores=total_orientadores,
        directivos=total_directivos
    )
# ------------------- RESTO DE RUTAS (sin cambios en funcionalidad) -------------------

# Ruta para GUARDAR datos en la base de datos dentro de la tabla alumnos
@app.route('/alumnos', methods=['GET', 'POST'])
def alumnos():

    if request.method == 'POST':
        try:
            NumeroControl = request.form['NumeroControl']
            Curp = request.form['Curp']
            Nombre = request.form['Nombre']
            Paterno = request.form['Paterno']
            Materno = request.form['Materno']
            Turno = request.form['Turno']
            Grupo = request.form['Grupo']
            Semestre = request.form['Semestre']
            cursor = db.cursor()
            sql = "INSERT INTO alumnos (NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al guardar: {e}"

    # Obtener (Mostrar) datos de la tabla orientadores
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Grupo, Turno, Semestre FROM alumnos")
    alumnos = cursor.fetchall()
    cursor.close()
    return render_template('alumnos.html', alumnos=alumnos)
# Ruta para BUSCAR alumnos (por texto o voz)
@app.route('/buscar_alumno', methods=['POST'])
def buscar_alumno():
    termino = request.form['termino']
    cursor = db.cursor(dictionary=True)
    consulta = """
        SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre
        FROM alumnos
        WHERE NumeroControl LIKE %s
        OR Curp LIKE %s
        OR Nombre LIKE %s
        OR Paterno LIKE %s
        OR Materno LIKE %s
        OR Grupo LIKE %s
        OR Semestre LIKE %s
    """
    like = f"%{termino}%"
    cursor.execute(consulta, (like, like, like, like, like, like, like))
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('alumnos.html', alumnos=resultados)

# Ruta para mostrar el formulario de edición y actualizar datos en la base de datos
@app.route('/editar_alumnos/<int:NumeroControl>', methods=['GET', 'POST'])
def editar_alumnos(NumeroControl):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        NumeroControl = request.form['NumeroControl']
        Curp = request.form['Curp']
        Nombre = request.form['Nombre']
        Paterno = request.form['Paterno']
        Materno = request.form['Materno']
        Turno = request.form['Turno']
        Grupo = request.form['Grupo']
        Semestre = request.form['Semestre']
        sql = "UPDATE alumnos SET NumeroControl=%s, Curp=%s, Nombre=%s, Paterno=%s, Materno=%s, Turno=%s, Grupo=%s, Semestre=%s WHERE NumeroControl=%s"
        cursor.execute(sql, (NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre, NumeroControl))
        db.commit()
        cursor.close()
        return redirect('/')
    
 #ruta de busqueda de alumno   
    else:
        cursor.execute("SELECT * FROM alumnos WHERE NumeroControl=%s", (NumeroControl,))
        alumnos = cursor.fetchone()
        cursor.close()
        return render_template('editar_alumnos.html', alumnos=alumnos)

#Ruta para eliminar datos de la base de datos
@app.route('/eliminar_alumnos/<int:NumeroControl>', methods=['POST'])
def eliminar_alumnos(NumeroControl):
    cursor = db.cursor()
    try:
        sql = "DELETE FROM alumnos WHERE NumeroControl=%s"
        cursor.execute(sql, (NumeroControl,))
        db.commit()
        cursor.close()
        return redirect('/')
    except Exception as e:
        return f"Error al eliminar: {e}"
    
#ruta directivos
@app.route('/directivos', methods=['GET', 'POST'])
def directivos():
    if request.method == 'POST':
        try:
            no_empleado = request.form['no_empleado']
            nombre = request.form['nombre']
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form['apellido_materno']
            area_desarrolla = request.form['area_desarrolla']
            cursor = db.cursor()
            sql = "INSERT INTO directivos (no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al guardar: {e}"
    # Obtener (Mostrar) datos de la tabla orientadores
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla FROM directivos")
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('directivos.html', directivo=resultados)

#ruta pa buscar directivo 
@app.route('/buscar_directivo', methods=['POST'])
def buscar_directivo():
    termino = request.form['termino']
    cursor = db.cursor(dictionary=True)
    consulta = """
        SELECT no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla
        FROM directivos
        WHERE no_empleado LIKE %s
        OR nombre LIKE %s
        OR apellido_paterno LIKE %s
        OR apellido_materno LIKE %s
        OR area_desarrolla LIKE %s
    """
    like = f"%{termino}%"
    cursor.execute(consulta, (like, like, like, like, like, like, like))
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('directivos.html', directivo=resultados)

# Ruta para mostrar el formulario de edición y actualizar datos en la base de datos
@app.route('/editar_directivo/<int:no_empleado>', methods=['GET', 'POST'])
def editar_directivo(no_empleado):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        no_empleado = request.form['no_empleado']
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        area_desarrolla = request.form['area_desarrolla']
        sql = "UPDATE directivos SET nombre=%s, apellido_paterno=%s, apellido_materno=%s, area_desarrolla=%s WHERE no_empleado=%s"
        cursor.execute(sql, ( nombre, apellido_paterno, apellido_materno, area_desarrolla, no_empleado))
        db.commit()
        cursor.close()
        return redirect('/')
    else:
        cursor.execute("SELECT * FROM directivos WHERE no_empleado=%s", (no_empleado,))
        resultados = cursor.fetchone()
        cursor.close()
        return render_template('editar_directivos.html', directivo=resultados)

#Ruta para eliminar datos de la base de datos los directivos
@app.route('/eliminar_directivos/<int:no_empleado>', methods=['POST'])
def eliminar_directivos(no_empleado):
    cursor = db.cursor()
    try:
        sql = "DELETE FROM directivos WHERE no_empleado=%s"
        cursor.execute(sql, (no_empleado,))
        db.commit()
        cursor.close()
        return redirect('/')
    except Exception as e:
        return f"Error al eliminar: {e}"


#Ruta para docentes
@app.route('/docentes', methods=['GET', 'POST'])
def docentes():
    if request.method == 'POST':
        try:
            no_empleado = request.form['no_empleado']
            nombre = request.form['nombre']
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form['apellido_materno']
            materia_desarrolla = request.form['materia_desarrolla']
            cursor = db.cursor()
            sql = "INSERT INTO docentes (no_empleado, nombre, apellido_paterno, apellido_materno, materia_desarrolla) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (no_empleado, nombre, apellido_paterno, apellido_materno, materia_desarrolla))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al guardar: {e}"

    # Obtener (Mostrar) datos de la tabla docentes
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT no_empleado, nombre, apellido_paterno, apellido_materno, materia_desarrolla FROM docentes")
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('docentes.html', docentes=resultados)

#ruta pa buscar directivo 
@app.route('/buscar_docente', methods=['POST'])
def buscar_docente():
    termino = request.form['termino']
    cursor = db.cursor(dictionary=True)
    consulta = """
        SELECT no_empleado, nombre, apellido_paterno, apellido_materno, materia_desarrolla
        FROM docentes
        WHERE no_empleado LIKE %s
        OR nombre LIKE %s
        OR apellido_paterno LIKE %s
        OR apellido_materno LIKE %s
        OR materia_desarrolla LIKE %s
    """
    like = f"%{termino}%"
    cursor.execute(consulta, (like, like, like, like, like, like, like))
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('docentes.html', docentes=resultados)

# Ruta para mostrar el formulario de edición y actualizar datos en la base de datos
@app.route('/editar_docentes/<int:no_empleado>', methods=['GET', 'POST'])
def editar_docentes(no_empleado):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        no_empleado = request.form['no_empleado']
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        materia_desarrolla = request.form['materia_desarrolla']
        sql = "UPDATE docentes SET nombre=%s, apellido_paterno=%s, apellido_materno=%s, materia_desarrolla=%s, WHERE no_empleado=%s"
        cursor.execute(sql, ( nombre, apellido_paterno, apellido_materno, materia_desarrolla, no_empleado))
        db.commit()
        cursor.close()
        return redirect('/')
    else:
        cursor.execute("SELECT * FROM docentes WHERE no_empleado=%s", (no_empleado,))
        docentes = cursor.fetchone()
        cursor.close()
        return render_template('editar_docentes.html', docentes=docentes)

#Ruta para eliminar datos de la base de datos
@app.route('/eliminar_docentes/<int:no_empleado>', methods=['POST'])
def eliminar_docentes(no_empleado):
    cursor = db.cursor()
    try:
        sql = "DELETE FROM docentes WHERE no_empleado=%s"
        cursor.execute(sql, (no_empleado,))
        db.commit()
        cursor.close()
        return redirect('/')
    except Exception as e:
        return f"Error al eliminar: {e}"
    

    

#ruta orientadores
@app.route('/orientadores', methods=['GET', 'POST'])
def orientadores():
    if request.method == 'POST':
        try:
            no_empleado = request.form['no_empleado']
            nombre = request.form['nombre']
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form['apellido_materno']
            area_desarrolla = request.form['area_desarrolla']
            cursor = db.cursor()
            sql = "INSERT INTO orientadores (no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla))
            db.commit()
            cursor.close()
            return redirect('/')
        except Exception as e:
            return f"Error al guardar: {e}"

    # Obtener (Mostrar) datos de la tabla orientadores
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla, no_empleado FROM orientadores")
    orientadores = cursor.fetchall()
    cursor.close()
    return render_template('orientadores.html', orientadores=orientadores)

#ruta pa buscar orientadores
@app.route('/buscar_orientadores', methods=['POST'])
def buscar_orientadores():
    termino = request.form['termino']
    cursor = db.cursor(dictionary=True)
    consulta = """
        SELECT no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla
        FROM orientadores
        WHERE no_empleado LIKE %s
        OR nombre LIKE %s
        OR apellido_paterno LIKE %s
        OR apellido_materno LIKE %s
        OR area_desarrolla LIKE %s
    """
    like = f"%{termino}%"
    cursor.execute(consulta, (like, like, like, like, like))
    resultados = cursor.fetchall()
    cursor.close()
    return render_template('orientadores.html', orientadores=resultados)

# Ruta para mostrar el formulario de edición y actualizar datos en la base de datos
@app.route('/editar_orientadores/<int:no_empleado>', methods=['GET', 'POST'])
def editar_orientadores(no_empleado):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        no_empleado = request.form['no_empleado']
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        area_desarrolla = request.form['area_desarrolla']
        sql = "UPDATE orientadores SET no_empleado=%s, nombre=%s, apellido_paterno=%s, apellido_materno=%s, area_desarrolla=%s, WHERE no_empleado=%s"
        cursor.execute(sql, (no_empleado, nombre, apellido_paterno, apellido_materno, area_desarrolla, no_empleado))
        db.commit()
        cursor.close()
        return redirect('/')
    else:
        cursor.execute("SELECT * FROM orientadores WHERE no_empleado=%s", (no_empleado,))
        orientadores = cursor.fetchone()
        cursor.close()
        return render_template('editar_orientadores.html', orientadores=orientadores)

#------------------------Ruta para eliminar datos de la base de datos---------------------#
@app.route('/eliminar_orientadores/<int:no_empleado>', methods=['POST'])
def eliminar_orientadores(no_empleado):
    cursor = db.cursor()
    try:
        sql = "DELETE FROM orientadores WHERE no_empleado=%s"
        cursor.execute(sql, (no_empleado,))
        db.commit()
        cursor.close()
        return redirect('/')
    except Exception as e:
        return f"Error al eliminar: {e}"
    
#----------------------- subir recursos----------------------------
@app.route('/subir_recurso', methods=['GET', 'POST'])
@login_requerido
def subir_recurso():

    if session['rol'] == "Alumno":
        return "No tienes permiso", 403

    if request.method == 'POST':
        archivo = request.files['archivo']
        mensaje = request.form['mensaje']

        if archivo.filename != "":
            nombre = archivo.filename
            ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre)
            archivo.save(ruta)

            cursor = db.cursor()
            sql = """INSERT INTO recursos 
                     (nombre_archivo, ruta_archivo, mensaje, usuario, rol) 
                     VALUES (%s,%s,%s,%s,%s)"""
            cursor.execute(sql, (
                nombre, ruta, mensaje,
                session['usuario'], session['rol']
            ))
            db.commit()
            cursor.close()

            return redirect('/recursos')

    return render_template('subir.html')

#-------------- ver recursos -------------------
@app.route('/recursos')
@login_requerido
def recursos():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recursos ORDER BY fecha DESC")
    recursos = cursor.fetchall()
    cursor.close()

    return render_template('ver_recursos.html', recursos=recursos)

#-------------------- descargar -----------------
@app.route('/descargar/<int:id>')
@login_requerido
def descargar(id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()
    cursor.close()

    return send_file(recurso['ruta_archivo'], as_attachment=True)

#---------------- eliminar----------------
@app.route('/eliminar_recurso/<int:id>')
@login_requerido
def eliminar_recurso(id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()

    if recurso['usuario'] != session['usuario']:
        return "No puedes eliminar este archivo", 403

    os.remove(recurso['ruta_archivo'])
    cursor.execute("DELETE FROM recursos WHERE id=%s", (id,))
    db.commit()
    cursor.close()

    return redirect('/recursos')

#-------------------------- editar ------------------
@app.route('/editar_recurso/<int:id>', methods=['GET','POST'])
@login_requerido
def editar_recurso(id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()

    if recurso['usuario'] != session['usuario']:
        return "No puedes editar esto", 403

    if request.method == 'POST':
        nuevo = request.form['mensaje']
        cursor.execute("UPDATE recursos SET mensaje=%s WHERE id=%s", (nuevo,id))
        db.commit()
        cursor.close()
        return redirect('/recursos')

    cursor.close()
    return render_template('editar_recurso.html', recurso=recurso)

   # ============================================
# SISTEMA DE REPORTES 
# ============================================

@app.route('/reportes')
@login_requerido
def panel_reportes():
    """Panel principal de generación de reportes"""
    
    # Solo directivos y orientadores pueden generar reportes completos
    if session['rol'] not in ['Directivo', 'Orientador']:
        flash("No tienes permisos para acceder a esta sección", "error")
        return redirect('/')
    
    return render_template('reportes.html')


# ============================================
# REPORTE GENERAL DE ALUMNOS (PDF)
# ============================================
@app.route('/reporte/alumnos/pdf')
@login_requerido
def reporte_alumnos_pdf():
    """Genera PDF con todos los alumnos registrados"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT NumeroControl, Curp, Nombre, Paterno, Materno, 
               Turno, Grupo, Semestre 
        FROM alumnos 
        ORDER BY Semestre, Grupo, Paterno
    """)
    alumnos = cursor.fetchall()
    cursor.close()
    
    # Crear PDF en memoria
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=30, leftMargin=30,
                           topMargin=40, bottomMargin=30)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Título
    titulo_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e8449'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    titulo = Paragraph("<b>REPORTE GENERAL DE ALUMNOS</b>", titulo_style)
    elementos.append(titulo)
    
    # Información del reporte
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    info = Paragraph(f"Generado por: {session['usuario']} - {session['rol']}<br/>Fecha: {fecha_actual}", info_style)
    elementos.append(info)
    elementos.append(Spacer(1, 20))
    
    # Estadísticas
    total_alumnos = len(alumnos)
    estadisticas = Paragraph(f"<b>Total de alumnos registrados: {total_alumnos}</b>", styles['Normal'])
    elementos.append(estadisticas)
    elementos.append(Spacer(1, 20))
    
    # Tabla de datos
    datos = [['No. Control', 'CURP', 'Nombre Completo', 'Turno', 'Grupo', 'Sem.']]
    
    for alumno in alumnos:
        nombre_completo = f"{alumno['Nombre']} {alumno['Paterno']} {alumno['Materno']}"
        datos.append([
            str(alumno['NumeroControl']),
            alumno['Curp'][:10] + '...',  # Acortar CURP
            nombre_completo[:30],
            alumno['Turno'],
            alumno['Grupo'],
            str(alumno['Semestre'])
        ])
    
    tabla = Table(datos, colWidths=[70, 80, 180, 50, 50, 40])
    tabla.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Cuerpo
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
    ]))
    
    elementos.append(tabla)
    
    # Construir PDF
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reporte_alumnos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )


# ============================================
# REPORTE GENERAL DE ALUMNOS (EXCEL)
# ============================================
@app.route('/reporte/alumnos/excel')
@login_requerido
def reporte_alumnos_excel():
    """Genera Excel con todos los alumnos registrados"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT NumeroControl, Curp, Nombre, Paterno, Materno, 
               Turno, Grupo, Semestre 
        FROM alumnos 
        ORDER BY Semestre, Grupo, Paterno
    """)
    alumnos = cursor.fetchall()
    cursor.close()
    
    # Crear DataFrame
    df = pd.DataFrame(alumnos)
    df.columns = ['No. Control', 'CURP', 'Nombre', 'Apellido Paterno', 
                  'Apellido Materno', 'Turno', 'Grupo', 'Semestre']
    
    # Crear archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Alumnos', index=False)
        
        # Ajustar ancho de columnas
        worksheet = writer.sheets['Alumnos']
        for column in worksheet.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'reporte_alumnos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )


# ============================================
# REPORTE DE DOCENTES (PDF)
# ============================================
@app.route('/reporte/docentes/pdf')
@login_requerido
def reporte_docentes_pdf():
    """Genera PDF con todos los docentes"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT no_empleado, nombre, apellido_paterno, 
               apellido_materno, materia_desarrolla 
        FROM docentes 
        ORDER BY apellido_paterno
    """)
    docentes = cursor.fetchall()
    cursor.close()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    styles = getSampleStyleSheet()
    
    titulo = Paragraph("<b>REPORTE DE DOCENTES</b>", styles['Title'])
    elementos.append(titulo)
    elementos.append(Spacer(1, 20))
    
    info = Paragraph(
        f"Generado por: {session['usuario']}<br/>Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    )
    elementos.append(info)
    elementos.append(Spacer(1, 20))
    
    datos = [['No. Empleado', 'Nombre Completo', 'Materia que Desarrolla']]
    
    for doc in docentes:
        nombre_completo = f"{doc['nombre']} {doc['apellido_paterno']} {doc['apellido_materno']}"
        datos.append([
            str(doc['no_empleado']),
            nombre_completo,
            doc['materia_desarrolla']
        ])
    
    tabla = Table(datos, colWidths=[80, 200, 180])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
    ]))
    
    elementos.append(tabla)
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reporte_docentes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )


# ============================================
# REPORTE ESTADÍSTICO GENERAL (PDF)
# ============================================
@app.route('/reporte/estadisticas/pdf')
@login_requerido
def reporte_estadisticas_pdf():
    """Genera reporte estadístico completo del sistema"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    
    # Obtener estadísticas
    cursor.execute("SELECT COUNT(*) as total FROM alumnos")
    total_alumnos = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM docentes")
    total_docentes = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM orientadores")
    total_orientadores = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM directivos")
    total_directivos = cursor.fetchone()['total']
    
    # Alumnos por semestre
    cursor.execute("""
        SELECT Semestre, COUNT(*) as cantidad 
        FROM alumnos 
        GROUP BY Semestre 
        ORDER BY Semestre
    """)
    por_semestre = cursor.fetchall()
    
    # Alumnos por turno
    cursor.execute("""
        SELECT Turno, COUNT(*) as cantidad 
        FROM alumnos 
        GROUP BY Turno
    """)
    por_turno = cursor.fetchall()
    
    # Recursos compartidos
    cursor.execute("SELECT COUNT(*) as total FROM recursos")
    total_recursos = cursor.fetchone()['total']
    
    cursor.close()
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    styles = getSampleStyleSheet()
    
    # Título principal
    titulo = Paragraph("<b>REPORTE ESTADÍSTICO GENERAL</b>", styles['Title'])
    elementos.append(titulo)
    elementos.append(Spacer(1, 30))
    
    # Totales generales
    totales_data = [
        ['Categoría', 'Cantidad'],
        ['Total de Alumnos', str(total_alumnos)],
        ['Total de Docentes', str(total_docentes)],
        ['Total de Orientadores', str(total_orientadores)],
        ['Total de Directivos', str(total_directivos)],
        ['Recursos Compartidos', str(total_recursos)]
    ]
    
    tabla_totales = Table(totales_data, colWidths=[300, 150])
    tabla_totales.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
    ]))
    
    elementos.append(tabla_totales)
    elementos.append(Spacer(1, 30))
    
    # Distribución por semestre
    elementos.append(Paragraph("<b>DISTRIBUCIÓN DE ALUMNOS POR SEMESTRE</b>", styles['Heading2']))
    elementos.append(Spacer(1, 10))
    
    semestre_data = [['Semestre', 'Cantidad de Alumnos']]
    for item in por_semestre:
        semestre_data.append([f"Semestre {item['Semestre']}", str(item['cantidad'])])
    
    tabla_semestre = Table(semestre_data, colWidths=[250, 200])
    tabla_semestre.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elementos.append(tabla_semestre)
    elementos.append(Spacer(1, 20))
    
    # Distribución por turno
    elementos.append(Paragraph("<b>DISTRIBUCIÓN DE ALUMNOS POR TURNO</b>", styles['Heading2']))
    elementos.append(Spacer(1, 10))
    
    turno_data = [['Turno', 'Cantidad de Alumnos']]
    for item in por_turno:
        turno_data.append([item['Turno'], str(item['cantidad'])])
    
    tabla_turno = Table(turno_data, colWidths=[250, 200])
    tabla_turno.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elementos.append(tabla_turno)
    elementos.append(Spacer(1, 30))
    
    # Pie de página
    footer = Paragraph(
        f"<i>Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} por {session['usuario']} ({session['rol']})</i>",
        styles['Normal']
    )
    elementos.append(footer)
    
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reporte_estadisticas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )


# ============================================
# REPORTE PERSONALIZADO POR FILTROS
# ============================================
@app.route('/reporte/personalizado', methods=['GET', 'POST'])
@login_requerido
def reporte_personalizado():
    """Permite generar reportes con filtros específicos"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    if request.method == 'POST':
        tipo_reporte = request.form.get('tipo_reporte')
        semestre = request.form.get('semestre')
        turno = request.form.get('turno')
        grupo = request.form.get('grupo')
        formato = request.form.get('formato', 'pdf')
        
        cursor = db.cursor(dictionary=True)
        
        # Construir query dinámicamente
        query = "SELECT * FROM alumnos WHERE 1=1"
        params = []
        
        if semestre:
            query += " AND Semestre = %s"
            params.append(semestre)
        if turno:
            query += " AND Turno = %s"
            params.append(turno)
        if grupo:
            query += " AND Grupo = %s"
            params.append(grupo)
        
        query += " ORDER BY Paterno"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        cursor.close()
        
        if formato == 'pdf':
            # Generar PDF con filtros
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elementos = []
            styles = getSampleStyleSheet()
            
            titulo = Paragraph("<b>REPORTE PERSONALIZADO DE ALUMNOS</b>", styles['Title'])
            elementos.append(titulo)
            elementos.append(Spacer(1, 20))
            
            # Mostrar filtros aplicados
            filtros_texto = f"<b>Filtros aplicados:</b><br/>"
            if semestre:
                filtros_texto += f"Semestre: {semestre}<br/>"
            if turno:
                filtros_texto += f"Turno: {turno}<br/>"
            if grupo:
                filtros_texto += f"Grupo: {grupo}<br/>"
            
            elementos.append(Paragraph(filtros_texto, styles['Normal']))
            elementos.append(Spacer(1, 20))
            
            # Tabla de resultados
            datos = [['No. Control', 'Nombre', 'Paterno', 'Materno', 'Grupo', 'Sem.']]
            for alumno in resultados:
                datos.append([
                    str(alumno['NumeroControl']),
                    alumno['Nombre'],
                    alumno['Paterno'],
                    alumno['Materno'],
                    alumno['Grupo'],
                    str(alumno['Semestre'])
                ])
            
            tabla = Table(datos)
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elementos.append(tabla)
            doc.build(elementos)
            buffer.seek(0)
            
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'reporte_personalizado_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            )
        
        else:  # Excel
            df = pd.DataFrame(resultados)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Resultados', index=False)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'reporte_personalizado_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
    
    return render_template('reporte_personalizado.html')


# ============================================
# SISTEMA DE REPORTES DISCIPLINARIOS

# ============================================
# RUTA: PANEL DE REPORTES DISCIPLINARIOS (DOCENTES/ORIENTADORES/DIRECTIVOS)
# ============================================
@app.route('/reportes_disciplinarios')
@login_requerido
def panel_reportes_disciplinarios():
    """Panel principal para gestionar reportes disciplinarios"""
    
    # Solo docentes, orientadores y directivos pueden acceder
    if session['rol'] not in ['Docente', 'Orientador', 'Directivo']:
        flash("No tienes permisos para acceder a esta sección", "error")
        return redirect('/')
    
    cursor = db.cursor(dictionary=True)
    
    # Obtener todos los reportes con información del alumno
    cursor.execute("""
        SELECT 
            r.id,
            r.numero_control,
            a.Nombre,
            a.Paterno,
            a.Materno,
            a.Grupo,
            a.Semestre,
            r.tipo_falta,
            r.descripcion,
            r.docente_reporta,
            r.fecha_reporte,
            r.estado,
            r.observaciones,
            (SELECT COUNT(*) FROM reportes_disciplinarios 
             WHERE numero_control = r.numero_control AND estado = 'Activo') as total_reportes
        FROM reportes_disciplinarios r
        INNER JOIN alumnos a ON r.numero_control = a.NumeroControl
        ORDER BY r.fecha_reporte DESC
    """)
    reportes = cursor.fetchall()
    
    # Obtener alumnos en riesgo (3+ reportes activos)
    cursor.execute("""
        SELECT 
            a.NumeroControl,
            a.Nombre,
            a.Paterno,
            a.Materno,
            a.Grupo,
            a.Semestre,
            COUNT(r.id) as total_reportes
        FROM alumnos a
        INNER JOIN reportes_disciplinarios r ON a.NumeroControl = r.numero_control
        WHERE r.estado = 'Activo'
        GROUP BY a.NumeroControl
        HAVING total_reportes >= 3
        ORDER BY total_reportes DESC
    """)
    alumnos_en_riesgo = cursor.fetchall()
    
    cursor.close()
    
    return render_template(
        'reportes_disciplinarios.html',
        reportes=reportes,
        alumnos_en_riesgo=alumnos_en_riesgo
    )

#  ruta /cambiar_estado_reporte

@app.route('/cambiar_estado_reporte/<int:id>', methods=['POST'])
@login_requerido
def cambiar_estado_reporte(id):
    """Cambiar el estado de un reporte (solo orientadores y directivos)"""
    
    if session['rol'] not in ['Orientador', 'Directivo']:
        flash("No tienes permisos para cambiar el estado", "error")
        return redirect('/reportes_disciplinarios')
    
    try:
        nuevo_estado = request.form.get('estado')
        observaciones = request.form.get('observaciones', '')
        
        if not nuevo_estado:
            flash("Debes seleccionar un estado", "error")
            return redirect('/reportes_disciplinarios')
        
        cursor = db.cursor()
        
        # Obtener las observaciones anteriores
        cursor.execute("SELECT observaciones FROM reportes_disciplinarios WHERE id = %s", (id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            flash("Reporte no encontrado", "error")
            cursor.close()
            return redirect('/reportes_disciplinarios')
        
        observaciones_anteriores = resultado[0] if resultado[0] else ""
        
        # Agregar nueva observación con fecha y usuario
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        nueva_observacion = f"[{fecha_actual} - {session['usuario']}] Estado cambiado a '{nuevo_estado}'. {observaciones}"
        
        # Combinar observaciones
        if observaciones_anteriores:
            observaciones_completas = f"{observaciones_anteriores}\n\n{nueva_observacion}"
        else:
            observaciones_completas = nueva_observacion
        
        # Actualizar el reporte
        cursor.execute("""
            UPDATE reportes_disciplinarios 
            SET estado = %s, observaciones = %s 
            WHERE id = %s
        """, (nuevo_estado, observaciones_completas, id))
        
        db.commit()
        cursor.close()
        
        flash(f"✅ Estado del reporte actualizado a: {nuevo_estado}", "success")
        
    except Exception as e:
        flash(f"Error al actualizar el estado: {str(e)}", "error")
        print(f"Error en cambiar_estado_reporte: {e}")
    
    return redirect('/reportes_disciplinarios')


# ============================================
# RUTA: CREAR NUEVO REPORTE DISCIPLINARIO
# ============================================
@app.route('/crear_reporte_disciplinario', methods=['GET', 'POST'])
@login_requerido
def crear_reporte_disciplinario():
    """Crear un nuevo reporte disciplinario"""
    
    if session['rol'] not in ['Docente', 'Orientador', 'Directivo']:
        flash("No tienes permisos para crear reportes", "error")
        return redirect('/')
    
    if request.method == 'POST':
        numero_control = request.form['numero_control']
        tipo_falta = request.form['tipo_falta']
        descripcion = request.form['descripcion']
        observaciones = request.form.get('observaciones', '')
        
        cursor = db.cursor()
        
        # Verificar que el alumno existe
        cursor.execute("SELECT NumeroControl FROM alumnos WHERE NumeroControl = %s", (numero_control,))
        if not cursor.fetchone():
            cursor.close()
            flash("El número de control no existe", "error")
            return redirect('/crear_reporte_disciplinario')
        
        # Insertar reporte
        sql = """INSERT INTO reportes_disciplinarios 
                 (numero_control, tipo_falta, descripcion, docente_reporta, observaciones) 
                 VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(sql, (numero_control, tipo_falta, descripcion, session['usuario'], observaciones))
        db.commit()
        
        # Verificar si el alumno ya tiene 3+ reportes (riesgo de expulsión)
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM reportes_disciplinarios 
            WHERE numero_control = %s AND estado = 'Activo'
        """, (numero_control,))
        total_reportes = cursor.fetchone()[0]
        
        cursor.close()
        
        if total_reportes >= 3:
            flash(f"⚠️ ALERTA: El alumno {numero_control} tiene {total_reportes} reportes activos. En riesgo de expulsión.", "error")
        else:
            flash("Reporte disciplinario creado exitosamente", "success")
        
        return redirect('/reportes_disciplinarios')
    
    # GET: Obtener lista de alumnos para el formulario
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT NumeroControl, Nombre, Paterno, Materno, Grupo, Semestre 
        FROM alumnos 
        ORDER BY Paterno
    """)
    alumnos = cursor.fetchall()
    cursor.close()
    
    return render_template('crear_reporte_disciplinario.html', alumnos=alumnos)


# ============================================
# RUTA: VER REPORTES DEL ALUMNO (VISTA ALUMNO)
# ============================================
# Reemplaza la ruta /mis_reportes en apps.py con este código:

@app.route('/mis_reportes')
@login_requerido
def mis_reportes():
    """Los alumnos pueden ver sus propios reportes"""
    
    if session['rol'] != 'Alumno':
        flash("Esta sección es solo para alumnos", "error")
        return redirect('/')
    
    cursor = db.cursor(dictionary=True)
    
    # El usuario del alumno es su nombre (como se loguea)
    nombre_usuario = session['usuario']
    
    # Obtener el número de control del alumno basado en su nombre
    cursor.execute("""
        SELECT NumeroControl, Nombre, Paterno, Materno, Grupo, Semestre 
        FROM alumnos 
        WHERE Nombre = %s
    """, (nombre_usuario,))
    alumno = cursor.fetchone()
    
    if not alumno:
        flash("No se encontró información del alumno", "error")
        cursor.close()
        return redirect('/alumnitos')
    
    numero_control = alumno['NumeroControl']
    
    # Obtener todos los reportes del alumno
    cursor.execute("""
        SELECT 
            id,
            tipo_falta,
            descripcion,
            docente_reporta,
            fecha_reporte,
            estado,
            observaciones
        FROM reportes_disciplinarios
        WHERE numero_control = %s
        ORDER BY fecha_reporte DESC
    """, (numero_control,))
    reportes = cursor.fetchall()
    
    # Contar reportes activos
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM reportes_disciplinarios
        WHERE numero_control = %s AND estado = 'Activo'
    """, (numero_control,))
    total_activos = cursor.fetchone()['total']
    
    cursor.close()
    
    # Determinar nivel de riesgo
    nivel_riesgo = "Bajo"
    color_riesgo = "success"
    
    if total_activos >= 3:
        nivel_riesgo = "CRÍTICO - Riesgo de Expulsión"
        color_riesgo = "danger"
    elif total_activos == 2:
        nivel_riesgo = "Alto"
        color_riesgo = "warning"
    elif total_activos == 1:
        nivel_riesgo = "Moderado"
        color_riesgo = "info"
    
    return render_template(
        'mis_reportes.html',
        alumno=alumno,
        reportes=reportes,
        total_activos=total_activos,
        nivel_riesgo=nivel_riesgo,
        color_riesgo=color_riesgo
    )


# ============================================
# RUTA: ELIMINAR REPORTE
# ============================================
@app.route('/eliminar_reporte_disciplinario/<int:id>', methods=['POST'])
@login_requerido
def eliminar_reporte_disciplinario(id):
    """Eliminar un reporte disciplinario (solo directivos)"""
    
    if session['rol'] != 'Directivo':
        return "Solo los directivos pueden eliminar reportes", 403
    
    cursor = db.cursor()
    cursor.execute("DELETE FROM reportes_disciplinarios WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    
    flash("Reporte eliminado exitosamente", "success")
    return redirect('/reportes_disciplinarios')


# ============================================
# RUTA: BUSCAR REPORTES POR ALUMNO
# ============================================
@app.route('/buscar_reportes_alumno', methods=['POST'])
@login_requerido
def buscar_reportes_alumno():
    """Buscar reportes de un alumno específico"""
    
    if session['rol'] not in ['Docente', 'Orientador', 'Directivo']:
        return "No autorizado", 403
    
    termino = request.form['termino']
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            r.id,
            r.numero_control,
            a.Nombre,
            a.Paterno,
            a.Materno,
            a.Grupo,
            a.Semestre,
            r.tipo_falta,
            r.descripcion,
            r.docente_reporta,
            r.fecha_reporte,
            r.estado,
            r.observaciones,
            (SELECT COUNT(*) FROM reportes_disciplinarios 
             WHERE numero_control = r.numero_control AND estado = 'Activo') as total_reportes
        FROM reportes_disciplinarios r
        INNER JOIN alumnos a ON r.numero_control = a.NumeroControl
        WHERE r.numero_control LIKE %s 
           OR a.Nombre LIKE %s 
           OR a.Paterno LIKE %s 
           OR a.Materno LIKE %s
        ORDER BY r.fecha_reporte DESC
    """, (f"%{termino}%", f"%{termino}%", f"%{termino}%", f"%{termino}%"))
    
    reportes = cursor.fetchall()
    
    # Obtener alumnos en riesgo
    cursor.execute("""
        SELECT 
            a.NumeroControl,
            a.Nombre,
            a.Paterno,
            a.Materno,
            a.Grupo,
            a.Semestre,
            COUNT(r.id) as total_reportes
        FROM alumnos a
        INNER JOIN reportes_disciplinarios r ON a.NumeroControl = r.numero_control
        WHERE r.estado = 'Activo'
        GROUP BY a.NumeroControl
        HAVING total_reportes >= 3
        ORDER BY total_reportes DESC
    """)
    alumnos_en_riesgo = cursor.fetchall()
    
    cursor.close()
    
    return render_template(
        'reportes_disciplinarios.html',
        reportes=reportes,
        alumnos_en_riesgo=alumnos_en_riesgo,
        termino_busqueda=termino
    )


# ============================================
# RUTA: GENERAR REPORTE PDF DE ALUMNOS EN RIESGO
# ============================================
@app.route('/reporte_alumnos_riesgo_pdf')
@login_requerido
def reporte_alumnos_riesgo_pdf():
    """Genera PDF de alumnos en riesgo de expulsión"""
    
    if session['rol'] not in ['Directivo', 'Orientador']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            a.NumeroControl,
            a.Nombre,
            a.Paterno,
            a.Materno,
            a.Grupo,
            a.Semestre,
            COUNT(r.id) as total_reportes,
            MAX(r.fecha_reporte) as ultimo_reporte
        FROM alumnos a
        INNER JOIN reportes_disciplinarios r ON a.NumeroControl = r.numero_control
        WHERE r.estado = 'Activo'
        GROUP BY a.NumeroControl
        HAVING total_reportes >= 3
        ORDER BY total_reportes DESC
    """)
    alumnos_riesgo = cursor.fetchall()
    cursor.close()
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    styles = getSampleStyleSheet()
    
    # Título
    titulo = Paragraph("<b>⚠️ REPORTE DE ALUMNOS EN RIESGO DE EXPULSIÓN</b>", styles['Title'])
    elementos.append(titulo)
    elementos.append(Spacer(1, 20))
    
    # Información
    info = Paragraph(
        f"<b>Total de alumnos en riesgo:</b> {len(alumnos_riesgo)}<br/>"
        f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>"
        f"Por: {session['usuario']} ({session['rol']})",
        styles['Normal']
    )
    elementos.append(info)
    elementos.append(Spacer(1, 20))
    
    # Tabla
    datos = [['No. Control', 'Nombre Completo', 'Grupo', 'Sem.', 'Reportes Activos', 'Último Reporte']]
    
    for alumno in alumnos_riesgo:
        nombre_completo = f"{alumno['Nombre']} {alumno['Paterno']} {alumno['Materno']}"
        datos.append([
            alumno['NumeroControl'],
            nombre_completo,
            alumno['Grupo'],
            str(alumno['Semestre']),
            str(alumno['total_reportes']),
            alumno['ultimo_reporte'].strftime('%d/%m/%Y')
        ])
    
    tabla = Table(datos, colWidths=[70, 150, 40, 35, 80, 80])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ffebee')]),
    ]))
    
    elementos.append(tabla)
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'alumnos_riesgo_expulsion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )


# ============================================
# RUTA: HISTORIAL COMPLETO DE UN ALUMNO (PDF)
# ============================================
@app.route('/historial_alumno_pdf/<numero_control>')
@login_requerido
def historial_alumno_pdf(numero_control):
    """Genera PDF con historial completo de reportes de un alumno"""
    
    if session['rol'] not in ['Directivo', 'Orientador', 'Docente']:
        return "No autorizado", 403
    
    cursor = db.cursor(dictionary=True)
    
    # Información del alumno
    cursor.execute("""
        SELECT NumeroControl, Nombre, Paterno, Materno, Grupo, Semestre, Turno
        FROM alumnos WHERE NumeroControl = %s
    """, (numero_control,))
    alumno = cursor.fetchone()
    
    # Reportes del alumno
    cursor.execute("""
        SELECT tipo_falta, descripcion, docente_reporta, fecha_reporte, estado, observaciones
        FROM reportes_disciplinarios
        WHERE numero_control = %s
        ORDER BY fecha_reporte DESC
    """, (numero_control,))
    reportes = cursor.fetchall()
    
    cursor.close()
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    styles = getSampleStyleSheet()
    
    # Título
    titulo = Paragraph("<b>HISTORIAL DISCIPLINARIO DEL ALUMNO</b>", styles['Title'])
    elementos.append(titulo)
    elementos.append(Spacer(1, 20))
    
    # Información del alumno
    info_alumno = f"""
        <b>No. Control:</b> {alumno['NumeroControl']}<br/>
        <b>Nombre:</b> {alumno['Nombre']} {alumno['Paterno']} {alumno['Materno']}<br/>
        <b>Grupo:</b> {alumno['Grupo']} | <b>Semestre:</b> {alumno['Semestre']} | <b>Turno:</b> {alumno['Turno']}<br/>
        <b>Total de reportes:</b> {len(reportes)}
    """
    elementos.append(Paragraph(info_alumno, styles['Normal']))
    elementos.append(Spacer(1, 20))
    
    # Reportes
    for i, reporte in enumerate(reportes, 1):
        datos = [
            ['Reporte #' + str(i), ''],
            ['Tipo de Falta:', reporte['tipo_falta']],
            ['Fecha:', reporte['fecha_reporte'].strftime('%d/%m/%Y %H:%M')],
            ['Reportado por:', reporte['docente_reporta']],
            ['Estado:', reporte['estado']],
            ['Descripción:', reporte['descripcion']],
        ]
        
        if reporte['observaciones']:
            datos.append(['Observaciones:', reporte['observaciones']])
        
        tabla = Table(datos, colWidths=[120, 350])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elementos.append(tabla)
        elementos.append(Spacer(1, 15))
    
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'historial_{numero_control}_{datetime.now().strftime("%Y%m%d")}.pdf'
    )


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        usuario = request.form["usuario"]
        rol = request.form["rol"]
        nueva_pass = request.form["nueva_pass"]
        confirmar_pass = request.form["confirmar_pass"]

        # Validar que las contraseñas coincidan
        if nueva_pass != confirmar_pass:
            flash("Las contraseñas no coinciden", "error")
            return redirect("/recuperar")
        
        # Validar longitud mínima
        if len(nueva_pass) < 8:
            flash("La contraseña debe tener al menos 8 caracteres", "error")
            return redirect("/recuperar")
        
        # Validar mayúscula
        if not any(c.isupper() for c in nueva_pass):
            flash("La contraseña debe contener al menos una mayúscula", "error")
            return redirect("/recuperar")
        
        # Validar número
        if not any(c.isdigit() for c in nueva_pass):
            flash("La contraseña debe contener al menos un número", "error")
            return redirect("/recuperar")

        cursor = db.cursor(dictionary=True)
        
        # Determinar la tabla según el rol
        tabla_rol = {
            'Alumno': 'alumnoslog',
            'Docente': 'docenteslog',
            'Orientador': 'orientadoreslog',
            'Directivo': 'directivoslog'
        }
        
        if rol not in tabla_rol:
            flash("Rol no válido", "error")
            cursor.close()
            return redirect("/recuperar")
        
        tabla = tabla_rol[rol]
        
        # Verificar si el usuario existe en la tabla correspondiente
        cursor.execute(f"SELECT * FROM {tabla} WHERE usuario = %s", (usuario,))
        user = cursor.fetchone()

        if not user:
            flash(f"Usuario no encontrado como {rol}", "error")
            cursor.close()
            return redirect("/recuperar")

        # Actualizar contraseña (sin encriptar para mantener compatibilidad con tu sistema actual)
        # NOTA: En producción deberías usar bcrypt para encriptar
        cursor.execute(f"UPDATE {tabla} SET password = %s WHERE usuario = %s", (nueva_pass, usuario))
        db.commit()
        cursor.close()

        # Limpiar intentos de login si existen
        ip_address = request.remote_addr
        clave_intento = f"{usuario}_{ip_address}"
        if clave_intento in intentos_login:
            del intentos_login[clave_intento]

        flash(f"✅ Contraseña actualizada correctamente para {usuario} ({rol})", "success")
        print(f"🔄 Contraseña actualizada: {usuario} | Rol: {rol}")
        
        # Redirigir al login después de 2 segundos
        return redirect(url_for("login"))
    
    return render_template("recuperar.html")


if __name__ == '__main__':
    app.run(debug=True) 