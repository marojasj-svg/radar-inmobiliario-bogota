---
tipo: reglas-radar
fecha_actualizacion: 2026-11-27
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

## Perfiles de apartamentos propios

- **Rincón:** 53,47 m² privados; 3 habitaciones, 2 baños; 1 parqueadero propio en sótano; piso 5 sin ascensor; estrato 4; excelente estado, última remodelación hace 3 años; bicicletero, buena vista y excelente ubicación; administración $515.000 COP/mes.
- **Mirandela:** 78,67 m² construidos; 3 habitaciones, 2 baños; 1 parqueadero; piso 3 sin ascensor; estrato 4; excelente estado; zonas verdes y salones sociales; administración $327.000 COP/mes.
- **Salitre:** 30 m² privados; 1 habitación, 1 baño; parqueadero comunal; piso 10 con ascensor; estrato 4; construcción de 1 año y remodelado; gimnasio, terrazas, coworking y zonas comunes; administración $147.000 COP/mes.

## Horizonte de publicación

- Fecha objetivo inicial: **27 de febrero de 2027**. Se puede ajustar en `config/activos.json`.
- Los criterios de comparables se guardan por activo en `config/activos.json`: misma cantidad de habitaciones y baños, área dentro de una tolerancia del área propia y requisito mínimo de parqueaderos cuando aplica.
- Cada corte actualiza las fichas `03_Decision_Rincon.md`, `03_Decision_Mirandela.md` y `03_Decision_Salitre.md` en Obsidian.
- La mediana de comparables y el rango preliminar de publicación solo se recomiendan con captura confiable actual y al menos 3 comparables directos. Si no se cumple, la ficha conserva el histórico para consulta y marca la recomendación como pendiente.
- Los comparables son precios publicados. El descuento de cierre de 5% es una hipótesis orientativa y no representa una venta confirmada ni un avalúo.
