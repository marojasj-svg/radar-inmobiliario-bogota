import csv
import glob
import json
import os
import re
from datetime import date, datetime
from statistics import mean, median
from shapely.geometry import Point

from config import (
    DESCUENTO_CIERRE_BASE_PCT,
    FACTOR_ATIPICO_PRECIO_M2,
    MINIMOS_CAPTURA_PORTAL,
    PRECISION_COORDENADAS_HUELLA,
    RANGO_CIERRE_PCT,
    TOLERANCIA_AREA_M2,
    TOLERANCIA_PRECIO_HUELLA_PCT,
    UMBRAL_BAJADA_PRECIO_PCT,
    UMBRAL_DESCUENTO_ZONA_PCT,
    UMBRAL_DIAS_MERCADO,
    ZONAS,
)

CARPETA_HISTORICOS = "data"
CARPETA_OPORTUNIDADES = "obsidian_vault/Oportunidades"
CARPETA_TABLEROS = "obsidian_vault"


def fecha_dt(valor):
    return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()


def dias_entre(inicio, fin):
    try:
        return max((fecha_dt(fin) - fecha_dt(inicio)).days, 0)
    except (ValueError, TypeError):
        return 0


def moneda(valor):
    return f"$ {int(round(valor or 0)):,.0f}".replace(",", ".")


def url_yaml(valor):
    return json.dumps(str(valor or ""), ensure_ascii=False)


def cargar_snapshot():
    archivos = sorted(glob.glob("data/snapshots/*.json"))
    if not archivos:
        return date.today().isoformat(), [], {}
    with open(archivos[-1], encoding="utf-8") as archivo:
        datos = json.load(archivo)
    inmuebles = datos.get("inmuebles", [])
    # Compatibilidad con capturas antiguas, que solo cubrían el polígono de Rincón.
    for item in inmuebles:
        item.setdefault("zona", "rincon")
        item.setdefault("portal", "Fincaraiz")
    estados = datos.get("estado_captura", {})
    if not estados:
        conteo = len([i for i in inmuebles if i.get("zona") == "rincon"])
        estados = {"rincon": {"Fincaraiz": {
            "capturados": conteo,
            "captura_confiable": conteo >= MINIMOS_CAPTURA_PORTAL["Fincaraiz"],
        }}}
    return datos.get("fecha_corte", date.today().isoformat()), inmuebles, estados


def migrar_csv_rincon():
    ruta = "data/historico_maestro.csv"
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return []
    resultado = []
    with open(ruta, newline="", encoding="utf-8-sig") as archivo:
        for fila in csv.DictReader(archivo):
            primera = fila.get("fecha_primera_deteccion") or date.today().isoformat()
            ultima = fila.get("fecha_ultima_vez_visto") or primera
            precio_ini = int(float(fila.get("precio_inicial") or 0))
            precio_act = int(float(fila.get("precio_actual") or 0))
            texto_historial = str(fila.get("historial_precios") or "")
            historial = [
                {"fecha": fecha, "precio": int(re.sub(r"[^0-9]", "", precio))}
                for fecha, precio in re.findall(r"(20\d{2}-\d{2}-\d{2})\s*:\s*\$?\s*([0-9.,]+)", texto_historial)
            ]
            if not historial:
                historial = [{"fecha": primera, "precio": precio_ini}]
                if precio_act != precio_ini:
                    historial.append({"fecha": ultima, "precio": precio_act})
            salida = ultima if fila.get("estado") == "vendido_o_retirado" else None
            resultado.append({
                **fila,
                "zona": "rincon",
                "id_inmueble": fila.get("id_inmueble", ""),
                "fecha_primera_deteccion": primera,
                "fecha_ultima_deteccion": ultima,
                "fecha_salida": salida,
                "precio_inicial": precio_ini,
                "precio_actual": precio_act,
                "precio_m2": int(float(fila.get("precio_m2") or 0)),
                "area_m2": float(fila.get("area_m2") or 0),
                "habitaciones": int(float(fila.get("habitaciones") or 0)),
                "banos": int(float(fila.get("banos") or 0)),
                "parqueaderos": int(float(fila.get("parqueaderos") or 0)),
                "dias_en_mercado": int(float(fila.get("dias_en_mercado") or 0)),
                "estado": "posible_venta" if salida else "activo",
                "activo_en_corte": not bool(salida),
                "historial_precios": historial,
                "huella_inmueble": "",
            })
    return resultado


def cargar_historico(zona_id):
    ruta = os.path.join(CARPETA_HISTORICOS, f"historico_{zona_id}.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as archivo:
            registros = json.load(archivo)
    else:
        registros = migrar_csv_rincon() if zona_id == "rincon" else []

    # Completa los campos añadidos al pasar del histórico CSV al esquema por zona.
    for registro in registros:
        registro.setdefault("zona", zona_id)
        lat, lon = registro.get("lat"), registro.get("lon")
        try:
            lat, lon = float(lat), float(lon)
            registro["lat"], registro["lon"] = lat, lon
            registro["validado_poligono"] = ZONAS[zona_id]["poligono"].covers(Point(lon, lat))
        except (TypeError, ValueError):
            registro["lat"], registro["lon"] = None, None
            registro["validado_poligono"] = False
        registro.setdefault("fecha_ultima_deteccion", registro.get("fecha_ultima_vez_visto"))
        registro.setdefault(
            "activo_en_corte",
            registro.get("estado") in ("activo", "activo_nuevo", "activo_bajando", "revisar_atipico"),
        )
        if not registro.get("huella_inmueble"):
            registro["huella_inmueble"] = huella(registro)
    return registros


def huella(item):
    lat, lon = item.get("lat"), item.get("lon")
    coords = None
    if lat is not None and lon is not None:
        coords = [round(float(lat), PRECISION_COORDENADAS_HUELLA), round(float(lon), PRECISION_COORDENADAS_HUELLA)]
    return {
        "zona": item.get("zona"),
        "area_m2": round(float(item.get("area_m2") or 0), 1),
        "habitaciones": int(item.get("habitaciones") or 0),
        "banos": int(item.get("banos") or 0),
        "coordenadas": coords,
    }


def equivalentes(a, b):
    ha, hb = huella(a), huella(b)
    if ha["zona"] != hb["zona"] or abs(ha["area_m2"] - hb["area_m2"]) > TOLERANCIA_AREA_M2:
        return False
    if ha["habitaciones"] != hb["habitaciones"] or ha["banos"] != hb["banos"]:
        return False
    if not ha["coordenadas"] or not hb["coordenadas"] or ha["coordenadas"] != hb["coordenadas"]:
        return False
    pa, pb = float(a.get("precio_actual", a.get("precio", 0)) or 0), float(b.get("precio_actual", b.get("precio", 0)) or 0)
    if not pa or not pb:
        return False
    return abs(pb - pa) / pa * 100 <= TOLERANCIA_PRECIO_HUELLA_PCT


def normalizar_historial_precios(historial, fecha_corte, precio):
    historial = list(historial or [])
    coincidencias = [i for i, dato in enumerate(historial) if dato.get("fecha") == fecha_corte]
    if coincidencias:
        historial[coincidencias[-1]] = {"fecha": fecha_corte, "precio": int(precio)}
    elif not historial or historial[-1].get("precio") != int(precio):
        historial.append({"fecha": fecha_corte, "precio": int(precio)})
    return historial


def crear_registro(item, fecha_corte):
    nuevo = dict(item)
    nuevo.update({
        "fecha_primera_deteccion": fecha_corte,
        "fecha_ultima_deteccion": fecha_corte,
        "fecha_salida": None,
        "precio_inicial": int(item["precio"]),
        "precio_actual": int(item["precio"]),
        "variacion_pct": 0.0,
        "dias_en_mercado": 0,
        "estado": "activo_nuevo",
        "activo_en_corte": True,
        "historial_precios": [{"fecha": fecha_corte, "precio": int(item["precio"])}],
        "huella_inmueble": huella(item),
        "posible_republicacion": False,
    })
    return nuevo


def actualizar_registro(registro, item, fecha_corte):
    era_nuevo = registro.get("fecha_primera_deteccion") == fecha_corte
    fecha_primera = registro.get("fecha_primera_deteccion", fecha_corte)
    precio_ini = float(registro.get("precio_inicial") or item["precio"])
    precio = int(item["precio"])
    registro.update(item)
    registro["fecha_primera_deteccion"] = fecha_primera
    registro["fecha_ultima_deteccion"] = fecha_corte
    registro["fecha_salida"] = None
    registro["precio_inicial"] = int(precio_ini)
    registro["precio_actual"] = precio
    registro["variacion_pct"] = round((precio - precio_ini) / precio_ini * 100, 2) if precio_ini else 0
    registro["dias_en_mercado"] = dias_entre(fecha_primera, fecha_corte)
    registro["activo_en_corte"] = True
    registro["historial_precios"] = normalizar_historial_precios(
        registro.get("historial_precios"), fecha_corte, precio
    )
    registro["huella_inmueble"] = huella(item)
    registro["estado"] = "activo_nuevo" if era_nuevo else "activo"
    return registro


def mediana_activa(registros):
    precios = [
        int(r.get("precio_m2") or 0) for r in registros
        if r.get("activo_en_corte") and r.get("validado_poligono")
        and r.get("estado") != "revisar_atipico" and int(r.get("precio_m2") or 0) > 0
    ]
    return median(precios) if precios else 0


def calcular_cierre(registro, mediana):
    precio = int(registro.get("precio_actual") or 0)
    area = float(registro.get("area_m2") or 0)
    base = round(precio * (1 - DESCUENTO_CIERRE_BASE_PCT / 100))
    conservador = round(precio * (1 - RANGO_CIERRE_PCT[1] / 100))
    ajustado = round(precio * (1 - RANGO_CIERRE_PCT[0] / 100))
    cierre_m2 = round(base / area) if area else 0
    registro.update({
        "cierre_estimado_5pct_cop": base,
        "cierre_estimado_rango_cop": [conservador, ajustado],
        "cierre_estimado_5pct_m2": cierre_m2,
        "mediana_zona_m2_salida": int(mediana),
        "diferencia_cierre_vs_mediana_pct": round((cierre_m2 - mediana) / mediana * 100, 2) if mediana else None,
        "tipo_estimacion_cierre": "orientativa_no_confirmada",
    })


def actualizar_zona(zona_id, fecha_corte, lista_actual, estado_fuentes):
    registros = cargar_historico(zona_id)
    por_id = {r["id_inmueble"]: r for r in registros}
    actuales = {i["id_inmueble"]: i for i in lista_actual if i.get("zona") == zona_id}
    medianas_base = [
        int(i.get("precio_m2") or 0) for i in actuales.values()
        if i.get("validado_poligono") and int(i.get("precio_m2") or 0) > 0
    ]
    mediana_preliminar = median(medianas_base) if medianas_base else 0

    # Actualizar y clasificar los anuncios presentes en el corte.
    for iid, item in actuales.items():
        registro = por_id.get(iid)
        if registro is None:
            registro = crear_registro(item, fecha_corte)
            registros.append(registro)
            por_id[iid] = registro
        else:
            actualizar_registro(registro, item, fecha_corte)

        precio_m2 = int(registro.get("precio_m2") or 0)
        atipico = (
            not registro.get("validado_poligono")
            or not registro.get("lat")
            or not registro.get("lon")
            or (mediana_preliminar and precio_m2 and (
                precio_m2 < mediana_preliminar * FACTOR_ATIPICO_PRECIO_M2[0]
                or precio_m2 > mediana_preliminar * FACTOR_ATIPICO_PRECIO_M2[1]
            ))
        )
        if atipico:
            registro["estado"] = "revisar_atipico"

    mediana_salida = mediana_activa(registros)

    # Solo inferir una salida si el portal superó el umbral de captura de esa zona.
    faltantes = [
        r for r in registros
        if r.get("zona") == zona_id and r.get("activo_en_corte")
        and r.get("id_inmueble") not in actuales
        and estado_fuentes.get(r.get("portal"), {}).get("captura_confiable", False)
    ]
    candidatos = list(actuales.values())
    usados = set()
    for anterior in faltantes:
        reemplazo = next((
            i for i in candidatos
            if i["id_inmueble"] not in usados and equivalentes(anterior, i)
        ), None)
        anterior["activo_en_corte"] = False
        anterior["dias_en_mercado"] = dias_entre(
            anterior.get("fecha_primera_deteccion"), anterior.get("fecha_ultima_deteccion")
        )
        if reemplazo:
            anterior["estado"] = "posible_republicacion"
            anterior["id_republicado_como"] = reemplazo["id_inmueble"]
            reemplazo_reg = por_id.get(reemplazo["id_inmueble"])
            if reemplazo_reg:
                primera = min(
                    str(reemplazo_reg.get("fecha_primera_deteccion", fecha_corte)),
                    str(anterior.get("fecha_primera_deteccion", fecha_corte)),
                )
                reemplazo_reg["fecha_primera_deteccion"] = primera
                reemplazo_reg["dias_en_mercado"] = dias_entre(primera, fecha_corte)
                reemplazo_reg["posible_republicacion"] = True
                reemplazo_reg["id_origen_republicacion"] = anterior["id_inmueble"]
            usados.add(reemplazo["id_inmueble"])
        else:
            anterior["estado"] = "posible_venta"
            anterior["fecha_salida"] = fecha_corte
            calcular_cierre(anterior, mediana_salida)

    ruta = os.path.join(CARPETA_HISTORICOS, f"historico_{zona_id}.json")
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(registros, archivo, ensure_ascii=False, indent=2)
    return registros


def es_activo_valido(registro):
    return bool(registro.get("activo_en_corte")) and registro.get("validado_poligono") and registro.get("estado") != "revisar_atipico"


def frontmatter_ficha(r, fecha_corte):
    campos = {
        "tipo": "oportunidad-inmobiliaria",
        "zona": r.get("zona"),
        "estado_poligono": ZONAS[r["zona"]]["estado_poligono"],
        "portal": r.get("portal"),
        "id_inmueble": r.get("id_inmueble"),
        "barrio": r.get("barrio"),
        "huella_inmueble": r.get("huella_inmueble"),
        "fecha_primera_deteccion": r.get("fecha_primera_deteccion"),
        "fecha_ultima_deteccion": r.get("fecha_ultima_deteccion"),
        "fecha_salida": r.get("fecha_salida"),
        "precio_actual": r.get("precio_actual"),
        "precio_inicial": r.get("precio_inicial"),
        "variacion_pct": r.get("variacion_pct"),
        "area_m2": r.get("area_m2"),
        "precio_m2": r.get("precio_m2"),
        "dias_en_mercado": r.get("dias_en_mercado"),
        "estado": r.get("estado"),
        "cierre_estimado_5pct_cop": r.get("cierre_estimado_5pct_cop"),
        "cierre_estimado_5pct_m2": r.get("cierre_estimado_5pct_m2"),
        "fecha_corte": fecha_corte,
        "url": r.get("url"),
    }
    return "---\n" + "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, str)) or v is None else v}"
        for k, v in campos.items()
    ) + "\n---"


def escribir_fichas(zona_id, fecha_corte, registros, mediana):
    for r in registros:
        if r.get("zona") != zona_id:
            continue
        r["mediana_zona_m2"] = int(mediana)
        r["descuento_vs_zona_pct"] = round((int(r.get("precio_m2") or 0) - mediana) / mediana * 100, 2) if mediana else None
        es_oportunidad = es_activo_valido(r) and (
            (r.get("descuento_vs_zona_pct") is not None and r["descuento_vs_zona_pct"] <= UMBRAL_DESCUENTO_ZONA_PCT)
            or int(r.get("dias_en_mercado") or 0) >= UMBRAL_DIAS_MERCADO
            or float(r.get("variacion_pct") or 0) <= UMBRAL_BAJADA_PRECIO_PCT
        )
        es_salida = r.get("estado") in ("posible_venta", "posible_republicacion")
        es_revision = bool(r.get("activo_en_corte")) and r.get("estado") == "revisar_atipico"
        if not es_oportunidad and not es_salida and not es_revision:
            continue
        carpeta = os.path.join(CARPETA_OPORTUNIDADES, zona_id.title())
        os.makedirs(carpeta, exist_ok=True)
        nombre = r["id_inmueble"].replace("/", "_") + ".md"
        texto = f"""{frontmatter_ficha(r, fecha_corte)}

# {r.get('titulo', 'Apartamento')} ({r['id_inmueble']})

- **Zona:** {ZONAS[zona_id]['nombre']} ({ZONAS[zona_id]['estado_poligono']})
- **Barrio:** {r.get('barrio', '')}
- **Precio publicado:** {moneda(r.get('precio_actual'))} COP | {moneda(r.get('precio_m2'))} COP/m²
- **Mediana activa de la zona:** {moneda(mediana)} COP/m²
- **DOM observado:** {int(r.get('dias_en_mercado') or 0)} días
- **Estado:** {r.get('estado')}
- **Historial de precios:** {json.dumps(r.get('historial_precios', []), ensure_ascii=False)}
- **Enlace:** [Ver anuncio]({r.get('url', '')})
"""
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as archivo:
            archivo.write(texto)


def tabla_posibles_ventas(registros, mediana):
    filas = []
    for r in registros:
        if r.get("estado") != "posible_venta":
            continue
        filas.append(
            f"| {r.get('id_inmueble')} | {r.get('portal')} | {r.get('barrio', '')} | "
            f"{r.get('area_m2', 0)} | {r.get('habitaciones', 0)}/{r.get('banos', 0)} | "
            f"{int(r.get('dias_en_mercado') or 0)} | {moneda(r.get('precio_actual'))} | "
            f"{moneda(r.get('cierre_estimado_5pct_cop'))} | {moneda(r.get('cierre_estimado_5pct_m2'))} | "
            f"{r.get('diferencia_cierre_vs_mediana_pct', '')}% | Estimación orientativa |"
        )
    return "\n".join(filas) or "| Sin posibles ventas | - | - | - | - | - | - | - | - | - | - |"


def generar_tableros(fecha_corte, historicos, estados_captura):
    resumen = {}
    for zona_id, zona in ZONAS.items():
        registros = historicos[zona_id]
        fuentes_zona = estados_captura.get(zona_id, {})
        portales_confiables = [p for p, estado in fuentes_zona.items() if estado.get("captura_confiable")]
        estado_captura = (
            "confiable" if fuentes_zona and len(portales_confiables) == len(fuentes_zona)
            else "parcial" if portales_confiables
            else "sin_datos_confiables"
        )
        activos = [r for r in registros if r.get("zona") == zona_id and es_activo_valido(r)]
        ventas = [r for r in registros if r.get("zona") == zona_id and r.get("estado") == "posible_venta"]
        mediana = median([int(r.get("precio_m2") or 0) for r in activos if int(r.get("precio_m2") or 0) > 0]) if activos else 0
        mediana_cierre = median([int(r.get("cierre_estimado_5pct_m2") or 0) for r in ventas if int(r.get("cierre_estimado_5pct_m2") or 0) > 0]) if ventas else 0
        dom = mean([int(r.get("dias_en_mercado") or 0) for r in ventas]) if ventas else 0
        total_historico = sum(1 for r in registros if r.get("zona") == zona_id)
        absorcion = round(len(ventas) / total_historico * 100, 2) if total_historico else 0
        resumen[zona_id] = (activos, ventas, mediana, mediana_cierre, dom, absorcion)

        os.makedirs(CARPETA_TABLEROS, exist_ok=True)
        path = os.path.join(CARPETA_TABLEROS, f"01_Tablero_{zona_id.title()}.md")
        frontmatter = (
            f"---\ntipo: tablero-inmobiliario\nzona: {zona_id}\n"
            f"estado_poligono: {zona['estado_poligono']}\nfecha_actualizacion: {fecha_corte}\n"
            f"estado_captura: {estado_captura}\nportales_confiables: {json.dumps(portales_confiables, ensure_ascii=False)}\n"
            f"oferta_activa_valida: {len(activos)}\nposibles_ventas: {len(ventas)}\n"
            f"mediana_precio_m2: {int(mediana)}\n---"
        )
        lineas = [
            frontmatter, "", f"# Radar de {zona['nombre']} — Bogotá", "",
            f"Polígono en **{zona['estado_poligono']}**. Los indicadores geográficos deben interpretarse con esa calibración.",
            f"**Captura {fecha_corte}:** " + "; ".join(
                f"{p}: {e.get('capturados', 0)} anuncios ({'confiable' if e.get('captura_confiable') else 'no confiable'})"
                for p, e in fuentes_zona.items()
            ) if fuentes_zona else "**Captura:** no disponible.",
            *([] if portales_confiables else ["La captura actual no es confiable; las cifras de oferta y medianas conservan el último histórico validado y pueden estar desactualizadas."]),
            "", "## Dinámica de zona", "",
            f"- Oferta activa válida: **{len(activos)}**",
            f"- Posibles ventas acumuladas: **{len(ventas)}**",
            f"- Tasa de absorción observada: **{absorcion}%**",
            f"- DOM promedio de salida: **{dom} días**",
            f"- Mediana activa: **{moneda(mediana)} COP/m²**",
            f"- Mediana de cierre estimado (-5%): **{moneda(mediana_cierre)} COP/m²**",
            "", "## Posibles ventas y cierres estimados", "",
            "| ID | Portal | Barrio | Área (m²) | Hab/Baños | DOM (días) | Último precio | Cierre est. (-5%) | Cierre est. ($/m²) | vs mediana zona | Señal |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
            tabla_posibles_ventas(registros, mediana),
        ]
        if zona_id == "rincon":
            comps = [r for r in activos if 50 <= float(r.get("area_m2") or 0) <= 62 and int(r.get("habitaciones") or 0) == 3]
            lineas += ["", "## Comparables directos del apartamento propio (50–62 m², 3 habitaciones)", "",
                "| ID | Portal | Área | Precio | Precio/m² | DOM | Baños |",
                "|---|---|---:|---:|---:|---:|---:|"]
            lineas += [
                f"| {r.get('id_inmueble')} | {r.get('portal')} | {r.get('area_m2')} | {moneda(r.get('precio_actual'))} | {moneda(r.get('precio_m2'))} | {r.get('dias_en_mercado', 0)} | {r.get('banos', 0)} |"
                for r in comps
            ] or ["| Sin comparables actuales | - | - | - | - | - | - |"]
        with open(path, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(lineas) + "\n")
        escribir_fichas(zona_id, fecha_corte, registros, mediana)

    filas = []
    for zona_id, zona in ZONAS.items():
        activos, ventas, mediana, mediana_cierre, dom, absorcion = resumen[zona_id]
        filas.append(
            f"| {zona['nombre']} | {zona['estado_poligono']} | {resumen[zona_id][0] and 'confiable' or 'sin datos'} | {len(activos)} | {len(ventas)} | "
            f"{absorcion}% | {dom} días | {moneda(mediana)} | {moneda(mediana_cierre)} |"
        )
    texto = f"""---
tipo: radar-portafolio
fecha_actualizacion: {fecha_corte}
zonas: 3
---

# Radar de liquidez del portafolio — Bogotá

| Zona | Estado del polígono | Captura | Oferta activa válida | Posibles ventas acumuladas | Tasa de absorción | DOM promedio de salida | Mediana activa COP/m² | Mediana cierre estimado (-5%) |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(filas)}
"""
    with open(os.path.join(CARPETA_TABLEROS, "00_Radar_Portafolio_3_Zonas.md"), "w", encoding="utf-8") as archivo:
        archivo.write(texto)
    reglas = """---
tipo: reglas-radar
fecha_actualizacion: """ + fecha_corte + """
descuento_cierre_base_pct: 5
rango_cierre_pct: [3, 7]
tolerancia_area_m2: 2
tolerancia_precio_huella_pct: 5
precision_coordenadas_huella: 4
---

# Reglas de dinámica y venta

- Los cierres estimados son escenarios orientativos calculados sobre el último precio publicado; no son precios de transacciones confirmadas.
- Base: descuento de negociación del 5%; banda orientativa del 3% al 7%.
- La posible republicación compara zona, área (±2 m²), habitaciones, baños, coordenadas redondeadas a 4 decimales y precio (±5%).
- Los anuncios sin coordenadas o con precio/m² atípico (menor a 0,5× o mayor a 1,8× la mediana preliminar) se aíslan en estado `revisar_atipico`.
- Una ausencia solo cambia a posible venta cuando el portal supera el umbral mínimo de captura de esa zona.
- DOM observado comienza en la primera detección disponible; no equivale a la fecha real de publicación.
- Tasa de absorción acumulada: posibles ventas estimadas divididas por IDs únicos históricos de la zona; no equivale a absorción mensual de transacciones confirmadas.

## Perfiles de activos propios

- Rincón: 55 m², 3 habitaciones, 2 baños, parqueadero propio, 5.º piso sin ascensor, administración $515.000 COP/mes. Horizonte inicial: junio de 2027.
- Mirandela y Salitre: perfil por parametrizar en archivos de configuración cuando se suministren sus características.
"""
    with open(os.path.join(CARPETA_TABLEROS, "02_Reglas_Dinamica_y_Venta.md"), "w", encoding="utf-8") as archivo:
        archivo.write(reglas)


def main():
    fecha_corte, inmuebles_hoy, fuentes = cargar_snapshot()
    historicos = {}
    for zona_id in ZONAS:
        por_fuente = fuentes.get(zona_id, {})
        historicos[zona_id] = actualizar_zona(
            zona_id,
            fecha_corte,
            inmuebles_hoy,
            por_fuente,
        )
    generar_tableros(fecha_corte, historicos, fuentes)
    print(f"[OK] Histórico y tableros actualizados para {fecha_corte}.")


if __name__ == "__main__":
    main()
