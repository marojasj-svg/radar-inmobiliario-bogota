# Radar Inmobiliario Bogotá (Estrella del Norte / Orquídeas / Toberín)

Sistema automatizado en Python + GitHub Actions + Obsidian para monitorear la oferta de apartamentos en venta dentro del polígono definido en el norte de Bogotá (Autopista Norte, Calle 165, Carrera 15/16B, Calle 153).

## ¿Qué hace este sistema?
1. **Rastreo automático cada 3 días:** Consulta publicaciones activas en el cuadrante y filtra geográficamente las coordenadas exactas mediante polígonos (`shapely`).
2. **Medición real de rotación (DOM y Absorción):** Compara cada corte contra el histórico acumulado (`data/historico_maestro.csv`) para identificar:
   - **Días en el mercado (DOM):** Cuánto tiempo lleva publicado cada apartamento.
   - **Tasa de absorción / posibles ventas:** Inmuebles que desaparecen del portal tras llevar varios días publicados.
   - **Caídas de precio (*Price Drops*):** Propietarios que reducen el valor pedido.
3. **Integración directa con Obsidian:** Genera un tablero resumen (`obsidian_vault/00_Tablero_Dinamica_Zona.md`) y fichas individuales en Markdown con propiedades YAML listas para **Dataview** en `obsidian_vault/Oportunidades/`.

## Configuración Rápida en GitHub
1. Sube todos estos archivos a tu repositorio privado `radar-inmobiliario-bogota`.
2. Ve a **Settings > Actions > General > Workflow permissions**, selecciona **Read and write permissions** y guarda.
3. Ve a la pestaña **Actions**, selecciona **Monitor Inmobiliario Zona Norte** y haz clic en **Run workflow** para ejecutar la primera captura de línea base.

## Conexión con Obsidian
1. Clona este repositorio en tu computador o dentro de una subcarpeta de tu bóveda de Obsidian.
2. Instala el plugin comunitario **Obsidian Git** y activa *Pull on startup* para recibir las nuevas oportunidades automáticamente.
