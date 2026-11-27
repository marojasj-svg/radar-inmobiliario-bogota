"""Búsquedas estructuradas de API.SH para FincaRaíz y Metrocuadrado."""
import json
import os

import requests

API_BASE = "https://api.api.sh"
TIMEOUT_SEGUNDOS = 60
PAGINAS_MAXIMAS = 10


def _coordenadas(obj):
    """Extrae coordenadas publicadas del anuncio o su bloque raw, sin usar POI cercanos."""
    if isinstance(obj, dict):
        lat = obj.get("latitude") or obj.get("lat")
        lon = obj.get("longitude") or obj.get("lon") or obj.get("lng")
        try:
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        except (TypeError, ValueError):
            pass
        for clave, valor in obj.items():
            if str(clave).lower() in {
                "nearby", "nearby_places", "poi", "similar", "photos", "images", "advertiser"
            }:
                continue
            resultado = _coordenadas(valor)
            if resultado != (None, None):
                return resultado
    elif isinstance(obj, list):
        for valor in obj:
            resultado = _coordenadas(valor)
            if resultado != (None, None):
                return resultado
    elif isinstance(obj, str):
        texto = obj.strip()
        if texto.startswith("{") or texto.startswith("["):
            try:
                return _coordenadas(json.loads(texto))
            except json.JSONDecodeError:
                pass
    return None, None


def buscar(portal, zona):
    """Devuelve anuncios originales y estado de búsqueda del portal."""
    clave = os.getenv("RADAR_DATA_API_KEY")
    if not clave:
        return [], {
            "consultas": 0,
            "consultas_ok": 0,
            "capturados": 0,
            "captura_confiable": False,
            "proveedor": "API.SH",
            "errores": ["Falta configurar el secreto RADAR_DATA_API_KEY en GitHub Actions."],
        }

    if portal == "Fincaraiz":
        endpoint = f"{API_BASE}/fincaraiz/v1/search"
        lugares = zona["barrios_fincaraiz"]
    else:
        endpoint = f"{API_BASE}/metrocuadrado/v1/search"
        lugares = [zona["busqueda_metrocuadrado"].replace(" bogota", "").strip()]

    headers = {"x-api-key": clave}
    anuncios, errores, advertencias = {}, [], []
    consultas = consultas_ok = 0
    truncado = False

    for lugar in lugares:
        pagina = 1
        while pagina <= PAGINAS_MAXIMAS:
            consultas += 1
            params = (
                {
                    "transaction": "sale",
                    "property_type": "apartment",
                    "location": lugar,
                    "page": pagina,
                    "raw": "true",
                }
                if portal == "Fincaraiz"
                else {
                    "deal": "venta",
                    "type": "apartamento",
                    "city": "bogota",
                    "neighborhood": lugar,
                    "page": pagina,
                    "raw": "true",
                }
            )
            try:
                respuesta = requests.get(
                    endpoint, params=params, headers=headers, timeout=TIMEOUT_SEGUNDOS
                )
                if respuesta.status_code == 404:
                    consultas_ok += 1
                    advertencias.append(f"Sin anuncios para la ubicación '{lugar}'.")
                    break
                respuesta.raise_for_status()
                data = respuesta.json()
                if not isinstance(data, dict):
                    raise ValueError("La respuesta del proveedor no es un objeto JSON.")
                if data.get("success") is False:
                    raise ValueError(data.get("error", "Error reportado por API.SH"))
                lista = data.get("listings") or data.get("results") or []
                if not isinstance(lista, list) or any(not isinstance(item, dict) for item in lista):
                    raise ValueError("La respuesta no contiene una lista válida de anuncios.")
                consultas_ok += 1
                for item in lista:
                    clave_anuncio = str(item.get("id") or item.get("code") or item.get("url") or "")
                    if clave_anuncio:
                        lat, lon = _coordenadas(item)
                        if lat is not None and lon is not None:
                            item["latitude"], item["longitude"] = lat, lon
                        anuncios[clave_anuncio] = item
                siguiente = data.get("next_page")
                if not siguiente or not lista:
                    break
                if pagina >= PAGINAS_MAXIMAS:
                    truncado = True
                    advertencias.append(f"Se alcanzó el máximo de páginas para '{lugar}'.")
                    break
                pagina = int(siguiente)
            except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
                errores.append(f"{lugar}, página {pagina}: {error}")
                break

    return list(anuncios.values()), {
        "consultas": consultas,
        "consultas_ok": consultas_ok,
        "capturados": len(anuncios),
        "captura_confiable": (
            consultas > 0
            and consultas_ok == consultas
            and bool(anuncios)
            and not errores
            and not truncado
        ),
        "truncado_por_limite": truncado,
        "proveedor": "API.SH",
        "errores": errores[:10],
        "advertencias": advertencias[:10],
    }
