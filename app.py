import http.server
import socketserver
import json
import joblib
from scipy.interpolate import griddata
import numpy as np
import requests
from datetime import datetime
import os
import random # <--- Importamos random para simular la lluvia

# --- CONFIGURACIÓN Y CARGA DEL MODELO (sin cambios) ---
PORT = 8000
MODEL_FILE = 'datos_interpolacion_horario.pkl' 
agente_interpolador = None
try:
    agente_interpolador = joblib.load(MODEL_FILE)
    print(f"✅ Agente horario '{MODEL_FILE}' cargado en memoria.")
except FileNotFoundError:
    print(f"❌ Error: El archivo del modelo '{MODEL_FILE}' no se encontró.")

# --- ¡NUEVA FUNCIÓN! Generador de Descripción Completa ---
def generar_descripcion_completa(temperatura_c, precipitacion_mm):
    
    # Clasificar temperatura
    if temperatura_c is None or isinstance(temperatura_c, str):
        desc_temp = "Temperatura no disponible"
    elif temperatura_c < 5: desc_temp = "Muy Frío"
    elif 5 <= temperatura_c < 12: desc_temp = "Frío"
    elif 12 <= temperatura_c < 18: desc_temp = "Fresco / Templado"
    elif 18 <= temperatura_c < 24: desc_temp = "Cálido / Agradable"
    else: desc_temp = "Caluroso"
        
    # Clasificar precipitación
    if precipitacion_mm is None or isinstance(precipitacion_mm, str):
        desc_precip = "" # No añade nada si no hay dato
    elif precipitacion_mm == 0:
        desc_precip = "con cielo despejado."
    elif 0 < precipitacion_mm <= 1.0:
        desc_precip = "con posibles lloviznas."
    elif 1.0 < precipitacion_mm <= 5.0:
        desc_precip = "con probabilidad de lluvia."
    else: # > 5.0
        desc_precip = "con pronóstico de lluvias intensas."
        
    temperatura_str = f"{temperatura_c:.1f}°C" if isinstance(temperatura_c, float) else "N/A"

    return f"El pronóstico es **{desc_temp}** (aprox. {temperatura_str}) {desc_precip}"


# --- FUNCIONES DE LÓGICA (sin cambios, excepto el nombre de la función de pronóstico) ---
def pronosticar_temperatura(latitud, longitud, fecha_hora_str):
    # ... (La misma lógica de 'pronostico_horario_con_tendencia' que ya tenías)
    # ...
    if agente_interpolador is None: return "Error: Modelo no cargado."
    try:
        fecha_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M')
        mes_dia_hora = fecha_obj.strftime('%m-%d %H:00:00')
        anio_futuro = fecha_obj.year
    except (ValueError, TypeError): return "Formato de fecha/hora inválido."
    temperaturas_historicas = []
    anios_historicos = []
    for anio in range(2015, 2025):
        fecha_historica_str = f"{anio}-{mes_dia_hora}"
        if fecha_historica_str in agente_interpolador:
            datos_hora = agente_interpolador[fecha_historica_str]
            puntos_conocidos = datos_hora['puntos']
            valores_conocidos = datos_hora['valores']
            punto_deseado = (longitud, latitud)
            temp_estimada = griddata(puntos_conocidos, valores_conocidos, punto_deseado, method='cubic')
            if not np.isnan(temp_estimada):
                temperaturas_historicas.append(float(temp_estimada))
                anios_historicos.append(anio)
    if len(temperaturas_historicas) < 4:
        return np.mean(temperaturas_historicas) if temperaturas_historicas else None
    else:
        pendiente, intercepto = np.polyfit(anios_historicos, temperaturas_historicas, 1)
        return (pendiente * anio_futuro) + intercepto

# ... (Las funciones obtener_ubicacion_osm y obtener_temperatura_real sin cambios) ...
def obtener_ubicacion_osm(latitud, longitud):
    # ...
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitud}&lon={longitud}"
        headers = {'User-Agent': 'MiAppClimaUniversitaria/1.0 (tu.email@ejemplo.com)'}
        respuesta = requests.get(url, headers=headers)
        datos = respuesta.json()
        if 'address' in datos:
            address = datos['address']
            return address.get('state', 'No encontrado'), address.get('country', 'No encontrado')
        return "Desconocido", "Desconocido"
    except Exception: return "Error API", "Error API"

def obtener_temperatura_real_horaria(latitud, longitud, fecha_str, hora_str):
    # ...
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={latitud}&longitude={longitud}&start_date={fecha_str}&end_date={fecha_str}&hourly=temperature_2m"
    try:
        respuesta = requests.get(url)
        datos = respuesta.json()
        if 'hourly' in datos and 'temperature_2m' in datos['hourly']:
            hora_indice = int(hora_str.split(':')[0])
            return float(datos['hourly']['temperature_2m'][hora_indice])
        return "N/A"
    except Exception: return "Error API"

# --- Servidor HTTP (con la nueva lógica de descripción) ---
class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
        
    def do_GET(self):
        # ... (código modificado para la nueva ruta /info) ...
        if self.path == '/': self.path = '/templates/index.html'
        elif self.path == '/info': self.path = '/templates/info_clima.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == '/api/get_location_data':
            # ... (código de recepción de datos sin cambios) ...
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            lat, lon, fecha, hora = data.get('latitude'), data.get('longitude'), data.get('date'), data.get('time')
            if fecha and hora: fecha_hora_completa = f"{fecha} {hora}"
            else: fecha_hora_completa = None

            # 1. Obtener pronóstico numérico de tu modelo
            temp_pronosticada = pronosticar_temperatura(lat, lon, fecha_hora_completa)
            
            # 2. SIMULACIÓN DE LLUVIA (para la descripción)
            # Cuando tengas tu modelo de lluvia, reemplazarías esta línea.
            precip_simulada = random.uniform(0, 7.0) if isinstance(temp_pronosticada, float) else None
            
            # 3. Generar la descripción completa
            descripcion_final = generar_descripcion_completa(temp_pronosticada, precip_simulada)
            
            # 4. Obtener el resto de los datos
            departamento, pais = obtener_ubicacion_osm(lat, lon)
            real = obtener_temperatura_real_horaria(lat, lon, fecha, hora)

            response_data = {
                'departamento': departamento,
                'pais': pais,
                'prediccion_modelo': descripcion_final, # ¡Enviamos la descripción completa!
                'temperatura_real': f"{real:.2f}°C" if isinstance(real, float) else str(real)
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else: self.send_error(404)

# --- Inicia el Servidor (sin cambios) ---
if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"🚀 Servidor actualizado iniciado en http://localhost:{PORT}")
        httpd.serve_forever()