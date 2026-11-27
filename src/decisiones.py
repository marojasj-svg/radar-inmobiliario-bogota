"""Genera fichas de decisión de venta por apartamento para Obsidian."""
import glob
import json
import os
from datetime import date, datetime
from statistics import median

RUTA_ACTIVOS = "config/activos.json"
CARPETA_TABLEROS = "obsidian_vault"


def leer_activos():
    with open(RUTA_ACTIVOS, encoding="utf-8") as archivo:
        return json.load(archivo)


def cargar_cortes():
    cortes = []
    for ruta in sorted(glob.glob("data/snapshots/*.json")):
        try:
            with open(ruta, encoding="utf-8") as archivo:
                corte = json.load(archivo)
            cortes.append(corte)
        except (OSError, json.JSONDecodeError):
            continue
    return cortes


def moneda(valor):
    return f"$ {int(round(float(valor or 0))):,}".replace(",", ".")


def numero(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def datos_area(item):
    area = numero(item.get("area_m2"))
    precio_m2 = numero(item.get("precio_m2"))
    if not precio_m2 and area:
        precio_m2 = numero(item.get("precio_actual", item.get("precio"))) / area
    return area, precio_m2


def es_comparable(item, activo, incluir_inactivo=False):
    if not incluir_inactivo and not item.get("activo_en_corte", True):
        return False
    if not item.get("validado_poligono"):
        return False
    if item.get("estado") == "revisar_atipico":
        return False
    if int(numero(item.get("habitaciones"))) != activo["habitaciones"]:
        return False
    if int(numero(item.get("banos"))) != activo["banos"]:
        return False

    area, precio_m2 = datos_area(item)
    area_objetivo = numero(activo.get("area_m2"))
    tolerancia = numero(activo.get("tolerancia_area_pct", 15)) / 100
    if not area or not area_objetivo or abs(area - area_objetivo) > area_objetivo * tolerancia:
        return False
    if int(numero(item.get("parqueaderos"))) < int(activo.get("parqueaderos_min_comparable", 0)):
        return False
    return precio_m2 > 0


def nombre_portal(portal):
    return {"Fincaraiz": "FincaRaíz", "Metrocuadrado": "Metrocuadrado"}.get(portal, portal or "-")


def limpiar_celda(valor):
    return str(valor or "-").replace("|", "/").replace("\n", " ")


def mediana_comparables(items):
    valores = [datos_area(i)[1] for i in items if datos_area(i)[1] > 0]
    return median(valores) if valores else 0


def cortes_confiables(cortes, zona_id):
    resultado = []
    for corte in cortes:
        fuentes = corte.get("estado_captura", {}).get(zona_id, {})
        portales = [portal for portal, estado in fuentes.items() if estado.get("captura_confiable")]
        if portales:
            resultado.append((corte, portales))
    return resultado


def comparables_historicos(zona_id, activo, historicos, portales_permitidos=None):
    filas = []
    for item in historicos:
        if item.get("zona") != zona_id:
            continue
        if portales_permitidos is not None and item.get("portal") not in portales_permitidos:
            continue
        if es_comparable(item, activo):
            filas.append(item)
    return sorted(
        filas,
        key=lambda i: (
            abs(datos_area(i)[0] - numero(activo["area_m2"])),
            -datos_area(i)[1],
        ),
    )


def comparables_corte(corte, zona_id, activo, portales):
    filas = []
    for item in corte.get("inmuebles", []):
        if item.get("zona") != zona_id or item.get("portal") not in portales:
            continue
        if es_comparable(item, activo):
            filas.append(item)
    return sorted(
        filas,
        key=lambda i: (
            abs(datos_area(i)[0] - numero(activo["area_m2"])),
            -datos_area(i)[1],
        ),
    )


def tendencia_comparables(cortes, zona_id, activo, indice_historico):
    filas = []
    for corte, portales in cortes_confiables(cortes, zona_id):
        registros = []
        for item in corte.get("inmuebles", []):
            llave = item.get("id_inmueble")
            historico = indice_historico.get(llave, {})
            if historico.get("estado") == "revisar_atipico":
                continue
            if item.get("portal") not in portales or not es_comparable(item, activo):
                continue
            registros.append(item)
        if registros:
            mediana_m2 = mediana_comparables(registros)
            filas.append({
                "fecha": corte.get("fecha_corte", ""),
                "cantidad": len(registros),
                "mediana_m2": mediana_m2,
                "valor_referencia": mediana_m2 * numero(activo["area_m2"]),
            })
    return filas[-8:]


def encabezado_fuentes(fecha_corte, fuentes, ultima_confiable):
    portales_actuales = [
        nombre_portal(p) for p, estado in fuentes.items()
        if estado.get("captura_confiable")
    ]
    if portales_actuales:
        return (
            f"**Calidad del corte {fecha_corte}:** parcial/confiable para "
            f"{', '.join(portales_actuales)}. Los comparables se limitan a esos portales."
        ), True

    fecha_anterior, portales_anteriores = ultima_confiable
    if fecha_anterior:
        return (
            f"**Calidad del corte {fecha_corte}:** ningún portal entregó datos confiables. "
            f"Se muestran solo los últimos comparables históricos validados; última captura "
            f"confiable: {fecha_anterior} ({', '.join(nombre_portal(p) for p in portales_anteriores)})."
        ), False
    return (
        f"**Calidad del corte {fecha_corte}:** ningún portal entregó datos confiables y "
        "todavía no hay capturas históricas válidas para esta zona.",
        False,
    )


def escribir_ficha(zona_id, activo, fecha_corte, historicos, fuentes, cortes, indice_historico):
    ruta = os.path.join(CARPETA_TABLEROS, f"03_Decision_{activo['nombre']}.md")
    fuentes_actuales = fuentes.get(zona_id, {})
    portales_actuales = {
        portal for portal, estado in fuentes_actuales.items()
        if estado.get("captura_confiable")
    }
    validos = cortes_confiables(cortes, zona_id)
    ultima_confiable = ("", [])
    if validos:
        corte_ok, portales_ok = validos[-1]
        ultima_confiable = (corte_ok.get("fecha_corte", ""), portales_ok)

    if portales_actuales:
        comparables = comparables_historicos(
            zona_id, activo, historicos, portales_permitidos=portales_actuales
        )
        etiqueta_comparables = "Comparables de los portales confiables en el corte actual"
    else:
        comparables = comparables_historicos(zona_id, activo, historicos)
        etiqueta_comparables = "Últimos comparables validados conocidos (pueden haber cambiado o salido)"
    estado_fuentes, captura_actual_confiable = encabezado_fuentes(
        fecha_corte, fuentes_actuales, ultima_confiable
    )

    minimos = int(activo.get("min_comparables_para_rango", 3))
    mediana_m2 = mediana_comparables(comparables)
    valor_base = mediana_m2 * numero(activo["area_m2"])
    rango_publicacion = None
    rango_cierre = None
    if captura_actual_confiable and len(comparables) >= minimos:
        rango_publicacion = [round(valor_base * 0.97), round(valor_base * 1.03)]
        rango_cierre = [round(valor_base * 0.93), round(valor_base * 0.97)]

    fecha_objetivo = leer_activos().get("fecha_objetivo_publicacion", "")
    try:
        dias_objetivo = (date.fromisoformat(fecha_objetivo) - date.fromisoformat(fecha_corte)).days
    except ValueError:
        dias_objetivo = None

    perfil = [
        f"- **Área del apartamento:** {activo['area_m2']} m² ({activo.get('tipo_area', 'por confirmar')}).",
        f"- **Distribución:** {activo['habitaciones']} habitaciones, {activo['banos']} baños, estrato {activo.get('estrato', 'sin dato')}.",
        f"- **Parqueadero:** {activo.get('tipo_parqueadero', 'sin dato')} ({activo.get('parqueaderos', 0)}).",
        f"- **Piso y ascensor:** piso {activo.get('piso', 'sin dato')}; {'con' if activo.get('ascensor') else 'sin'} ascensor.",
        f"- **Estado:** {activo.get('estado', 'sin dato')}.",
        f"- **Administración:** {moneda(activo.get('administracion_cop'))} COP/mes.",
        f"- **Atributos:** {', '.join(activo.get('atributos', [])) or 'sin dato'}.",
    ]

    if rango_publicacion:
        precio_salida = (
            f"- **Rango preliminar para probar publicación:** {moneda(rango_publicacion[0])}–"
            f"{moneda(rango_publicacion[1])} COP (±3% sobre el valor derivado de la mediana de "
            f"{len(comparables)} comparables).
"
            f"- **Cierre orientativo (-5%):** {moneda(valor_base * 0.95)} COP; banda "
            f"{moneda(rango_cierre[0])}–{moneda(rango_cierre[1])} COP.
"
            "- Recomendación provisional basada en precios publicados; revisar fotos, estado y "
            "negociación antes de fijar el precio definitivo."
        )
    elif not captura_actual_confiable:
        precio_salida = (
            "- **Precio recomendado:** pendiente. No hay captura confiable actual; no usar el "
            "histórico como si fuera oferta vigente."
        )
    else:
        precio_salida = (
            f"- **Precio recomendado:** pendiente. Hay {len(comparables)} comparables; se "
            f"requieren al menos {minimos} dentro del rango del perfil."
        )

    filas_comparables = []
    for item in comparables[:20]:
        area, precio_m2 = datos_area(item)
        precio = numero(item.get("precio_actual", item.get("precio")))
        fecha_visto = item.get("fecha_ultima_deteccion", item.get("fecha_corte", "sin dato"))
        url = str(item.get("url") or "")
        ficha = f"[{limpiar_celda(item.get('id_inmueble'))}]({url})" if url else limpiar_celda(item.get("id_inmueble"))
        edad = ""
        try:
            edad = str(max((date.fromisoformat(fecha_corte) - date.fromisoformat(str(fecha_visto)[:10])).days, 0))
        except ValueError:
            pass
        filas_comparables.append(
            f"| {ficha} | {nombre_portal(item.get('portal'))} | {limpiar_celda(item.get('barrio'))} | "
            f"{area:.1f} | {int(numero(item.get('habitaciones')))} / {int(numero(item.get('banos')))} | "
            f"{int(numero(item.get('parqueaderos')))} | {moneda(precio)} | {moneda(precio_m2)} | "
            f"{edad} |"
        )
    tabla_comparables = "\n".join(filas_comparables) or (
        "| Sin comparables que cumplan los criterios | - | - | - | - | - | - | - | - |"
    )

    tendencia = tendencia_comparables(cortes, zona_id, activo, indice_historico)
    filas_tendencia = [
        f"| {r['fecha']} | {r['cantidad']} | {moneda(r['mediana_m2'])} | {moneda(r['valor_referencia'])} |"
        for r in tendencia
    ]
    tabla_tendencia = "\n".join(filas_tendencia) or (
        "| Aún no hay cortes históricos confiables con comparables directos | - | - | - |"
    )

    frontmatter = f"""---
tipo: ficha-de-decision-inmobiliaria
zona: {zona_id}
fecha_corte: {fecha_corte}
fecha_objetivo_publicacion: {fecha_objetivo}
estado_captura: {"confiable" if captura_actual_confiable else "sin_datos_confiables"}
comparables_directos: {len(comparables)}
mediana_comparable_m2: {round(mediana_m2) if mediana_m2 else 0}
---
"""
    contenido = f"""{frontmatter}
# Decisión de venta — {activo['nombre']}

**Horizonte inicial:** {fecha_objetivo} ({dias_objetivo if dias_objetivo is not None else 'sin fecha'} días desde el corte {fecha_corte}).

## Perfil del apartamento

{chr(10).join(perfil)}

## Calidad y vigencia de la información

{estado_fuentes}

{etiqueta_comparables}. El DOM se cuenta desde la primera detección del radar y no equivale necesariamente a la publicación original. Las desapariciones no confirman una venta.

## Comparables directos

Criterios: misma cantidad de habitaciones y baños; área dentro de ±{activo.get('tolerancia_area_pct', 15)}% del apartamento propio; al menos {activo.get('parqueaderos_min_comparable', 0)} parqueadero(s) comparables cuando aplica. El portal puede no distinguir siempre parqueadero privado de comunal.

| ID | Portal | Barrio | Área m² | Hab./baños | Parqueaderos | Precio publicado | Precio/m² | Días desde última detección |
|---|---|---|---:|---:|---:|---:|---:|---:|
{tabla_comparables}

## Referencia de precio

- **Comparables directos disponibles:** {len(comparables)}.
- **Mediana observada de anuncios comparables:** {moneda(mediana_m2)} COP/m².
- **Valor mecánico por área propia:** {moneda(valor_base)} COP; sirve como referencia estadística, no como avalúo.
{precio_salida}

## Evolución del mercado por corte

El seguimiento guarda una fila solo cuando al menos un portal superó las validaciones de captura y geografía.

| Corte | Comparables | Mediana anuncios COP/m² | Valor por área propia |
|---|---:|---:|---:|
{tabla_tendencia}

## Qué revisar antes de publicar

- Confirmar que el polígono de la zona y el anuncio comparable correspondan al microsector del apartamento.
- Revisar si el precio publicado bajó y cuánto tiempo lleva observado.
- Comparar administración, piso, ascensor, estado, parqueadero y zonas comunes; no todos quedan disponibles en los anuncios.
- Ajustar el precio objetivo cada mes con una captura confiable y registrar el precio final de publicación cuando se active el anuncio.
"""
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)
    return os.path.basename(ruta)


def _reemplazar_seccion(texto, titulo, seccion):
    inicio = texto.find(titulo)
    if inicio < 0:
        return texto.rstrip() + "\n\n" + seccion.rstrip() + "\n"
    return texto[:inicio] + seccion.rstrip() + "\n"


def actualizar_reglas(activos, carpeta):
    ruta = os.path.join(carpeta, "02_Reglas_Dinamica_y_Venta.md")
    try:
        with open(ruta, encoding="utf-8") as archivo:
            texto = archivo.read()
    except OSError:
        return
    lineas = ["## Perfiles de apartamentos propios"]
    for zona_id, activo in activos["activos"].items():
        ascensor = "con ascensor" if activo.get("ascensor") else "sin ascensor"
        atributos = ", ".join(activo.get("atributos", []))
        lineas.append(
            f"- **{activo['nombre']}:** {activo['area_m2']} m² {activo.get('tipo_area', '')}; "
            f"{activo['habitaciones']} habitaciones, {activo['banos']} baños; "
            f"parqueadero {activo.get('tipo_parqueadero', 'sin dato')}; piso {activo.get('piso', 'sin dato')} "
            f"{ascensor}; estrato {activo.get('estrato', 'sin dato')}; {activo.get('estado', '')}; "
            f"administración {moneda(activo.get('administracion_cop'))} COP/mes; "
            f"atributos: {atributos}."
        )
    lineas.append(
        f"\n- **Horizonte inicial de publicación:** {activos.get('fecha_objetivo_publicacion', 'por definir')}."
    )
    _reemplazar_seccion(texto, "## Perfiles de activos propios", "\n".join(lineas))
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(_reemplazar_seccion(texto, "## Perfiles de activos propios", "\n".join(lineas)))


def agregar_enlaces_decision(carpeta, activos):
    enlaces = "\n".join(
        f"- [[03_Decision_{activo['nombre']}|Decisión de venta: {activo['nombre']}]]"
        for activo in activos["activos"].values()
    )
    seccion = "## Fichas de decisión de venta\n\n" + enlaces
    rutas = [os.path.join(carpeta, "00_Radar_Portafolio_3_Zonas.md")]
    rutas.extend(
        os.path.join(carpeta, f"01_Tablero_{a['nombre']}.md")
        for a in activos["activos"].values()
    )
    for ruta in rutas:
        try:
            with open(ruta, encoding="utf-8") as archivo:
                texto = archivo.read()
        except OSError:
            continue
        texto = _reemplazar_seccion(texto, "## Fichas de decisión de venta", seccion)
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(texto)


def generar_decisiones(fecha_corte, historicos, fuentes):
    activos = leer_activos()
    cortes = cargar_cortes()
    indice_historico = {
        item.get("id_inmueble"): item
        for registros in historicos.values()
        for item in registros
        if item.get("id_inmueble")
    }
    paginas = []
    for zona_id, activo in activos["activos"].items():
        registros = historicos.get(zona_id, [])
        paginas.append(
            escribir_ficha(
                zona_id, activo, fecha_corte, registros,
                fuentes.get(zona_id, {}), cortes, indice_historico,
            )
        )
    actualizar_reglas(activos, CARPETA_TABLEROS)
    agregar_enlaces_decision(CARPETA_TABLEROS, activos)
    print(f"[OK] Fichas de decisión generadas: {', '.join(paginas)}.")
