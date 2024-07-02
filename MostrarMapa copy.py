from datetime import datetime
import requests
import json
import folium
from folium import PolyLine
import csv
from scriptSQL import run_query, calculate_time_difference
from flask import Flask, render_template_string

#Lectura de los distintos csv
csv_files = ["trips.csv", "stops.csv", "stop_times.csv", "shapes.csv", "calendar_dates.csv", "routes.csv"]
data = {}

for file in csv_files:
  with open(file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    data[file.split(".")[0]] = list(reader)

LineaNo = 15 # Linea de guagua a mostrar

app = Flask(__name__) # Crear la aplicacion Flask

@app.route('/')
def map_display():
  # Funciones para obtener los tiempos de llegada de las guaguas
  def get_tiempos(paradaNo, linea=-1):
    """
    Obtiene los tiempos de llegada de las guaguas a una parada específica.

    Args:
      paradaNo (int): El número de la parada.
      linea (int, optional): El número de la línea de guagua. Por defecto es -1, lo que significa que se obtendrán los tiempos de todas las líneas.

    Returns:
      int or list: Si se especifica una línea, devuelve el tiempo de llegada de la guagua en minutos (int). Si no se especifica una línea, devuelve una lista de pares de id y tiempo de llegada de las guaguas (list).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
           "Accept-Encoding": "gzip, deflate", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "DNT": "1", "Connection": "close", "Upgrade-Insecure-Requests": "1"}
    response = requests.get('https://movil.titsa.com/ajax/jsonguaguasparadadestino.php?IdParada=' + str(paradaNo),
                headers=headers)

    try:
      parsed_json = response.json()
      id_tiempo_pairs = []

      for tiempo in parsed_json["tiempos"]:
        id = tiempo["id"]
        tiempo_value = tiempo["tiempo"]

        if int(id) == linea:
          return int(tiempo_value)
        else:
          id_tiempo_pair = {"id": id, "tiempo": tiempo_value}
          id_tiempo_pairs.append(id_tiempo_pair)

      print("Queda mucho tiempo para la siguiente guagua, el resto de guaguas son.")
      return id_tiempo_pairs

    except json.JSONDecodeError as e:
      print("Error al analizar JSON:", e)
  # Función para obtener las paradas de una línea de guagua
  def get_paradas(LineaNo):
      """
      Obtiene una lista de códigos de paradas para una línea de transporte específica.

      Parámetros:
      - LineaNo (int): El número de la línea de transporte.

      Retorna:
      - codigo_list (list): Una lista de códigos de paradas.

      """
      headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
             "Accept-Encoding": "gzip, deflate", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
             "DNT": "1", "Connection": "close", "Upgrade-Insecure-Requests": "1"}
      response = requests.get(
        'https://titsa.com/ajax/xItinerario.php?c=1234&id_linea=' + str(LineaNo) + '&id_trayecto=' + str(11),
        headers=headers)

      try:
        parsed_json = response.json()
        codigo_list = [int(parada["codigo"]) for parada in parsed_json["paradas"]]
        return codigo_list

      except json.JSONDecodeError as e:
        print("Error parsing JSON:", e)
  # Función para trazar la ruta de una línea de guagua en un mapa
  def plot_shape_on_map(trip_shapes):
    """
    Dibuja las formas de los viajes en un mapa utilizando la biblioteca Folium.

    Args:
      trip_shapes (list): Una lista de diccionarios que representan las formas de los viajes.
        Cada diccionario debe contener las claves 'shape_id', 'shape_pt_sequence', 'shape_pt_lat' y 'shape_pt_lon'.

    Returns:
      folium.Map: Un objeto de mapa de Folium que muestra las formas de los viajes dibujadas en el mapa.
    """
    m = folium.Map(location=[28.4581, -16.2955], zoom_start=12)

    for shape in trip_shapes:
      shape_id = shape['shape_id']
      coordinates = []

      sorted_shapes = sorted(trip_shapes, key=lambda x: int(x['shape_pt_sequence']))
      for sorted_shape in sorted_shapes:
        if sorted_shape['shape_id'] == shape_id:
          coordinates.append((float(sorted_shape['shape_pt_lat']), float(sorted_shape['shape_pt_lon'])))

      polyline = PolyLine(coordinates, color='blue', weight=2, opacity=0.8)
      m.add_child(polyline)

    return m
  # Función para trazar las paradas de una línea de guagua en un mapa con marcadores de tiempo
  def add_stop_markers_with_times(trip_stop_times, stops_data, m, tiempos):
    """
    Agrega marcadores de paradas con tiempos estimados de llegada al mapa.

    Parámetros:
    - trip_stop_times: Lista de diccionarios que contiene información de los tiempos de llegada a las paradas de un viaje.
    - stops_data: Lista de diccionarios que contiene información de las paradas.
    - m: Objeto de mapa en el que se agregarán los marcadores.
    - tiempos: Lista de tiempos estimados de llegada a cada parada.

    Retorna:
    None
    """
    stop_info_dict = {stop['stop_id']: stop for stop in stops_data}

    stop_time_index = 0
    for stop_time in trip_stop_times:
      stop_id = stop_time['stop_id']
      arrival_time = stop_time['arrival_time']

      stop_info = stop_info_dict.get(stop_id)
      if not stop_info:
        print("Error: Información de la parada no encontrada para", stop_id)
        continue

      stop_lat = float(stop_info['stop_lat'])
      stop_lon = float(stop_info['stop_lon'])
      timedif = calculate_time_difference(stop_time['arrival_time'])
      if timedif > 100:
        timedif = timedif - 1440

      color_mapping = {'early': 'green', 'on_time': 'orange', 'late': 'red'}
      status = 'early' if tiempos[stop_time_index] < timedif else 'on_time' if (
          tiempos[stop_time_index] - timedif) == 0 else 'late'
      marker_color = color_mapping[status]

      folium.Marker(
        location=[stop_lat, stop_lon],
        popup=f"Parada:{stop_id} \nLlegada:{arrival_time} \nTiempo estimado de llegada: {tiempos[stop_time_index]} min\nTiempo estimado según horario: {timedif} min",
        icon=folium.Icon(icon='info-sign', color=marker_color, icon_color='white')
      ).add_to(m)
      stop_time_index += 1

  # Obtener paradas de la línea especificada (LineaNo)
  paradas = get_paradas(LineaNo)  

  # Obtener tiempos estimados para cada parada, convirtiendo el código de parada a entero antes de la consulta
  tiempo_est = [get_tiempos(int(i), LineaNo) for i in paradas]  

  # Obtener la fecha actual en el formato YYYYMMDD (necesario para consultar el calendario de servicios)
  specific_date = datetime.now().strftime("%Y%m%d")  
  service_ids = [calendar_date['service_id'] for calendar_date in data['calendar_dates'] if calendar_date['date'] == specific_date]

  # Verificar si se encontraron servicios para la fecha
  if not service_ids:  
      print("No se encontraron servicios para la fecha indicada.")  

  # Convertir el número de línea a cadena para buscar el ID de ruta correspondiente
  route_short_name = str(LineaNo)  
  route_id = next((route['route_id'] for route in data['routes'] if route['route_short_name'] == route_short_name), None)

  # Verificar si se encontró el ID de ruta
  if not route_id:  
      print("Error: No se encontró el ID de ruta para el número de línea proporcionado.") 

  # Ejecutar la consulta SQL para obtener los tiempos de parada del viaje (asumimos que tienes una función 'run_query' definida en otro lugar)
  trip_stop_times = run_query()  

  # Buscar el primer viaje que coincida con el ID de ruta y los IDs de servicio disponibles
  for trip in data['trips']:  
      if trip['route_id'] == route_id and trip['service_id'] in service_ids:
          first_trip_id = trip['trip_id']
          first_shape_id = trip['shape_id']
          break  # Detener la búsqueda al encontrar el primer viaje que coincide

  # Obtener la información de la forma (ruta) del viaje
  trip_shapes = [shape for shape in data['shapes'] if shape['shape_id'] == first_shape_id]

  # Verificar si se encontraron datos de forma para el ID de forma
  if not trip_shapes:  
      print("Error: No se encontraron datos de forma para el ID de forma proporcionado.")  

  # Trazar la ruta en el mapa
  trip_map = plot_shape_on_map(trip_shapes)  

  # Añadir marcadores de paradas con tiempos estimados al mapa
  add_stop_markers_with_times(trip_stop_times, data['stops'], trip_map, tiempo_est)  

  # Obtener el HTML del mapa para mostrarlo en la aplicación Flask
  map_html = trip_map._repr_html_() 

  return render_template_string("""
    <html>
      <head>
        <script>
          setTimeout(function(){
            window.location.reload(1);
          }, 60000);
        </script>
      </head>
      <body>
        {{map_html | safe}}
      </body>
    </html>
  """, map_html=map_html)

if __name__ == '__main__':
  app.run(debug=True)
