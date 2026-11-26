---
tipo: dashboard-inmobiliario
zona: Estrella del Norte - Orquídeas - Toberín
fecha_actualizacion: 2026-11-26
activos_totales: 65
vendidos_o_retirados: 0
mediana_precio_m2: 5735294
tasa_absorcion_pct: 0.0
---

# Tablero de Dinámica Inmobiliaria — Zona Norte Bogotá
*Último corte: **2026-11-26***

## 1. Pulso de Liquidez y Velocidad de Venta
- **Oferta activa en polígono:** 65 apartamentos
- **Inmuebles que salieron del mercado (posibles ventas):** 0
- **Tasa de absorción acumulada:** 0.0%
- **Tiempo promedio hasta salir del mercado:** 0.0 días *(se calibra automáticamente con cada corte semanal)*
- **Precio / m² mediano del cuadrante:** **$5,735,294 COP/m²**
- **Ticket mediano de venta:** **$375,000,000 COP**

## 2. Top Oportunidades Detectadas (Descuento vs. Zona o Alto DOM)

| Ficha | Barrio | Área | Precio | Precio/m² | vs. Mediana | Días (DOM) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [[FR-194644927]] | Estrella Del Norte | 195.0 m² | $645.0M | $3.31M | -42.33% | 1 d |
| [[FR-194401446]] | Estrella Del Norte | 78.0 m² | $270.0M | $3.46M | -39.64% | 1 d |
| [[FR-194063239]] | Estrella Del Norte | 166.0 m² | $580.0M | $3.49M | -39.08% | 1 d |
| [[FR-193737508]] | El Toberin | 54.0 m² | $225.0M | $4.17M | -27.35% | 1 d |
| [[FR-193610696]] | Estrella Del Norte | 116.0 m² | $517.0M | $4.46M | -22.29% | 1 d |
| [[FR-193800815]] | Estrella Del Norte | 116.0 m² | $520.0M | $4.48M | -21.84% | 1 d |
| [[FR-194038827]] | Estrella Del Norte | 116.0 m² | $520.0M | $4.48M | -21.84% | 1 d |
| [[FR-192982042]] | Estrella Del Norte | 116.0 m² | $533.5M | $4.60M | -19.8% | 1 d |
| [[FR-193457338]] | Estrella Del Norte | 116.0 m² | $533.5M | $4.60M | -19.8% | 1 d |
| [[FR-194440047]] | El Toberin | 55.0 m² | $270.0M | $4.91M | -14.41% | 1 d |
| [[FR-194459858]] | El Toberin | 55.0 m² | $270.0M | $4.91M | -14.41% | 1 d |
| [[FR-194485745]] | El Toberin | 55.0 m² | $270.0M | $4.91M | -14.41% | 1 d |
| [[FR-194387128]] | El Toberin | 55.0 m² | $270.0M | $4.91M | -14.41% | 1 d |
| [[FR-194426049]] | El Toberin | 55.0 m² | $270.0M | $4.91M | -14.41% | 1 d |
| [[FR-194129028]] | Estrella Del Norte | 86.0 m² | $430.0M | $5.00M | -12.82% | 1 d |

## 3. Consulta Dataview Recomendada en Obsidian
```dataview
TABLE barrio AS "Barrio", area_m2 AS "m²", precio_actual AS "Precio", descuento_vs_zona_pct AS "Desc %", dias_en_mercado AS "Días"
FROM "Oportunidades"
WHERE tipo = "oportunidad-inmobiliaria"
SORT descuento_vs_zona_pct ASC
```
