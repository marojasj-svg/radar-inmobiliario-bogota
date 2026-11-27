import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from shapely.geometry import Point

from config import MINIMOS_CAPTURA_PORTAL, ZONAS
from proveedor_api import buscar as buscar_api

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}
TIMEOUT_SEGUNDOS = 25
PAGINAS_POR_BUSQUEDA = 3


def numero(valor):
    """Convierte valores monetarios y áreas en formatos colombianos."""
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, dict):
        valor = valor.get("amount") or valor.get("value") or valor.get("total") or 0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^0-9,.-]", "", str(valor)).strip()
    if not texto:
        return 0.0
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        texto = "".join(partes[:-1]) + ("." + partes[-1] if len(partes[-1]) <= 2 else partes[-1])
    elif texto.count(".") > 1:
        partes = texto.split(".")
        texto = "".join(partes[:-1]) + ("." + partes[-1] if len(partes[-1]) <= 2 else partes[-1])
    try:
        return float(texto)
    except ValueError:
        return 0.0


def extraer_datos_embebidos(html):
    soup = BeautifulSoup(html, "html.parser")
    datos = []
    for script in soup.find_all("script"):
        texto = script.string or script.get_text()
        if not texto:
            continue
        tipo = (script.get("type") or "").lower()
        if script.get("id") == "__NEXT_DATA__" or "json" in tipo or texto.lstrip().startswith("{"):
            try:
                datos.append(json.loads(texto))
            except (json.JSONDecodeError, TypeError):
                continue
    return datos


def buscar_listados_recursivo(obj, resultados, vistos):
    if isinstance(obj, dict):
        tiene_precio = any(k in obj for k in ("price", "precio", "valor", "salePrice"))
        tiene_area = any(k in obj for k in ("area", "surface", "m2", "builtArea", "areaConstruida"))
        if tiene_precio and tiene_area:
            clave = str(obj.get("id") or obj.get("property_id") or obj.get("code") or obj.get("url") or id(obj))
            if clave not in vistos:
                vistos.add(clave)
                resultados.append(obj)
        for valor in obj.values():
            buscar_listados_recursivo(valor, resultados, vistos)
    elif isinstance(obj, list):
        for valor in obj:
            buscar_listados_recursivo(valor, resultados, vistos)


def extraer_coordenadas(raw):
    loc = raw.get("location") or raw.get("coordinates") or raw.get("geo") or raw.get("ubicacion") or {}
    if isinstance(loc, list) and len(loc) >= 2:
        lon, lat = loc[0], loc[1]
    elif isinstance(loc, dict):
        lat = raw.get("latitude") or raw.get("lat") or loc.get("lat") or loc.get("latitude")
        lon = raw.get("longitude") or raw.get("lon") or raw.get("lng") or loc.get("lon") or loc.get("lng") or loc.get("longitude")
    else:
        lat = raw.get("latitude") or raw.get("lat")
        lon = raw.get("longitude") or raw.get("lon") or raw.get("lng")
    try:
        return (float(lat), float(lon)) if lat is not None and lon is not None else (None, None)
    except (TypeError, ValueError):
        return None, None


def normalizar_item(raw, portal, zona_id, barrio_fuente):
    try:
        id_raw = str(raw.get("id") or raw.get("property_id") or raw.get("code") or raw.get("codigo") or "")
        enlace = raw.get("link") or raw.get("url") or raw.get("slug") or raw.get("permalink") or ""
        if not id_raw and enlace:
            id_raw = str(enlace).rstrip("/").split("/")[-1]
        if not id_raw:
            return None

        precio = numero(raw.get("price") or raw.get("price_sale") or raw.get("precio") or raw.get("valor") or raw.get("salePrice") or raw.get("sale_price"))
        area = numero(raw.get("area") or raw.get("area_m2") or raw.get("surface") or raw.get("m2") or raw.get("builtArea") or raw.get("built_area_m2") or raw.get("areaConstruida"))
        if precio <= 50_000_000 or area < 20:
            return None

        lat, lon = extraer_coordenadas(raw)
        zona = ZONAS[zona_id]
        validado = False
        if lat is not None and lon is not None:
            validado = zona["poligono"].covers(Point(lon, lat))
            # No asignar a una zona anuncios geolocalizados fuera del polígono.
            if not validado:
                return None

        habit = raw.get("rooms") or raw.get("bedrooms") or raw.get("habitaciones") or raw.get("alcobas") or 0
        banos = raw.get("bathrooms") or raw.get("banos") or raw.get("baños") or 0
        parqueaderos = raw.get("garages") or raw.get("parking") or raw.get("parqueaderos") or raw.get("garajes") or 0
        titulo = str(raw.get("title") or raw.get("name") or raw.get("titulo") or f"Apartamento {area:.0f} m2").strip()
        if enlace:
            url = str(enlace) if str(enlace).startswith("http") else urljoin(
                "https://www.fincaraiz.com.co/" if portal == "Fincaraiz" else "https://www.metrocuadrado.com/",
                str(enlace).lstrip("/")
            )
        else:
            url = ""

        loc = raw.get("location") or raw.get("ubicacion") or {}
        barrio = raw.get("neighborhood") or raw.get("neighborhood_common_name") or raw.get("barrio") or (
            loc.get("neighborhood") or loc.get("name") or loc.get("main") or loc.get("neighbourhood") if isinstance(loc, dict) else None
        ) or barrio_fuente.replace("-", " ").title()

        prefijo = "FR" if portal == "Fincaraiz" else "MC"
        id_raw = re.sub(rf"^{prefijo}-?", "", id_raw, flags=re.IGNORECASE)
        return {
            "portal": portal,
            "zona": zona_id,
            "id_inmueble": f"{prefijo}-{id_raw}",
            "titulo": titulo,
            "barrio": str(barrio),
            "precio": int(precio),
            "area_m2": round(area, 1),
            "precio_m2": int(precio / area),
            "habitaciones": int(numero(habit)),
            "banos": int(numero(banos)),
            "parqueaderos": int(numero(parqueaderos)),
            "lat": lat,
            "lon": lon,
            "validado_poligono": validado,
            "url": url,
        }
    except (TypeError, ValueError, AttributeError):
        return None


def urls_busqueda(portal, zona_id, zona):
    if portal == "Fincaraiz":
        for barrio in zona["barrios_fincaraiz"]:
            for pagina in range(1, PAGINAS_POR_BUSQUEDA + 1):
                yield barrio, f"https://www.fincaraiz.com.co/venta/apartamentos/bogota/{barrio}/pagina{pagina}"
    else:
        barrio = zona["busqueda_metrocuadrado"].split()[0].lower()
        base = f"https://www.metrocuadrado.com/apartamentos/venta/bogota/{barrio}/"
        for pagina in range(1, PAGINAS_POR_BUSQUEDA + 1):
            yield barrio, base if pagina == 1 else f"{base}?page={pagina}"


def recolectar_portal(portal, zona_id, zona):
    candidatos, estado = buscar_api(portal, zona)
    unicos = {}
    for item in candidatos:
        barrio = (
            item.get("neighborhood")
            or item.get("neighborhood_common_name")
            or zona.get("busqueda_metrocuadrado", zona_id).split()[0]
        )
        normalizado = normalizar_item(item, portal, zona_id, barrio)
        if normalizado:
            unicos[normalizado["id_inmueble"]] = normalizado

    minimo = MINIMOS_CAPTURA_PORTAL[portal]
    con_coordenadas = [
        item for item in unicos.values()
        if item.get("lat") is not None and item.get("lon") is not None
    ]
    dentro_poligono = [item for item in unicos.values() if item.get("validado_poligono")]
    cobertura_geo = round(len(con_coordenadas) / len(unicos) * 100, 1) if unicos else 0.0
    estado["capturados"] = len(unicos)
    estado["capturados_con_coordenadas"] = len(con_coordenadas)
    estado["capturados_en_poligono"] = len(dentro_poligono)
    estado["cobertura_coordenadas_pct"] = cobertura_geo
    estado["captura_confiable"] = (
        estado.get("captura_confiable", False)
        and len(dentro_poligono) >= minimo
        and cobertura_geo >= 80.0
        and estado.get("consultas_ok") == estado.get("consultas")
    )
    if candidatos and not unicos:
        estado.setdefault("errores", []).append(
            "La API devolvió anuncios, pero ninguno pasó la validación de precio, área y polígono."
        )
    return list(unicos.values()), estado


def main():
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs("data/snapshots", exist_ok=True)
    ruta = f"data/snapshots/{fecha}.json"
    forzar = os.getenv("FORZAR_CAPTURA", "false").lower() in ("1", "true", "si", "sí")
    if os.path.exists(ruta) and not forzar:
        print(
            f"[INFO] Ya existe un corte para {fecha}; se reutiliza sin consultar portales. "
            "Activa 'Forzar captura' en la ejecución manual para actualizarlo."
        )
        return
    inmuebles, estado_captura = [], {}

    for zona_id, zona in ZONAS.items():
        if not zona["activa"]:
            continue
        estado_captura[zona_id] = {}
        for portal in ("Fincaraiz", "Metrocuadrado"):
            registros, estado = recolectar_portal(portal, zona_id, zona)
            inmuebles.extend(registros)
            estado_captura[zona_id][portal] = estado
            print(f"[INFO] {zona_id}/{portal}: {len(registros)} anuncios; captura confiable={estado['captura_confiable']}")

    ruta = f"data/snapshots/{fecha}.json"
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump({
            "fecha_corte": fecha,
            "total_capturados": len(inmuebles),
            "estado_poligono": {k: v["estado_poligono"] for k, v in ZONAS.items()},
            "estado_captura": estado_captura,
            "inmuebles": inmuebles,
        }, archivo, ensure_ascii=False, indent=2)
    print(f"[INFO] Corte {fecha}: {len(inmuebles)} registros en {ruta}")


if __name__ == "__main__":
    main()
