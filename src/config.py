"""Configuración compatible con el código existente y parametrizada por zona."""
import json
from pathlib import Path

from shapely.geometry import Polygon

RUTA_ZONAS = Path(__file__).resolve().parents[1] / "config" / "zonas.json"
with RUTA_ZONAS.open(encoding="utf-8") as archivo:
    CONFIG_ZONAS = json.load(archivo)["zonas"]

ZONAS = {
    clave: {
        **zona,
        "id": clave,
        # El archivo expresa latitud,longitud; Shapely requiere x=longitud,y=latitud.
        "poligono": Polygon([(lon, lat) for lat, lon in zona["coordenadas_lat_lon"]]),
    }
    for clave, zona in CONFIG_ZONAS.items()
}

# Alias legado para consumidores que todavía procesan únicamente Rincón.
COORDENADAS_POLIGONO = [(lon, lat) for lat, lon in ZONAS["rincon"]["coordenadas_lat_lon"]]
POLIGONO_ZONA = ZONAS["rincon"]["poligono"]
BBOX = {
    "min_lon": min(lon for lon, lat in COORDENADAS_POLIGONO),
    "max_lon": max(lon for lon, lat in COORDENADAS_POLIGONO),
    "min_lat": min(lat for lon, lat in COORDENADAS_POLIGONO),
    "max_lat": max(lat for lon, lat in COORDENADAS_POLIGONO),
}

UMBRAL_DESCUENTO_ZONA_PCT = -10.0
UMBRAL_DIAS_MERCADO = 75
UMBRAL_BAJADA_PRECIO_PCT = -5.0
DESCUENTO_CIERRE_BASE_PCT = 5.0
RANGO_CIERRE_PCT = (3.0, 7.0)
TOLERANCIA_AREA_M2 = 2.0
TOLERANCIA_PRECIO_HUELLA_PCT = 5.0
PRECISION_COORDENADAS_HUELLA = 4
FACTOR_ATIPICO_PRECIO_M2 = (0.5, 1.8)
MINIMOS_CAPTURA_PORTAL = {"Fincaraiz": 5, "Metrocuadrado": 3}
