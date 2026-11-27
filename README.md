# Radar Inmobiliario Bogotá

Automatización para observar oferta y rotación de apartamentos en tres zonas: Rincón, Mirandela y Salitre. El sistema consulta FincaRaíz y Metrocuadrado, guarda capturas por fecha, mantiene histórico por zona y genera tableros y fichas Markdown para Obsidian.

## Flujo automático

El workflow de GitHub Actions ejecuta `src/scraper.py` y luego `src/analizador.py`. El cron realiza cortes cada tres días. En una ejecución manual, si ya existe un corte para hoy, el radar lo reutiliza sin volver a llamar a los proveedores. Para actualizarlo el mismo día, marca **Forzar captura** en **Actions → Monitor Inmobiliario Zona Norte → Run workflow**.

- `config/zonas.json`: límites, estado de calibración y rutas de búsqueda por zona. Las coordenadas se guardan como [latitud, longitud]; el código las convierte al orden requerido por Shapely.
- `data/snapshots/AAAA-MM-DD.json`: corte unificado con anuncios y estado de captura por portal y zona.
- `data/historico_rincon.json`, `data/historico_mirandela.json`, `data/historico_salitre.json`: estado persistente de cada anuncio, fechas detectadas, precios, huellas y salidas probables.
- `data/metrocuadrado_coordenadas.json`: coordenadas obtenidas de los detalles de Metrocuadrado, para no volver a consultar el mismo anuncio durante 30 días.
- `data/scrappa_creditos.json`: contador mensual preventivo de solicitudes que hace este radar a Scrappa.
- `obsidian_vault/00_Radar_Portafolio_3_Zonas.md`: comparación consolidada.
- `obsidian_vault/01_Tablero_Rincon.md`, `01_Tablero_Mirandela.md`, `01_Tablero_Salitre.md`: tablero por zona; el frontmatter conserva `estado_poligono`.
- `obsidian_vault/02_Reglas_Dinamica_y_Venta.md`: parámetros de estimación y perfil de referencia de Rincón.
- `obsidian_vault/Oportunidades/<Zona>/<ID>.md`: fichas individuales.

La primera ejecución con la nueva estructura migra el histórico CSV anterior de Rincón a su archivo JSON. Los cortes históricos anteriores solo contienen Rincón y FincaRaíz.

## Calidad y límites de las métricas

Un anuncio que desaparece se clasifica como **posible venta**, no como venta confirmada. La ausencia solo se procesa si ese portal superó el umbral mínimo de captura de la zona; una falla o captura vacía no cierra todos los anuncios. Huellas similares entre portales o IDs se marcan como posibles republicaciones y transfieren la antigüedad acumulada.

Los anuncios sin coordenadas y los precios por m² muy alejados de la mediana preliminar se aíslan como `revisar_atipico`. Se excluyen de la oferta válida y de las medianas. DOM cuenta desde la primera detección disponible; no es necesariamente la fecha real de publicación.

El cierre estimado usa un descuento base del 5% y una banda de 3% a 7% sobre el último precio publicado. Es una referencia orientativa, no un dato transaccional ni un avalúo.

Mirandela y Salitre están activas con polígonos `aproximado_v1`; sus tableros indican que están en calibración. Refinar los vértices en `config/zonas.json` no requiere cambiar el motor de análisis.

## Proveedores y credenciales

FincaRaíz se consulta por API.SH y Metrocuadrado por Scrappa. Son proveedores externos e independientes de los portales. Scrappa requiere una búsqueda por radio y una consulta de detalle por anuncio nuevo para recuperar coordenadas. El radar limita esta búsqueda a un círculo calculado alrededor del polígono y valida después cada coordenada contra el polígono configurado. Los anuncios fuera del polígono no entran en el corte.

En GitHub, abre **Settings → Secrets and variables → Actions → New repository secret** y configura:

- `RADAR_DATA_API_KEY`: clave API.SH para FincaRaíz.
- `SCRAPPA_API_KEY`: clave Scrappa para Metrocuadrado.

Pega cada clave directamente en GitHub como secreto. No la agregues al código, a un archivo del repositorio ni a este chat.

Scrappa incluye 500 créditos mensuales gratuitos por cuenta. Para limitar el consumo de este radar, el contador del repositorio reserva como máximo 450 solicitudes al mes, distribuidas en hasta 150 por zona, y conserva las coordenadas consultadas por 30 días. Usa una cuenta/clave dedicada al radar: el contador solo conoce las solicitudes del repositorio y no puede contar otras aplicaciones que usen la misma cuenta. No compres créditos ni actives un plan pago para habilitar este flujo; si el límite preventivo se alcanza, la captura Metrocuadrado queda incompleta y no se usa para inferir salidas. Revisa la [documentación de búsqueda](https://scrappa.co/docs/metrocuadrado-api/metrocuadrado_search), la [documentación de detalles](https://scrappa.co/docs/metrocuadrado-api/metrocuadrado_property) y los [precios vigentes](https://scrappa.co/pricing) antes de utilizar el servicio; sus condiciones pueden cambiar.

API.SH ofrece créditos gratuitos mensuales sujetos a sus límites vigentes; revisa sus [precios](https://api.sh/pricing). Un error HTTP 402 significa que la cuenta o la clave no tiene créditos disponibles o alcanzó un límite. Sin agregar fondos, espera al reinicio mensual o revisa los límites en el panel de API.SH. Si falta cualquier clave, la captura de ese portal se marca como no confiable y no genera posibles ventas.

GitHub Actions usa además el token temporal `GITHUB_TOKEN` que GitHub crea para cada ejecución. `actions/checkout` conserva la credencial para que el paso final pueda publicar el commit, y el workflow limita el permiso del token a `contents: write`.

En **Settings → Actions → General → Workflow permissions**, habilita permisos de lectura y escritura para que el workflow pueda guardar capturas, históricos y tableros.

## Obsidian

Clona este repositorio dentro de la bóveda o usa Obsidian Git para traer los commits del workflow. Los tableros y fichas son Markdown con frontmatter YAML compatible con Dataview.
