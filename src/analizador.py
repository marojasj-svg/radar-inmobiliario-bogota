import glob
import json
import os
from datetime import datetime
import pandas as pd
from config import (
    UMBRAL_DESCUENTO_ZONA_PCT,
    UMBRAL_DIAS_MERCADO,
    UMBRAL_BAJADA_PRECIO_PCT,
)

HISTORICO_CSV = "data/historico_maestro.csv"
TABLERO_MD = "obsidian_vault/00_Tablero_Dinamica_Zona.md"
CARPETA_OPORTUNIDADES = "obsidian_vault/Oportunidades"


def cargar_ultimo_snapshot() -> tuple[str, list[dict]]:
    archivos = sorted(glob.glob("data/snapshots/*.json"))
    if not archivos:
        return datetime.now().strftime("%Y-%m-%d"), []
    with open(archivos[-1], "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["fecha_corte"], data.get("inmuebles", [])


def actualizar_historico(fecha_corte: str, inmuebles_hoy: list[dict]) -> pd.DataFrame:
    columnas = [
        "id_inmueble",
        "portal",
        "titulo",
        "barrio",
        "precio_inicial",
        "precio_actual",
        "variacion_pct",
        "area_m2",
        "precio_m2",
        "habitaciones",
        "banos",
        "parqueaderos",
        "lat",
        "lon",
        "fecha_primera_deteccion",
        "fecha_ultima_vez_visto",
        "dias_en_mercado",
        "estado",
        "historial_precios",
        "url",
    ]

    if os.path.exists(HISTORICO_CSV) and os.path.getsize(HISTORICO_CSV) > 0:
        df = pd.read_csv(HISTORICO_CSV)
    else:
        df = pd.DataFrame(columns=columnas)

    ids_hoy = {item["id_inmueble"]: item for item in inmuebles_hoy}
    dt_hoy = datetime.strptime(fecha_corte, "%Y-%m-%d")

    # 1. Actualizar registros existentes
    for idx, row in df.iterrows():
        iid = row["id_inmueble"]
        dt_inicio = datetime.strptime(str(row["fecha_primera_deteccion"]), "%Y-%m-%d")

        if iid in ids_hoy:
            actual = ids_hoy.pop(iid)
            nuevo_precio = actual["precio"]
            precio_ini = float(row["precio_inicial"])
            var_pct = round(((nuevo_precio - precio_ini) / precio_ini) * 100, 2)
            dom = max((dt_hoy - dt_inicio).days, 1)

            hist = str(row.get("historial_precios", ""))
            if nuevo_precio != float(row["precio_actual"]):
                hist = f"{hist} | {fecha_corte}: ${nuevo_precio:,.0f}"

            df.at[idx, "precio_actual"] = nuevo_precio
            df.at[idx, "variacion_pct"] = var_pct
            df.at[idx, "precio_m2"] = actual["precio_m2"]
            df.at[idx, "fecha_ultima_vez_visto"] = fecha_corte
            df.at[idx, "dias_en_mercado"] = dom
            df.at[idx, "estado"] = "activo_bajando" if var_pct < 0 else "activo"
            df.at[idx, "historial_precios"] = hist
        else:
            # Si ya estaba activo y desapareció en este corte -> posible venta o retiro
            if str(row["estado"]).startswith("activo"):
                dt_ult = datetime.strptime(str(row["fecha_ultima_vez_visto"]), "%Y-%m-%d")
                dom_final = max((dt_ult - dt_inicio).days, 1)
                df.at[idx, "dias_en_mercado"] = dom_final
                df.at[idx, "estado"] = "vendido_o_retirado"

    # 2. Insertar inmuebles nuevos detectados hoy
    nuevos = []
    for iid, item in ids_hoy.items():
        nuevos.append(
            {
                "id_inmueble": iid,
                "portal": item["portal"],
                "titulo": item["titulo"],
                "barrio": item["barrio"],
                "precio_inicial": item["precio"],
                "precio_actual": item["precio"],
                "variacion_pct": 0.0,
                "area_m2": item["area_m2"],
                "precio_m2": item["precio_m2"],
                "habitaciones": item["habitaciones"],
                "banos": item["banos"],
                "parqueaderos": item["parqueaderos"],
                "lat": item["lat"],
                "lon": item["lon"],
                "fecha_primera_deteccion": fecha_corte,
                "fecha_ultima_vez_visto": fecha_corte,
                "dias_en_mercado": 1,
                "estado": "activo_nuevo",
                "historial_precios": f"{fecha_corte}: ${item['precio']:,.0f}",
                "url": item["url"],
            }
        )

    if nuevos:
        df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)

    df.to_csv(HISTORICO_CSV, index=False)
    return df


def generar_notas_obsidian(fecha_corte: str, df: pd.DataFrame):
    os.makedirs(CARPETA_OPORTUNIDADES, exist_ok=True)

    if df.empty:
        with open(TABLERO_MD, "w", encoding="utf-8") as f:
            f.write(f"# Radar Inmobiliario Zona Norte ({fecha_corte})\n\nSin registros en el corte inicial. Verifica la conectividad del scraper.\n")
        return

    activos = df[df["estado"].str.startswith("activo")].copy()
    cerrados = df[df["estado"] == "vendido_o_retirado"].copy()

    mediana_m2 = activos["precio_m2"].median() if not activos.empty else 0
    precio_mediano = activos["precio_actual"].median() if not activos.empty else 0
    dom_promedio_ventas = cerrados["dias_en_mercado"].mean() if not cerrados.empty else 0
    tasa_absorcion = (len(cerrados) / len(df) * 100) if len(df) > 0 else 0

    activos["descuento_vs_zona_pct"] = (
        ((activos["precio_m2"] - mediana_m2) / mediana_m2 * 100).round(2)
        if mediana_m2 > 0
        else 0.0
    )

    # Filtrar oportunidades reales
    oportunidades = activos[
        (activos["descuento_vs_zona_pct"] <= UMBRAL_DESCUENTO_ZONA_PCT)
        | (activos["dias_en_mercado"] >= UMBRAL_DIAS_MERCADO)
        | (activos["variacion_pct"] <= UMBRAL_BAJADA_PRECIO_PCT)
    ].sort_values(by="descuento_vs_zona_pct")

    # Escribir fichas individuales para Obsidian
    for _, row in oportunidades.iterrows():
        nota_path = os.path.join(CARPETA_OPORTUNIDADES, f"{row['id_inmueble']}.md")
        contenido = f"""---
tipo: oportunidad-inmobiliaria
portal: {row['portal']}
id_inmueble: {row['id_inmueble']}
barrio: "{row['barrio']}"
precio_actual: {int(row['precio_actual'])}
precio_inicial: {int(row['precio_inicial'])}
variacion_pct: {row['variacion_pct']}
area_m2: {row['area_m2']}
precio_m2: {int(row['precio_m2'])}
mediana_zona_m2: {int(mediana_m2)}
descuento_vs_zona_pct: {row['descuento_vs_zona_pct']}
dias_en_mercado: {int(row['dias_en_mercado'])}
habitaciones: {int(row['habitaciones'])}
parqueaderos: {int(row['parqueaderos'])}
estado: {row['estado']}
fecha_corte: {fecha_corte}
url: "{row['url']}"
---

# {row['titulo']} (`{row['id_inmueble']}`)

- **Barrio:** [[{row['barrio']}]]
- **Precio actual:** ${row['precio_actual']:,.0f} COP (**${row['precio_m2']:,.0f} / m²**)
- **Comparativo zona:** **{row['descuento_vs_zona_pct']}%** frente a la mediana del cuadrante (${mediana_m2:,.0f} / m²)
- **Tiempo en el mercado (DOM):** **{int(row['dias_en_mercado'])} días** (detectado el {row['fecha_primera_deteccion']})
- **Historial de precios:** {row['historial_precios']}
- **Características:** {row['area_m2']} m² | {int(row['habitaciones'])} hab | {int(row['parqueaderos'])} parq
- **Enlace:** [Ver publicación original]({row['url']})
"""
        with open(nota_path, "w", encoding="utf-8") as f:
            f.write(contenido)

    # Escribir tablero principal de dinámica de la zona
    lineas_tabla = []
    for _, r in oportunidades.head(15).iterrows():
        lineas_tabla.append(
            f"| [[{r['id_inmueble']}]] | {r['barrio']} | {r['area_m2']} m² | ${r['precio_actual']/1e6:.1f}M | ${r['precio_m2']/1e6:.2f}M | {r['descuento_vs_zona_pct']}% | {int(r['dias_en_mercado'])} d |"
        )
    tabla_md = "\n".join(lineas_tabla) if lineas_tabla else "| Sin alertas aún | - | - | - | - | - | - |"

    tablero = f"""---
tipo: dashboard-inmobiliario
zona: Estrella del Norte - Orquídeas - Toberín
fecha_actualizacion: {fecha_corte}
activos_totales: {len(activos)}
vendidos_o_retirados: {len(cerrados)}
mediana_precio_m2: {int(mediana_m2)}
tasa_absorcion_pct: {round(tasa_absorcion, 2)}
---

# Tablero de Dinámica Inmobiliaria — Zona Norte Bogotá
*Último corte: **{fecha_corte}***

## 1. Pulso de Liquidez y Velocidad de Venta
- **Oferta activa en polígono:** {len(activos)} apartamentos
- **Inmuebles que salieron del mercado (posibles ventas):** {len(cerrados)}
- **Tasa de absorción acumulada:** {tasa_absorcion:.1f}%
- **Tiempo promedio hasta salir del mercado:** {dom_promedio_ventas:.1f} días *(se calibra automáticamente con cada corte semanal)*
- **Precio / m² mediano del cuadrante:** **${mediana_m2:,.0f} COP/m²**
- **Ticket mediano de venta:** **${precio_mediano:,.0f} COP**

## 2. Top Oportunidades Detectadas (Descuento vs. Zona o Alto DOM)

| Ficha | Barrio | Área | Precio | Precio/m² | vs. Mediana | Días (DOM) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{tabla_md}

## 3. Consulta Dataview Recomendada en Obsidian
```dataview
TABLE barrio AS "Barrio", area_m2 AS "m²", precio_actual AS "Precio", descuento_vs_zona_pct AS "Desc %", dias_en_mercado AS "Días"
FROM "Oportunidades"
WHERE tipo = "oportunidad-inmobiliaria"
SORT descuento_vs_zona_pct ASC
```
"""
    with open(TABLERO_MD, "w", encoding="utf-8") as f:
        f.write(tablero)


def main():
    fecha_corte, inmuebles_hoy = cargar_ultimo_snapshot()
    df = actualizar_historico(fecha_corte, inmuebles_hoy)
    generar_notas_obsidian(fecha_corte, df)
    print(f"[OK] Análisis completado para {fecha_corte}. Total registros históricos: {len(df)}")


if __name__ == "__main__":
    main()
