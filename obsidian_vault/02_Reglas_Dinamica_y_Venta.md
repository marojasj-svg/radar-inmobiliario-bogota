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

## Perfiles de activos propios

- Rincón: 55 m², 3 habitaciones, 2 baños, parqueadero propio, 5.º piso sin ascensor, administración $515.000 COP/mes. Horizonte inicial: junio de 2027.
- Mirandela y Salitre: perfil por parametrizar en archivos de configuración cuando se suministren sus características.
