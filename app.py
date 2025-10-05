# app.py
import os
import json
import random
from datetime import datetime

import joblib
import numpy as np
from scipy.interpolate import griddata
import requests

from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
import bcrypt

# ---------------- CONFIGURACIÓN ----------------
PORT = 8000
MODEL_FILE = 'datos_interpolacion_horario.pkl'
agente_interpolador = None

# Intentamos cargar el modelo si existe
if os.path.exists(MODEL_FILE):
    try:
        agente_interpolador = joblib.load(MODEL_FILE)
        print(f"✅ Agente horario '{MODEL_FILE}' cargado en memoria.")
    except Exception as e:
        print(f"❌ Error cargando el modelo '{MODEL_FILE}': {e}")
else:
    print(f"❌ El archivo del modelo '{MODEL_FILE}' no se encontró. (Se usará comportamiento degradado)")

# ---------------- FUNCIONES AUXILIARES ----------------
def generar_descripcion_completa(temperatura_c, precipitacion_mm):
    # Clasificar temperatura
    if temperatura_c is None or isinstance(temperatura_c, str):
        desc_temp = "Temperatura no disponible"
    elif temperatura_c < 5:
        desc_temp = "Muy Frío"
    elif 5 <= temperatura_c < 12:
        desc_temp = "Frío"
    elif 12 <= temperatura_c < 18:
        desc_temp = "Fresco / Templado"
    elif 18 <= temperatura_c < 24:
        desc_temp = "Cálido / Agradable"
    else:
        desc_temp = "Caluroso"

    # Clasificar precipitación
    if precipitacion_mm is None or isinstance(precipitacion_mm, str):
        desc_precip = ""  # No añade nada si no hay dato
    elif precipitacion_mm == 0:
        desc_precip = "con cielo despejado."
    elif 0 < precipitacion_mm <= 1.0:
        desc_precip = "con posibles lloviznas."
    elif 1.0 < precipitacion_mm <= 5.0:
        desc_precip = "con probabilidad de lluvia."
    else:  # > 5.0
        desc_precip = "con pronóstico de lluvias intensas."

    temperatura_str = f"{temperatura_c:.1f}°C" if isinstance(temperatura_c, (float, int)) else "N/A"
    # No usamos markdown en la API (devuelve texto plano).
    return f"El pronóstico es {desc_temp} (aprox. {temperatura_str}) {desc_precip}".strip()

def pronosticar_temperatura(latitud, longitud, fecha_hora_str):
    """
    Usa el diccionario agente_interpolador con claves 'YYYY-mm-dd HH:00:00' que contienen:
      {'puntos': [(lon,lat), ...], 'valores': [temp1, temp2, ...]}
    Devuelve float (temperatura estimada) o None si no hay datos.
    """
    if agente_interpolador is None:
        return None

    try:
        fecha_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M')
        mes_dia_hora = fecha_obj.strftime('%m-%d %H:00:00')
        anio_futuro = fecha_obj.year
    except Exception:
        return None

    temperaturas_historicas = []
    anios_historicos = []
    for anio in range(2015, 2025):
        clave = f"{anio}-{mes_dia_hora}"
        if clave in agente_interpolador:
            datos_hora = agente_interpolador[clave]
            puntos_conocidos = datos_hora.get('puntos')
            valores_conocidos = datos_hora.get('valores')
            if puntos_conocidos and valores_conocidos:
                punto_deseado = (longitud, latitud)
                try:
                    temp_estimada = griddata(puntos_conocidos, valores_conocidos, punto_deseado, method='cubic')
                    if temp_estimada is not None and not np.isnan(temp_estimada):
                        temperaturas_historicas.append(float(temp_estimada))
                        anios_historicos.append(anio)
                except Exception:
                    # si falla la interpolación para este año, continuamos
                    continue

    if not temperaturas_historicas:
        return None
    if len(temperaturas_historicas) < 4:
        return float(np.mean(temperaturas_historicas))
    pendiente, intercepto = np.polyfit(anios_historicos, temperaturas_historicas, 1)
    return float((pendiente * anio_futuro) + intercepto)

def obtener_ubicacion_osm(latitud, longitud):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitud}&lon={longitud}"
        headers = {'User-Agent': 'EcoWeatherApp/1.0 (contacto@ejemplo.com)'}
        respuesta = requests.get(url, headers=headers, timeout=10)
        datos = respuesta.json()
        if 'address' in datos:
            address = datos['address']
            return address.get('state', 'Desconocido'), address.get('country', 'Desconocido')
        return "Desconocido", "Desconocido"
    except Exception:
        return "Error API", "Error API"

def obtener_temperatura_real_horaria(latitud, longitud, fecha_str, hora_str):
    try:
        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={latitud}&longitude={longitud}"
            f"&start_date={fecha_str}&end_date={fecha_str}&hourly=temperature_2m"
        )
        respuesta = requests.get(url, timeout=10)
        datos = respuesta.json()
        if 'hourly' in datos and 'temperature_2m' in datos['hourly']:
            hora_indice = int(hora_str.split(':')[0])
            temps = datos['hourly']['temperature_2m']
            if 0 <= hora_indice < len(temps):
                return float(temps[hora_indice])
        return None
    except Exception:
        return None

# ---------------- FLASK APP ----------------
app = Flask(__name__, static_folder='static', template_folder='templates')

# ---------------- DB ----------------
def conectar():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="login_db",
        autocommit=False
    )

# ---------------- RUTAS ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inicio')
def inicio():
    return render_template('inicio.html')

@app.route('/info')
def info_clima():
    return render_template('info_clima.html')

@app.route('/pronostico')
def pronostico():
    return render_template('pronost.html')

@app.route('/login')
def iniciosesion():
    return render_template('login/login.html')

@app.route('/registro')
def registrousu():
    return render_template('login/registro.html')

# ----- API que consumirá tu JS (POST JSON) -----
@app.route('/api/get_location_data', methods=['POST'])
def api_get_location_data():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON inválido'}), 400

    try:
        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))
    except Exception:
        return jsonify({'error': 'Latitud/Longitud inválidas'}), 400

    fecha = data.get('date')  # 'YYYY-MM-DD'
    hora = data.get('time')   # 'HH:MM'
    fecha_hora_completa = f"{fecha} {hora}" if fecha and hora else None

    # 1) Predicción numérica (modelo)
    temp_pronosticada = pronosticar_temperatura(lat, lon, fecha_hora_completa) if fecha_hora_completa else None

    # 2) Simulación de precipitación (temporal)
    precip_simulada = random.uniform(0, 7.0) if isinstance(temp_pronosticada, (float, int)) else None

    # 3) Generar descripción textual
    descripcion_final = generar_descripcion_completa(temp_pronosticada, precip_simulada)

    # 4) Obtener ubicación y temperatura real de archivo
    departamento, pais = obtener_ubicacion_osm(lat, lon)
    temperatura_real = obtener_temperatura_real_horaria(lat, lon, fecha, hora) if fecha and hora else None

    response_data = {
        'departamento': departamento,
        'pais': pais,
        'prediccion_modelo': descripcion_final,
        'temperatura_real': f"{temperatura_real:.2f}°C" if isinstance(temperatura_real, (float, int)) else "N/A"
    }
    return jsonify(response_data), 200

# ---------------- AUTH / USUARIOS ----------------
@app.route('/login', methods=['POST'])
def login():
    usuario = request.form.get('username')
    contraseña = request.form.get('password')
    if not usuario or not contraseña:
        return render_template('login/login.html', mensaje="❌ Complete usuario y contraseña.")

    conexion = None
    try:
        conexion = conectar()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (usuario,))
        usuario_db = cursor.fetchone()
        cursor.close()
        if usuario_db and 'password' in usuario_db:
            stored = usuario_db['password']
            # stored debe ser string; bcrypt espera bytes
            if isinstance(stored, str):
                stored_bytes = stored.encode('utf-8')
            else:
                stored_bytes = stored
            if bcrypt.checkpw(contraseña.encode('utf-8'), stored_bytes):
                mensaje = f"✅ Bienvenido, {usuario}"
            else:
                mensaje = "❌ Usuario o contraseña incorrectos."
        else:
            mensaje = "❌ Usuario o contraseña incorrectos."
    except Exception as e:
        mensaje = f"⚠️ Error en la conexión: {e}"
    finally:
        if conexion:
            conexion.close()
    return render_template('login/login.html', mensaje=mensaje)

@app.route('/registro')
def registro():
    return render_template('login/registro.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    usuario = request.form.get('username')
    contraseña = request.form.get('password')
    if not usuario or not contraseña:
        return render_template('login/registro.html', mensaje="❌ Complete usuario y contraseña.")

    hashed = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt())  # bytes
    # convertimos a str para almacenar en DB (utf-8)
    hashed_str = hashed.decode('utf-8')

    conexion = None
    try:
        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (%s, %s)", (usuario, hashed_str))
        conexion.commit()
        cursor.close()
        mensaje = "✅ Usuario registrado correctamente."
    except mysql.connector.Error as err:
        # podrías comprobar err.errno para detectar duplicados (código varía según configuración)
        mensaje = "⚠️ El usuario ya existe o hubo un error en la inserción."
    except Exception as e:
        mensaje = f"⚠️ Error inesperado: {e}"
    finally:
        if conexion:
            conexion.close()

    return render_template('login/registro.html', mensaje=mensaje)

@app.route('/cambiar_password')
def cambiar_password():
    return render_template('login/cambiar_password.html')

@app.route('/actualizar_password', methods=['POST'])
def actualizar_password():
    usuario = request.form.get('username')
    actual = request.form.get('old_password')
    nueva = request.form.get('new_password')
    if not usuario or not actual or not nueva:
        return render_template('login/cambiar_password.html', mensaje="❌ Complete todos los campos.")

    conexion = None
    try:
        conexion = conectar()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (usuario,))
        usuario_db = cursor.fetchone()

        if usuario_db and 'password' in usuario_db:
            stored = usuario_db['password']
            stored_bytes = stored.encode('utf-8') if isinstance(stored, str) else stored
            if bcrypt.checkpw(actual.encode('utf-8'), stored_bytes):
                hashed_nueva = bcrypt.hashpw(nueva.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                update_cursor = conexion.cursor()
                update_cursor.execute("UPDATE usuarios SET password = %s WHERE username = %s", (hashed_nueva, usuario))
                conexion.commit()
                update_cursor.close()
                mensaje = "✅ Contraseña actualizada correctamente."
            else:
                mensaje = "❌ Contraseña actual incorrecta."
        else:
            mensaje = "❌ Usuario no encontrado."
        cursor.close()
    except Exception as e:
        mensaje = f"⚠️ Error en la operación: {e}"
    finally:
        if conexion:
            conexion.close()

    return render_template('login/cambiar_password.html', mensaje=mensaje)

# ---------------- EJECUCIÓN ----------------
if __name__ == '__main__':
    # Ejecutamos Flask en el puerto 8000 (igual que antes)
    app.run(debug=True, port=PORT)
