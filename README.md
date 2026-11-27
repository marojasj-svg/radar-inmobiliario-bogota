# Radar Inmobiliario Bogotá

Automatización para observar oferta y rotación de apartamentos en tres zonas: Rincón, Mirandela y Salitre. El sistema consulta FincaRaíz y Metrocuadrado, guarda capturas por fecha, mantiene histórico por zona y genera tableros y fichas Markdown para Obsidian.

## Flujo automático

El workflow de GitHub Actions ejecuta `src/scraper.py` y luego `src/analizador.py`. El cron actual realiza cortes cada tres días; también se ejecuta al actualizar código, configuración, dependencias o el workflow. Permite ejecución manual desde **Actions → Monitor Inmobiliario Zona Norte → Run workflow**.

- `config/zonas.json`: límites, estado de calibración y rutas de búsqueda por zona. Las coordenadas se guardan como [latitud, longitud]; el código las convierte al orden requerido por Shapely.
- `data/snapshots/AAAA-MM-DD.json`: corte unificado con anuncios y estado de captura por portal y zona.
- `data/historico_rincon.json`, `data/historico_mirandela.json`, `data/historico_salitre.json`: estado persistente de cada anuncio, fechas detectadas, precios, huellas y salidas probables.
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

## Credenciales y permisos

La captura estructurada consulta FincaRaíz y Metrocuadrado a través de API.SH, un proveedor externo y no afiliado a esos portales. Las búsquedas de Metrocuadrado complementan las coordenadas con las fichas y guardan resultados positivos en `data/cache_coordenadas_metrocuadrado.json` para no repetir consultas. Una captura solo se marca confiable si la cobertura de coordenadas y los anuncios validados dentro del polígono superan los mínimos configurados. Requiere una clave de API guardada en GitHub como secreto `RADAR_DATA_API_KEY` (Settings → Secrets and variables → Actions → New repository secret). Nunca debe pegarse en el código ni en los archivos del radar. API.SH publica 1.000 créditos mensuales gratuitos; cada búsqueda documentada cuesta 1 crédito, con topes configurables en su cuenta. El proveedor puede cambiar su disponibilidad, condiciones y precios; revisa sus [precios](https://api.sh/pricing) antes de activar o continuar el uso. Sin el secreto, el radar marca las capturas como no confiables y no infiere posibles ventas.

GitHub Actions usa además el token temporal `GITHUB_TOKEN` que GitHub crea para cada ejecución. `actions/checkout` conserva la credencial para que el paso final pueda publicar el commit, y el workflow limita el permiso del token a `contents: write`.

En **Settings → Actions → General → Workflow permissions**, habilita permisos de lectura y escritura para que el workflow pueda guardar capturas, históricos y tableros.

## Obsidian

Clona este repositorio dentro de la bóveda o usa Obsidian Git para traer los commits del workflow. Los tableros y fichas son Markdown con frontmatter YAML compatible con Dataview.
