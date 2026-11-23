"""
Servidor Flask de Cumbre Digital CO 2026.

Registra asistentes en la base SQLite evento.db y muestra:
  GET  /                        → formulario de registro
  POST /registro                → valida y guarda un asistente
  GET  /confirmacion/<numero>   → pantalla de registro exitoso
  GET  /admin                   → listado de asistentes
"""

import os
import re
import sqlite3
import uuid

from flask import Flask, abort, g, redirect, render_template, request, url_for

# ============================================
# Configuración
# ============================================
CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))

# Ruta de la base de datos: evento.db en la raíz del proyecto, salvo que
# la variable de entorno DB_PATH indique otra (útil en Render con disco persistente)
RUTA_BD = os.environ.get("DB_PATH", os.path.join(CARPETA_BASE, "evento.db"))

AREAS = ["Tecnología", "Marketing", "Negocios", "Emprendimiento"]

# Misma expresión regular que usa validacion.js en el navegador
REGEX_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

LONGITUD_MAXIMA = {"nombre": 100, "email": 254, "empresa": 100}

app = Flask(__name__)


# ============================================
# Base de datos
# ============================================
def obtener_bd():
    """Devuelve la conexión SQLite de la petición actual (la crea si no existe)."""
    if "bd" not in g:
        g.bd = sqlite3.connect(RUTA_BD)
        g.bd.row_factory = sqlite3.Row
    return g.bd


@app.teardown_appcontext
def cerrar_bd(_error):
    """Cierra la conexión al terminar cada petición."""
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def init_db():
    """Crea la tabla de asistentes si todavía no existe."""
    areas_sql = ", ".join(f"'{area}'" for area in AREAS)
    with sqlite3.connect(RUTA_BD) as bd:
        bd.execute(f"""
            CREATE TABLE IF NOT EXISTS asistentes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_registro TEXT    NOT NULL UNIQUE,
                nombre          TEXT    NOT NULL,
                email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                empresa         TEXT    NOT NULL,
                area            TEXT    NOT NULL CHECK (area IN ({areas_sql})),
                fecha_registro  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
    # El bloque "with" confirma la transacción pero no cierra la conexión
    bd.close()


# ============================================
# Validación
# ============================================
def validar(datos):
    """Valida los datos del formulario. Devuelve un diccionario campo → mensaje de error."""
    errores = {}

    if not datos["nombre"]:
        errores["nombre"] = "El nombre completo es obligatorio."
    if not datos["email"]:
        errores["email"] = "El email es obligatorio."
    elif not REGEX_EMAIL.match(datos["email"]):
        errores["email"] = "Ingresa un email con formato válido (ej. nombre@empresa.com)."
    if not datos["empresa"]:
        errores["empresa"] = "La empresa u organización es obligatoria."
    if not datos["area"]:
        errores["area"] = "Selecciona un área de interés."
    elif datos["area"] not in AREAS:
        errores["area"] = "El área seleccionada no es válida."

    for campo, maximo in LONGITUD_MAXIMA.items():
        if campo not in errores and len(datos[campo]) > maximo:
            errores[campo] = f"Este campo admite como máximo {maximo} caracteres."

    return errores


def email_ya_registrado(email):
    """True si ya existe un asistente con ese email (sin distinguir mayúsculas)."""
    fila = obtener_bd().execute(
        "SELECT 1 FROM asistentes WHERE email = ?", (email,)
    ).fetchone()
    return fila is not None


MENSAJE_EMAIL_DUPLICADO = "Este email ya está registrado."


# ============================================
# Rutas
# ============================================
@app.get("/")
def inicio():
    """Muestra el formulario vacío."""
    return render_template("index.html", datos={}, errores={}, areas=AREAS)


@app.post("/registro")
def registrar():
    """Valida y guarda un asistente; luego redirige a la confirmación."""
    datos = {
        "nombre": request.form.get("nombre", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "empresa": request.form.get("empresa", "").strip(),
        "area": request.form.get("area", "").strip(),
    }

    errores = validar(datos)
    if "email" not in errores and email_ya_registrado(datos["email"]):
        errores["email"] = MENSAJE_EMAIL_DUPLICADO

    if errores:
        return render_template("index.html", datos=datos, errores=errores, areas=AREAS), 400

    bd = obtener_bd()
    try:
        # Se inserta con un número temporal y, dentro de la misma transacción,
        # se reemplaza por REG-XXXX calculado a partir del id asignado.
        cursor = bd.execute(
            """INSERT INTO asistentes (numero_registro, nombre, email, empresa, area)
               VALUES (?, ?, ?, ?, ?)""",
            ("TMP-" + uuid.uuid4().hex, datos["nombre"], datos["email"],
             datos["empresa"], datos["area"]),
        )
        numero = f"REG-{cursor.lastrowid:04d}"
        bd.execute(
            "UPDATE asistentes SET numero_registro = ? WHERE id = ?",
            (numero, cursor.lastrowid),
        )
        bd.commit()
    except sqlite3.IntegrityError:
        # Caso raro: otra petición registró el mismo email al mismo tiempo
        bd.rollback()
        errores["email"] = MENSAJE_EMAIL_DUPLICADO
        return render_template("index.html", datos=datos, errores=errores, areas=AREAS), 400

    # Post/Redirect/Get: recargar la confirmación no duplica el registro
    return redirect(url_for("confirmacion", numero_registro=numero))


@app.get("/confirmacion/<numero_registro>")
def confirmacion(numero_registro):
    """Muestra los datos del asistente recién registrado."""
    asistente = obtener_bd().execute(
        "SELECT numero_registro, nombre, area FROM asistentes WHERE numero_registro = ?",
        (numero_registro,),
    ).fetchone()
    if asistente is None:
        abort(404)
    return render_template("confirmacion.html", asistente=asistente)


@app.get("/admin")
def admin():
    """Lista todos los asistentes con un conteo por área."""
    bd = obtener_bd()
    asistentes = bd.execute(
        """SELECT numero_registro, nombre, email, empresa, area, fecha_registro
           FROM asistentes ORDER BY id DESC"""
    ).fetchall()

    # Conteo por área, incluyendo las que aún no tienen inscritos
    conteo_areas = {area: 0 for area in AREAS}
    for fila in bd.execute("SELECT area, COUNT(*) AS total FROM asistentes GROUP BY area"):
        conteo_areas[fila["area"]] = fila["total"]

    return render_template("admin.html", asistentes=asistentes, conteo_areas=conteo_areas)


# ============================================
# Páginas de error en español
# ============================================
@app.errorhandler(404)
def no_encontrado(_error):
    return render_template(
        "error.html",
        titulo="Página no encontrada",
        mensaje="La página o el registro que buscas no existe.",
    ), 404


@app.errorhandler(500)
def error_interno(_error):
    return render_template(
        "error.html",
        titulo="Error del servidor",
        mensaje="Ocurrió un problema inesperado. Intenta de nuevo en unos minutos.",
    ), 500


# Se ejecuta al importar el módulo (también con gunicorn en Render)
init_db()

if __name__ == "__main__":
    app.run(debug=True)
