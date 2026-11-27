"""Búsquedas estructuradas de API.SH y recuperación persistente de coordenadas."""
import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests

API_BASE = "https://api.api.sh"
TIMEOUT_SEGUNDOS = 60
PAGINAS_MAXIMAS = 10
VERSION_CACHE_GEO = 2
DIAS_REINTENTO_GEO = 7
RUTA_CACHE_GEO = Path("data/cache_coordenadas_metrocuadrado.json")


def _coordenadas(item):
    """Busca coordenadas de la ficha y sus datos crudos, sin usar puntos de interés cercanos."""
    if isinstance(item, dict):
        lat = item.get("latitude") or item.get("lat")
        lon = item.get("longitude") or item.get("lon") or item.get("lng")
        try:
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        except (TypeError, ValueError):
            pass
        for clave, valor in item.items():
            if str(clave).lower() in {"nearby", "nearby_places", "poi", "similar", "photos", "images", "advertiser"}:
                continue
            resultado = _coordenadas(valor)
            if resultado != (None, None):
                return resultado
    elif isinstance(item, list):
        for valor in item:
            resultado = _coordenadas(valor)
            if resultado != (None, None):
                return resultado
    elif isinstance(item, str):
        texto = item.strip()
        if texto.startswith("{") or texto.startswith("["):
            try:
                return _coordenadas(json.loads(texto))
            except json.JSONDecodeError:
                pass
    return None, None


def _cargar_cache_geo():
    if not RUTA_CACHE_GEO.exists():
        return {}
    try:
        with RUTA_CACHE_GEO.open(encoding="utf-8") as archivo:
            cache = json.load(archivo)
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_cache_geo(cache):
    RUTA_CACHE_GEO.parent.mkdir(parents=True, exist_ok=True)
    temporal = RUTA_CACHE_GEO.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(cache, archivo, ensure_ascii=False, indent=2)
    temporal.replace(RUTA_CACHE_GEO)


def _aplicar_coordenadas(anuncio, lat, lon):
    if lat is not None and lon is not None:
        anuncio["latitude"] = lat
        anuncio["longitude"] = lon


def _completar_coordenadas_metro(anuncios, clave):
    cache = _cargar_cache_geo()
    consultas = coordenadas_recuperadas = cache_usado = 0
    advertencias = []
    claves_detalle = []
    headers = {"x-api-key": clave}

    for anuncio in anuncios:
        lat, lon = _coordenadas(anuncio)
        if lat is not None and lon is not None:
            continue

        identificador = str(anuncio.get("id") or anuncio.get("url") or "")
        if not identificador:
            advertencias.append("Anuncio de Metrocuadrado sin id ni URL para recuperar coordenadas.")
            continue

        guardado = cache.get(identificador, {})
        if guardado.get("version") == VERSION_CACHE_GEO and guardado.get("lat") is not None and guardado.get("lon") is not None:
            _aplicar_coordenadas(anuncio, guardado["lat"], guardado["lon"])
            cache_usado += 1
            continue

        revisado = guardado.get("revisado_en") if guardado.get("version") == VERSION_CACHE_GEO else None
        if revisado:
            try:
                if date.fromisoformat(revisado) > date.today() - timedelta(days=DIAS_REINTENTO_GEO):
                    continue
            except ValueError:
                pass

        params = {"url": anuncio["url"], "raw": "true"} if anuncio.get("url") else {"id": identificador, "raw": "true"}
        consultas += 1
        try:
            respuesta = requests.get(
                f"{API_BASE}/metrocuadrado/v1/listing",
                params=params,
                headers=headers,
                timeout=TIMEOUT_SEGUNDOS,
            )
            respuesta.raise_for_status()
            detalle = respuesta.json()
            if not isinstance(detalle, dict):
                raise ValueError("Detalle de Metrocuadrado no es un objeto JSON.")
            claves_detalle = sorted(detalle.keys())
            for envoltura in ("listing", "result", "data"):
                if isinstance(detalle.get(envoltura), dict):
                    detalle = detalle[envoltura]
            lat, lon = _coordenadas(detalle)
            guardado = {
                "lat": lat,
                "lon": lon,
                "revisado_en": date.today().isoformat(),
                "version": VERSION_CACHE_GEO,
            }
            cache[identificador] = guardado
            if lat is not None and lon is not None:
                _aplicar_coordenadas(anuncio, lat, lon)
                coordenadas_recuperadas += 1
            else:
                advertencias.append(f"Metrocuadrado no publicó coordenadas para {identificador}.")
        except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
            cache[identificador] = {
                "lat": None,
                "lon": None,
                "revisado_en": date.today().isoformat(),
                "version": VERSION_CACHE_GEO,
            }
            advertencias.append(f"No se pudo geolocalizar {identificador}: {error}")

    _guardar_cache_geo(cache)
    return {
        "consultas_geolocalizacion": consultas,
        "coordenadas_recuperadas": coordenadas_recuperadas,
        "coordenadas_desde_cache": cache_usado,
        "advertencias_geolocalizacion": advertencias[:20],
        "claves_detalle_ejemplo": claves_detalle,
    }


def buscar(portal, zona):
    """Devuelve anuncios originales y el estado de búsqueda del portal."""
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
    truncado_por_limite = False

    for lugar in lugares:
        pagina = 1
        while pagina <= PAGINAS_MAXIMAS:
            consultas += 1
            params = (
                {"transaction": "sale", "property_type": "apartment", "location": lugar, "page": pagina}
                if portal == "Fincaraiz"
                else {"deal": "venta", "type": "apartamento", "city": "bogota", "neighborhood": lugar, "page": pagina}
            )
            try:
                respuesta = requests.get(endpoint, params=params, headers=headers, timeout=TIMEOUT_SEGUNDOS)
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
                consultas_ok += 1
                lista = data.get("listings") or data.get("results") or []
                if not isinstance(lista, list) or any(not isinstance(item, dict) for item in lista):
                    raise ValueError("La respuesta no contiene una lista válida de anuncios.")
                for item in lista:
                    clave_anuncio = str(item.get("id") or item.get("code") or item.get("url") or "")
                    if clave_anuncio:
                        anuncios[clave_anuncio] = item
                siguiente = data.get("next_page")
                if not siguiente or not lista:
                    break
                if pagina >= PAGINAS_MAXIMAS:
                    truncado_por_limite = True
                    advertencias.append(f"Se alcanzó el máximo de páginas para '{lugar}'.")
                    break
                pagina = int(siguiente)
            except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
                errores.append(f"{lugar}, página {pagina}: {error}")
                break

    geo = {}
    if portal == "Metrocuadrado" and anuncios:
        geo = _completar_coordenadas_metro(list(anuncios.values()), clave)

    return list(anuncios.values()), {
        "consultas": consultas,
        "consultas_ok": consultas_ok,
        "capturados": len(anuncios),
        "captura_confiable": (
            consultas > 0 and consultas_ok == consultas and bool(anuncios)
            and not errores and not truncado_por_limite
        ),
        "truncado_por_limite": truncado_por_limite,
        "proveedor": "API.SH",
        "errores": errores[:10],
        "advertencias": advertencias[:10],
        **geo,
    }
