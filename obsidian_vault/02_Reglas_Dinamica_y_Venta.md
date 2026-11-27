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
- **Rincón:** 53.47 m² privada; 3 habitaciones, 2 baños; parqueadero propio en sótano; piso 5 sin ascensor; estrato 4; Excelente estado; última remodelación hace 3 años; administración $ 515.000 COP/mes; atributos: Excelente ubicación, Bicicletero, Buena vista.
- **Mirandela:** 78.67 m² construida; 3 habitaciones, 2 baños; parqueadero 1 parqueadero; piso 3 sin ascensor; estrato 4; Excelente estado; administración $ 327.000 COP/mes; atributos: Zonas verdes, Salones sociales.
- **Salitre:** 30.0 m² privada; 1 habitaciones, 1 baños; parqueadero comunal; piso 10 con ascensor; estrato 4; Construido hace 1 año; remodelado; administración $ 147.000 COP/mes; atributos: Gimnasio, Terrazas, Coworking, Zonas comunes.

- **Horizonte inicial de publicación:** 2027-02-27.
