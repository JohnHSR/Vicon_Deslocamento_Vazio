import requests
import folium
import time
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os
from variaveis import ORS_TOKEN

"""
Exemplo de ORS_TOKEN

ORS_TOKEN = "DH187212791H29S81H0S821H820182018SJ1209S18S2JH09"
"""


# Geocodificação via ORS
def geocode_ors(city_name, token):
    url = 'https://api.openrouteservice.org/geocode/search'
    params = {
        'api_key': token,
        'text': city_name,
        'boundary.country': 'BR',
        'size': 1
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if not data["features"]:
        raise Exception(f'Não encontrado: {city_name}')
    coord = data["features"][0]["geometry"]["coordinates"]
    return coord[0], coord[1]  # (lon, lat)

# Consulta rota e distância (km) via ORS
def rota_ors(origem, destino):
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {'Authorization': ORS_TOKEN}
    coords = [[origem[0], origem[1]], [destino[0], destino[1]]]
    body = {'coordinates': coords}
    resp = requests.post(url, json=body, headers=headers)
    resp.raise_for_status()
    feature = resp.json()['features'][0]
    rota_coords = feature['geometry']['coordinates']
    distancia_metros = feature['properties']['summary']['distance']
    return  rota_coords, distancia_metros / 1000  # km

# Gera o mapa e adiciona info fixa no canto
def plotar_rota(origem_nome, destino_nome, origem_coord, destino_coord, rota_coords, nome_html, distancia_km=None):
    rota_latlon = [[lat, lon] for lon, lat in rota_coords]
    m = folium.Map(location=[0, 0], tiles='CartoDB Voyager', control_scale=False, zoom_control=False)
    folium.PolyLine(rota_latlon, color='red', weight=8, opacity=0.85).add_to(m)
    folium.CircleMarker(rota_latlon[0], radius=9, color='green', fill=True, fill_color='green', tooltip=f"Origem: {origem_nome}").add_to(m)
    folium.CircleMarker(rota_latlon[-1], radius=9, color='orange', fill=True, fill_color='orange', tooltip=f"Destino: {destino_nome}").add_to(m)
    m.fit_bounds(rota_latlon)
    m.save(nome_html)
    time.sleep(1)  # garante que salvou antes do print

# Tira print automático headless
def salvar_print_html(nome_html, nome_png):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    abs_path = os.path.abspath(nome_html)
    url_html = 'file:///' + abs_path.replace("\\", "/")
    time.sleep(1)  # Garante que o arquivo está salvo
    if not os.path.exists(abs_path):
        driver.quit()
        raise FileNotFoundError(f"O arquivo HTML '{nome_html}' não foi encontrado.")

    if os.path.exists(nome_png):
        os.remove(nome_png)
    driver.get(url_html)
    time.sleep(3)  # Garante que o mapa carregue
    driver.save_screenshot(nome_png)
    driver.quit()

def gerar_rota_km(cidade_origem, cidade_destino):
    
    try:
        coord_origem = geocode_ors(cidade_origem, ORS_TOKEN)
        coord_destino = geocode_ors(cidade_destino, ORS_TOKEN)
        coords, distancia_km = rota_ors(coord_origem, coord_destino)
        return distancia_km
    except Exception as e:
        cidade_origem = f"Rodoviária de {cidade_origem}"
        cidade_destino = f"Rodoviária de {cidade_destino}"
        coord_origem = geocode_ors(cidade_origem, ORS_TOKEN)
        coord_destino = geocode_ors(cidade_destino, ORS_TOKEN)
        coords, distancia_km = rota_ors(coord_origem, coord_destino)
        return distancia_km

def gerar_rota_png(cidade_origem, cidade_destino, linha):
    try:
        nome_html = f"{linha}.html"
        nome_png = f"{linha}.png"
        coord_origem = geocode_ors(cidade_origem, ORS_TOKEN)
        coord_destino = geocode_ors(cidade_destino, ORS_TOKEN)
        rota_coords, distancia_km = rota_ors(coord_origem, coord_destino)
        plotar_rota(cidade_origem, cidade_destino, coord_origem, coord_destino, rota_coords, nome_html, distancia_km)
        salvar_print_html(nome_html, nome_png)
        return distancia_km
    except:
        cidade_origem = f"Rodoviária de {cidade_origem}"
        cidade_destino = f"Rodoviária de {cidade_destino}"

        nome_html = f"{linha}.html"
        nome_png = f"{linha}.png"
        coord_origem = geocode_ors(cidade_origem, ORS_TOKEN)
        coord_destino = geocode_ors(cidade_destino, ORS_TOKEN)
        rota_coords, distancia_km = rota_ors(coord_origem, coord_destino)
        plotar_rota(cidade_origem, cidade_destino, coord_origem, coord_destino, rota_coords, nome_html, distancia_km)
        salvar_print_html(nome_html, nome_png)
        return distancia_km