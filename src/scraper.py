import json
import os
import re
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from shapely.geometry import Point
from config import POLIGONO_ZONA

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

# Barrios cubiertos por el polígono para consulta en Fincaraíz
BARRIOS_OBJETIVO = [
    "estrella-del-norte",
    "orquideas",
    "el-toberin",
    "las-margaritas",
]


def punto_en_poligono(lat: float, lon: float) -> bool:
    if lat is None or lon is None:
        return False
    return POLIGONO_ZONA.contains(Point(float(lon), float(lat)))


def extraer_next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return {}
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        return {}


def buscar_listados_recursivo(obj, resultados: list):
    if isinstance(obj, dict):
        # Detectar estructura típica de aviso inmobiliario con precio, área y coordenadas
        if ("price" in obj or "precio" in obj) and ("area" in obj or "m2" in obj or "surface" in obj):
            resultados.append(obj)
        for v in obj.values():
            buscar_listados_recursivo(v, resultados)
    elif isinstance(obj, list):
        for item in obj:
            buscar_listados_recursivo(item, resultados)


def normalizar_item(raw: dict, barrio_fuente: str) -> dict | None:
    try:
        id_raw = str(raw.get("id") or raw.get("property_id") or raw.get("code") or "")
        if not id_raw:
            return None

        # Extraer precio
        precio = raw.get("price")
        if isinstance(precio, dict):
            precio = precio.get("amount") or precio.get("value")
        precio = float(re.sub(r"[^0-9.]", "", str(precio))) if precio else 0.0

        # Extraer área
        area = raw.get("area") or raw.get("surface") or raw.get("m2") or 0
        if isinstance(area, dict):
            area = area.get("value") or area.get("total") or 0
        area = float(re.sub(r"[^0-9.]", "", str(area))) if area else 0.0

        if precio <= 50_000_000 or area < 20:
            return None

        # Extraer coordenadas
        loc = raw.get("location") or raw.get("coordinates") or raw.get("geo") or {}
        lat = raw.get("latitude") or raw.get("lat") or loc.get("lat") or loc.get("latitude")
        lon = raw.get("longitude") or raw.get("lon") or raw.get("lng") or loc.get("lon") or loc.get("lng") or loc.get("longitude")

        # Si trae coordenadas, exigir que caiga dentro del polígono dibujado
        dentro_poligono = False
        if lat is not None and lon is not None:
            dentro_poligono = punto_en_poligono(float(lat), float(lon))
            if not dentro_poligono:
                return None

        habitaciones = raw.get("rooms") or raw.get("bedrooms") or raw.get("habitaciones") or 0
        banos = raw.get("bathrooms") or raw.get("banos") or 0
        parqueaderos = raw.get("garages") or raw.get("parking") or raw.get("parqueaderos") or 0
        titulo = str(raw.get("title") or raw.get("name") or f"Apartamento {area:.0f} m2").strip()
        slug = raw.get("link") or raw.get("url") or raw.get("slug") or ""
        if slug and not str(slug).startswith("http"):
            url = f"https://www.fincaraiz.com.co{slug if str(slug).startswith('/') else '/' + str(slug)}"
        else:
            url = str(slug) or f"https://www.fincaraiz.com.co/inmueble/{id_raw}"

        barrio = (
            raw.get("neighborhood")
            or (loc.get("neighborhood") if isinstance(loc, dict) else None)
            or barrio_fuente.replace("-", " ").title()
        )
        if isinstance(barrio, dict):
            barrio = barrio.get("name", barrio_fuente)

        return {
            "id_inmueble": f"FR-{id_raw}",
            "portal": "Fincaraiz",
            "titulo": titulo,
            "barrio": str(barrio),
            "precio": int(precio),
            "area_m2": round(area, 1),
            "precio_m2": int(precio / area),
            "habitaciones": int(habitaciones) if str(habitaciones).isdigit() else 0,
            "banos": int(banos) if str(banos).isdigit() else 0,
            "parqueaderos": int(parqueaderos) if str(parqueaderos).isdigit() else 0,
            "lat": float(lat) if lat is not None else None,
            "lon": float(lon) if lon is not None else None,
            "validado_poligono": dentro_poligono,
            "url": url,
        }
    except Exception:
        return None


def recolectar_zona() -> list[dict]:
    inmuebles_unicos = {}

    for barrio in BARRIOS_OBJETIVO:
        for pagina in range(1, 4):
            url = f"https://www.fincaraiz.com.co/venta/apartamentos/bogota/{barrio}/pagina{pagina}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=25)
                if resp.status_code != 200:
                    continue
                data = extraer_next_data(resp.text)
                candidatos = []
                buscar_listados_recursivo(data, candidatos)
                for item in candidatos:
                    normalizado = normalizar_item(item, barrio)
                    if normalizado and normalizado["id_inmueble"] not in inmuebles_unicos:
                        inmuebles_unicos[normalizado["id_inmueble"]] = normalizado
            except requests.RequestException as e:
                print(f"[WARN] Error consultando {url}: {e}")

    return list(inmuebles_unicos.values())


def main():
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs("data/snapshots", exist_ok=True)

    registros = recolectar_zona()
    print(f"[INFO] Fecha: {hoy} | Inmuebles capturados en zona: {len(registros)}")

    snapshot_path = f"data/snapshots/{hoy}.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "fecha_corte": hoy,
                "total_capturados": len(registros),
                "inmuebles": registros,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
