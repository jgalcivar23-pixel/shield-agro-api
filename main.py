import ee
import google.auth
from flask import Flask, request, jsonify

app = Flask(__name__)

def initialize_ee():
    credentials, project = google.auth.default()
    ee.Initialize(credentials=credentials, project=project)

def analisis_fitosanitario(temp, humedad, lluvia):
    riesgo_monilia = 0
    alertas_monilia = []
    if 22 <= temp <= 28:
        riesgo_monilia += 40
        alertas_monilia.append("🌡️ Temperatura óptima de esporulación")
    if humedad >= 85:
        riesgo_monilia += 40
        alertas_monilia.append("💧 HR crítica: germinación acelerada")
    if lluvia > 5:
        riesgo_monilia += 20
        alertas_monilia.append("🌧️ Lluvia: dispersión de inóculo activa")

    riesgo_mazorca = 0
    alertas_mazorca = []
    if temp >= 24 and lluvia > 10:
        riesgo_mazorca += 50
        alertas_mazorca.append("⚠️ Condiciones óptimas para Phytophthora")
    if humedad >= 90:
        riesgo_mazorca += 30
        alertas_mazorca.append("💧 Saturación favorece zoosporangios")
    if lluvia > 20:
        riesgo_mazorca += 20
        alertas_mazorca.append("🌧️ Diseminación por salpique crítica")

    def nivel(score):
        if score >= 70: return "ALTO 🔴"
        elif score >= 40: return "MODERADO 🟡"
        return "BAJO 🟢"

    return {
        'monilia': {
            'riesgo_score': riesgo_monilia,
            'nivel': nivel(riesgo_monilia),
            'alertas': alertas_monilia,
            'recomendacion': "Fungicida preventivo + poda sanitaria" if riesgo_monilia >= 70 else "Monitoreo semanal"
        },
        'mazorca_negra': {
            'riesgo_score': riesgo_mazorca,
            'nivel': nivel(riesgo_mazorca),
            'alertas': alertas_mazorca,
            'recomendacion': "Drenaje urgente + cobre sistémico" if riesgo_mazorca >= 70 else "Revisar drenajes y sombra"
        }
    }

@app.route('/analizar', methods=['POST', 'OPTIONS'])
def analizar():
    if request.method == 'OPTIONS':
        headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type'}
        return ('', 204, headers)
    headers = {'Access-Control-Allow-Origin': '*'}
    try:
        initialize_ee()
        data = request.get_json()
        lat = float(data.get('lat', -0.802))
        lon = float(data.get('lon', -77.816))
        humedad = float(data.get('humedad', 80))
        lluvia = float(data.get('lluvia', 5))

        punto = ee.Geometry.Point([lon, lat])
        buffer = punto.buffer(30000)
        lst = (ee.ImageCollection('MODIS/061/MOD11A2').filterDate('2024-06-01', '2025-04-01').filterBounds(buffer).select('LST_Day_1km').mean().multiply(0.02).subtract(273.15))
        lst_hist = (ee.ImageCollection('MODIS/061/MOD11A2').filterDate('2020-01-01', '2023-12-31').select('LST_Day_1km').mean().multiply(0.02).subtract(273.15))
        anomalia = lst.subtract(lst_hist).clip(buffer)
        stats = anomalia.reduceRegion(reducer=ee.Reducer.percentile([5, 95]), geometry=buffer, scale=1000, maxPixels=1e9).getInfo()
        min_val = stats.get('LST_Day_1km_p5', -2)
        max_val = stats.get('LST_Day_1km_p95', 2)
        temp_zona = lst.reduceRegion(reducer=ee.Reducer.mean(), geometry=buffer, scale=1000).getInfo().get('LST_Day_1km', 25)
        visParams = {'min': min_val, 'max': max_val, 'palette': ['313695','4575b4','abd9e9','ffffbf','fdae61','f46d43','a50026']}
        tile_url = anomalia.getMapId(visParams)['tile_fetcher'].url_format
        return (jsonify({'tile_url': tile_url, 'temperatura_zona': round(temp_zona, 1), 'rango_anomalia': {'min': round(min_val,2), 'max': round(max_val,2)}, 'analisis_fitosanitario': analisis_fitosanitario(temp_zona, humedad, lluvia), 'coordenadas': {'lat': lat, 'lon': lon}}), 200, headers)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500, headers)

@app.route('/')
def home():
    return jsonify({'status': 'Shield Agro API activa ✅'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
