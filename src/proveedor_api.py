"""Búsquedas de FincaRaíz (API.SH) y Metrocuadrado (Scrappa)."""
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path\nimport time

import requests

API_SH_BASE = "https://api.api.sh"
SCRAPPA_BASE = "https://scrappa.co/api"
TIMEOUT_SEGUNDOS = 45
PAGINAS_MAXIMAS = 10
CREDITOS_MES_RADAR = 450
CREDITOS_MES_POR_ZONA = 150
RUTA_CREDITOS = Path("data/scrappa_creditos.json")
RUTA_COORDENADAS = Path("data/metrocuadrado_coordenadas.json")


def _cargar_json(ruta, defecto):
    try:
        with ruta.open(encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return defecto


def _guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)


def _mes_actual():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _reservar_credito(zona_id):
    """Reserva antes de llamar a Scrappa; distribuye el tope entre las tres zonas."""
    control = _cargar_json(RUTA_CREDITOS, {})
    mes = _mes_actual()
    if control.get("mes") != mes:
        control = {"mes": mes, "creditos_reservados_por_zona": {}}
    por_zona = control.setdefault("creditos_reservados_por_zona", {})
    usados = int(por_zona.get(zona_id, 0))
    total = sum(int(v) for v in por_zona.values())
    if usados >= CREDITOS_MES_POR_ZONA or total >= CREDITOS_MES_RADAR:
        return False
    por_zona[zona_id] = usados + 1
    control["creditos_reservados"] = total + 1
    _guardar_json(RUTA_CREDITOS, control)
    return True


def _solicitud_scrappa(url, params, headers):
    """Reintenta solo 503, que Scrappa documenta como no facturable y seguro."""
    esperas = (0, 3, 8)
    for indice, espera in enumerate(esperas):
        if espera:
            time.sleep(espera)
        respuesta = requests.get(
            url, params=params, headers=headers, timeout=TIMEOUT_SEGUNDOS
        )
        if respuesta.status_code == 503 and indice < len(esperas) - 1:
            continue
        respuesta.raise_for_status()
        return respuesta


def _coordenadas(obj):
    """Busca un par latitud/longitud en el detalle, sin recorrer anuncios relacionados."""
    if isinstance(obj, dict):
        lat = obj.get("latitude") or obj.get("lat")
        lon = obj.get("longitude") or obj.get("lon") or obj.get("lng")
        try:
            if lat is not None and lon is not None:
                lat, lon = float(lat), float(lon)
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
        except (TypeError, ValueError):
            pass
        for clave, valor in obj.items():
            if str(clave).lower() in {
                "nearby", "nearby_places", "poi", "similar", "photos", "images", "related"
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
    return None, None


def _radio_km(zona):
    """Radio entero mínimo que cubre el polígono desde su centroide, con margen."""
    poligono = zona["poligono"]
    centro = poligono.centroid
    lat0 = math.radians(centro.y)
    max_km = 0.0
    for lon, lat in poligono.exterior.coords:
        dy = (lat - centro.y) * 111.32
        dx = (lon - centro.x) * 111.32 * math.cos(lat0)
        max_km = max(max_km, math.hypot(dx, dy))
    return max(1, math.ceil(max_km + 0.1)), centro.y, centro.x


def _detalle_metro(id_anuncio, cache, headers, zona_id):
    guardado = cache.get(id_anuncio)
    if guardado and guardado.get("consultado"):
        fecha = str(guardado["consultado"])[:10]
        edad = (datetime.now(timezone.utc).date() - datetime.strptime(fecha, "%Y-%m-%d").date()).days
        if edad < 30:
            return guardado.get("lat"), guardado.get("lon"), None

    if not _reservar_credito(zona_id):
        return None, None, "Se alcanzó el límite mensual preventivo de 150 créditos de esta zona."
    respuesta = _solicitud_scrappa(
        f"{SCRAPPA_BASE}/metrocuadrado/property",
        params={"id": id_anuncio},
        headers=headers,
    )
    respuesta.raise_for_status()
    data = respuesta.json()
    if data.get("success") is False:
        raise ValueError(data.get("error") or "Scrappa no pudo consultar el anuncio.")
    anuncio = data.get("listing") or {}
    lat, lon = _coordenadas(anuncio)
    cache[id_anuncio] = {
        "lat": lat,
        "lon": lon,
        "consultado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    _guardar_json(RUTA_COORDENADAS, cache)
    return lat, lon, None


def _buscar_metrocuadrado(zona):
    api_key = os.getenv("SCRAPPA_API_KEY")
    if not api_key:
        return [], {
            "consultas": 0, "consultas_ok": 0, "capturados": 0,
            "captura_confiable": False, "proveedor": "Scrappa",
            "errores": ["Falta configurar el secreto SCRAPPA_API_KEY en GitHub Actions."],
        }

    headers = {"x-api-key": api_key}
    zona_id = zona.get("id", "zona")
    radio_km, latitud, longitud = _radio_km(zona)
    cache = _cargar_json(RUTA_COORDENADAS, {})
    anuncios, errores, advertencias = {}, [], []
    consultas = consultas_ok = 0
    truncado = False
    max_paginas = PAGINAS_MAXIMAS
    pagina = 1
    total_paginas = 1

    while pagina <= min(total_paginas, max_paginas):
        if not _reservar_credito(zona_id):
            truncado = True
            advertencias.append("Se detuvo la búsqueda al alcanzar el límite mensual preventivo de 150 créditos de esta zona.")
            break
        consultas += 1
        params = {
            "business_type": "venta",
            "property_type": "1",
            "city": "bogota",
            "latitude": latitud,
            "longitude": longitud,
            "distance": radio_km,
            "page": pagina,
            "per_page": 48,
        }
        try:
            respuesta = _solicitud_scrappa(
                f"{SCRAPPA_BASE}/metrocuadrado/search",
                params=params,
                headers=headers,
            )
            respuesta.raise_for_status()
            data = respuesta.json()
            if data.get("success") is False:
                raise ValueError(data.get("error") or "Scrappa reportó un error en la búsqueda.")
            lista = data.get("results") or []
            if not isinstance(lista, list):
                raise ValueError("Scrappa no devolvió una lista válida de resultados.")
            consultas_ok += 1
            for item in lista:
                id_anuncio = str(item.get("id") or "")
                if not id_anuncio:
                    continue
                anuncio = dict(item)
                try:
                    lat, lon, aviso = _detalle_metro(id_anuncio, cache, headers, zona_id)
                    if aviso:
                        advertencias.append(aviso)
                    if lat is not None and lon is not None:
                        anuncio["latitude"], anuncio["longitude"] = lat, lon
                except (requests.RequestException, ValueError, TypeError) as error:
                    errores.append(f"Detalle {id_anuncio}: {error}")
                anuncios[id_anuncio] = anuncio

            total = int(data.get("total_hits") or 0)
            page_size = max(1, int(data.get("page_size") or 48))
            total_paginas = max(1, math.ceil(total / page_size))
            if data.get("exceeds_offset_ceiling"):
                truncado = True
                advertencias.append("Scrappa indicó que la búsqueda supera el límite de resultados de una sola zona.")
            if pagina >= total_paginas:
                break
            pagina += 1
        except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
            errores.append(f"Búsqueda, página {pagina}: {error}")
            break

    if pagina < total_paginas and pagina >= max_paginas:
        truncado = True
        advertencias.append(f"Se alcanzó el máximo de {max_paginas} páginas para el radio de la zona.")
    return list(anuncios.values()), {
        "consultas": consultas,
        "consultas_ok": consultas_ok,
        "capturados": len(anuncios),
        "captura_confiable": (
            consultas > 0 and consultas_ok == consultas and bool(anuncios)
            and not errores and not truncado
        ),
        "truncado_por_limite": truncado,
        "proveedor": "Scrappa",
        "radio_km": radio_km,
        "errores": errores[:10],
        "advertencias": advertencias[:10],
    }


def _buscar_fincaraiz(zona):
    """Conserva la captura FincaRaíz existente vía API.SH."""
    clave = os.getenv("RADAR_DATA_API_KEY")
    if not clave:
        return [], {
            "consultas": 0, "consultas_ok": 0, "capturados": 0,
            "captura_confiable": False, "proveedor": "API.SH",
            "errores": ["Falta configurar el secreto RADAR_DATA_API_KEY en GitHub Actions."],
        }

    endpoint = f"{API_SH_BASE}/fincaraiz/v1/search"
    headers = {"x-api-key": clave}
    anuncios, errores, advertencias = {}, [], []
    consultas = consultas_ok = 0
    truncado = False
    for lugar in zona["barrios_fincaraiz"]:
        pagina = 1
        while pagina <= PAGINAS_MAXIMAS:
            consultas += 1
            try:
                respuesta = requests.get(
                    endpoint,
                    params={
                        "transaction": "sale", "property_type": "apartment",
                        "location": lugar, "page": pagina, "raw": "true",
                    },
                    headers=headers,
                    timeout=TIMEOUT_SEGUNDOS,
                )
                if respuesta.status_code == 404:
                    consultas_ok += 1
                    advertencias.append(f"Sin anuncios para la ubicación '{lugar}'.")
                    break
                respuesta.raise_for_status()
                data = respuesta.json()
                if not isinstance(data, dict) or data.get("success") is False:
                    raise ValueError("API.SH devolvió una respuesta no válida.")
                lista = data.get("listings") or data.get("results") or []
                if not isinstance(lista, list):
                    raise ValueError("API.SH no devolvió una lista válida.")
                consultas_ok += 1
                for item in lista:
                    clave_anuncio = str(item.get("id") or item.get("code") or item.get("url") or "")
                    if clave_anuncio:
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
            consultas > 0 and consultas_ok == consultas and bool(anuncios)
            and not errores and not truncado
        ),
        "truncado_por_limite": truncado,
        "proveedor": "API.SH",
        "errores": errores[:10],
        "advertencias": advertencias[:10],
    }


def buscar(portal, zona):
    """Devuelve anuncios originales y estado de búsqueda del portal."""
    if portal == "Fincaraiz":
        return _buscar_fincaraiz(zona)
    if portal == "Metrocuadrado":
        return _buscar_metrocuadrado(zona)
    return [], {
        "consultas": 0, "consultas_ok": 0, "capturados": 0,
        "captura_confiable": False, "proveedor": "desconocido",
        "errores": [f"Portal no soportado: {portal}"],
    }
