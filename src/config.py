from shapely.geometry import Polygon

# Polígono exacto delimitado en el mapa:
# Occidente: Autopista Norte | Norte: Calle 163A-165 (Toberín)
# Oriente: Carrera 15 / 16B (Orquídeas) | Sur: Calle 153 (Estrella del Norte / Las Margaritas)
COORDENADAS_POLIGONO = [
    (-74.0458, 4.7438),  # Noroccidente (Autonorte con Calle 163A)
    (-74.0412, 4.7452),  # Norte (El Toberín - Calle 165)
    (-74.0365, 4.7435),  # Nororiente (Carrera 16B con Calle 164)
    (-74.0342, 4.7385),  # Oriente (Borde Babilonia / Carrera 15)
    (-74.0355, 4.7342),  # Suroriente (Calle 155 / Orquídeas sur)
    (-74.0448, 4.7338),  # Suroccidente (Autonorte con Calle 153 - Estrella del Norte)
    (-74.0468, 4.7388),  # Occidente medio (Autonorte con Calle 160)
    (-74.0458, 4.7438),  # Cierre del polígono
]

POLIGONO_ZONA = Polygon(COORDENADAS_POLIGONO)

# Bounding box amplio para la consulta inicial a APIs
BBOX = {
    "min_lon": -74.0480,
    "max_lon": -74.0330,
    "min_lat": 4.7325,
    "max_lat": 4.7465,
}

# Parámetros de alertas de oportunidad
UMBRAL_DESCUENTO_ZONA_PCT = -10.0  # Alerta si precio/m2 está >= 10% por debajo de la mediana del polígono
UMBRAL_DIAS_MERCADO = 75           # Alerta si lleva >= 75 días publicado (alta probabilidad de negociación)
UMBRAL_BAJADA_PRECIO_PCT = -5.0    # Alerta si el propietario bajó >= 5% respecto a su precio inicial
