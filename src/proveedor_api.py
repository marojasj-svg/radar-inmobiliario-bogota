"""Adaptador de búsqueda estructurada para API.SH; requiere RADAR_DATA_API_KEY."""
import os

import requests

API_BASE = "https://api.api.sh"
TIMEOUT_SEGUNDOS = 60
PAGINAS_MAXIMAS = 3


def buscar(portal, zona):
    """Devuelve anuncios originales y estado de las consultas del portal."""
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
                respuesta = requests.get(
                    endpoint, params=params, headers=headers, timeout=TIMEOUT_SEGUNDOS
                )
                if respuesta.status_code == 404:
                    # API.SH documenta 404 cuando una búsqueda no encuentra anuncios.
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
                pagina = int(siguiente)
            except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
                errores.append(f"{lugar}, página {pagina}: {error}")
                break

    return list(anuncios.values()), {
        "consultas": consultas,
        "consultas_ok": consultas_ok,
        "capturados": len(anuncios),
        "captura_confiable": consultas > 0 and consultas_ok == consultas and bool(anuncios) and not errores,
        "proveedor": "API.SH",
        "errores": errores[:10],
        "advertencias": advertencias[:10],
    }
