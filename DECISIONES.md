# Registro de decisiones — equipo01

Integrantes:
- **Matías Valenzuela** (`mvalenzuela21@alumnos.utalca.cl`) — Rol B (`orders`, `frontend` y revisión cruzada)
- **Cristóbal Herrera** (`cherrera21@alumnos.utalca.cl`) — Rol A (`catalog` y `worker`)
- **Benjamín Arancibia** (`benyamindragon@gmail.com`) — Rol C (`docker-compose.yml`, `.dockerignore` y seguridad)

Completa **una fila por decisión**. Explica el porqué en una o dos frases: la defensa oral se basa en este documento.

## Decisiones técnicas (obligatorias)

| # | Decisión | Alternativas que consideraron | Por qué eligieron esta | Riesgo o costo que aceptan |
|---|----------|-------------------------------|------------------------|----------------------------|
| 1 | Imagen base de `catalog` y `worker` (`python:3.12-alpine` con multi-stage y `/opt/venv`) | `python:3.12` (Debian completa ~1 GB), `python:3.12-slim` (~150 MB) | `python:3.12-alpine` con construcción multi-stage y entorno virtual reduce el tamaño final (~80-95 MB, muy bajo el límite de 250 MB) y minimiza la superficie de ataque dejando herramientas de build fuera de la imagen final. | Alpine utiliza `musl` en lugar de `glibc`, por lo que requiere instalar explícitamente `libpq` (`apk add --no-cache libpq`) en la etapa final para asegurar compatibilidad con `psycopg2-binary`. |
| 2 | Imagen base de `orders` (`node:20-alpine` con multi-stage build) | `node:20` (~1.1 GB), `node:20-bookworm-slim` (~200 MB), `gcr.io/distroless/nodejs20` | `node:20-alpine` mantiene la imagen bajo ~145 MB (límite 250 MB), incluye el usuario sin privilegios `node` de fábrica y dispone de `wget` en BusyBox para el `HEALTHCHECK`. | Depuración más limitada dentro del contenedor y posibles incompatibilidades si en el futuro se agregan módulos nativos en C++ que dependan de `glibc`. |
| 3 | Imagen base y usuario de `frontend` (`nginxinc/nginx-unprivileged:alpine` con usuario `nginx` en puerto `8080`) | `nginx:alpine` oficial corriendo como `root` o modificando manualmente permisos de `/var/cache/nginx` y `/run/nginx.pid` | La imagen oficial `nginxinc/nginx-unprivileged:alpine` (~45 MB, límite 100 MB) ya viene preconfigurada para escuchar en el puerto `8080` y ejecutarse directamente bajo el usuario no-root `nginx` (UID 101). | No puede enlazar puertos privilegiados (<1024) dentro del contenedor, por lo que requiere mapear `${FRONTEND_PORT}:8080` desde Docker Compose. |
| 4 | Cómo se manejan los secretos (contraseña de la base y `TEAM_SECRET`) | Definir `ENV` o `ARG` en el `Dockerfile`, o usar Docker Secrets con archivos montados en `/run/secrets/` | Se eliminaron todas las credenciales de los `Dockerfile`, se excluyó `.env` en los 4 `.dockerignore` y se inyectan solo en tiempo de ejecución mediante `env_file: .env` en `docker-compose.yml` porque el código de las apps lee `os.environ` / `process.env`. | El archivo `.env` reside en texto plano en el host y las variables son visibles con `docker inspect` en el contenedor en ejecución; en producción real usaríamos Docker Secrets o un gestor externo (Vault). |
| 5 | Diseño de redes: `public-net` (frontend, catalog, orders) e `internal-net` (catalog, orders, worker, db, cache) | Una única red `default` compartida por los 6 servicios, o 4 redes punto a punto por par de servicios | Separar en dos redes bridge garantiza que `frontend` solo alcance a `catalog` y `orders`, aislando completamente a `db`, `cache` y `worker` de la capa expuesta al navegador. | `catalog`, `orders`, `worker`, `db` y `cache` comparten `internal-net`, por lo que `catalog` aún tiene visibilidad de red hacia `cache` aunque no la utilice. |
| 6 | Healthcheck de `worker` (antigüedad de `/tmp/healthy` < 30s) y de `db` (`pg_isready`) / `cache` (`redis-cli ping`) | Para `worker`: revisar solo si el PID de Python existe (`pgrep`); para `db`/`cache`: revisar solo si el puerto TCP está abierto (`nc -z`) | `worker` no expone HTTP pero actualiza `/tmp/healthy` en cada ciclo (~5s), por lo que verificar `time.time() - os.path.getmtime('/tmp/healthy') < 30` comprueba que el bucle realmente no está bloqueado; `pg_isready` y `redis-cli ping` validan que el motor acepta consultas. | Ejecutar un subproceso cada 5s en cada contenedor añade un consumo marginal de CPU/I/O en el host. |
| 7 | Dónde viven los datos y cómo sobreviven a un reinicio (volumen nombrado `pgdata` en `/var/lib/postgresql/data`) | Bind mount a una carpeta local (`./data:/var/lib/postgresql/data`) o almacenamiento efímero del contenedor | Un volumen nombrado (`pgdata`) gestionado por Docker conserva las tablas y pedidos tras `docker compose down` y evita problemas de permisos de archivos entre Windows/Linux y el usuario `postgres` del contenedor. | Si alguien ejecuta `docker compose down -v`, el volumen nombrado se elimina junto con los datos si no existe un respaldo externo (`pg_dump`). |

## Problemas que encontraron y cómo los diagnosticaron

1. **Error tipográfico en la imagen base de `orders/Dockerfile` (`node:20-alpne`):**
   - **Diagnóstico:** Al revisar `orders/Dockerfile` y ejecutar `docker compose build orders`, Docker falló inmediatamente con el mensaje de error: `ERROR: failed to solve: node:20-alpne: failed to resolve source metadata for docker.io/library/node:20-alpne: pull access denied, repository does not exist or may require 'docker login': manifest for node:20-alpne not found`.
   - **Solución:** Se corrigió el tag a `FROM node:20-alpine` y se reestructuró en dos etapas (`deps` y `runner`) con usuario `node` y `HEALTHCHECK`.

2. **Fuga de secretos, ejecución como `root` y compiladores pesados en `catalog/Dockerfile`:**
   - **Diagnóstico:** Al ejecutar `python tools/verify.py --static` (`catalog/Dockerfile tiene 1 FROM; falta .dockerignore`) e inspeccionar `catalog/Dockerfile`, detectamos que tenía `ENV POSTGRES_PASSWORD=<secreto_expuesto>` hardcodeado en una capa de la imagen, instalaba `gcc` y `libpq-dev` en la misma etapa final sobre `python:3.12` (>1 GB) y copiaba todo el código (`COPY . /app`) antes de `pip install -r requirements.txt` (invalidando la caché de capas en cada cambio de código).
   - **Solución:** Se eliminó `ENV POSTGRES_PASSWORD`, se implementó un multi-stage build con `python:3.12-alpine` y `/opt/venv`, se copió `requirements.txt` antes del código, se añadió `libpq` y el usuario sin privilegios `10001:10001`, y se crearon los `.dockerignore` de los 4 servicios.

3. **Inicialización y orden de arranque de la base de datos y servicios de backend:**
   - **Diagnóstico:** Al revisar el esqueleto inicial de `docker-compose.yml` con `docker compose config`, observamos que `db` no montaba `./db/init.sql` en `/docker-entrypoint-initdb.d/` ni tenía `healthcheck`, por lo que `catalog`, `orders` y `worker` arrancaban antes de que PostgreSQL estuviera listo para aceptar conexiones.
   - **Solución:** Se configuraron los healthchecks de `db` y `cache` y se añadió `depends_on` con `condition: service_healthy` en `catalog`, `orders`, `worker` y `frontend`.

## Pendientes concretos para la segunda sesión

- Realizar las pruebas de respuesta ante los 3 incidentes en vivo que aplicará el docente en la Sesión 2 y registrarlos en la tabla de Incidentes.
- Preparar la defensa oral individual de las 7 decisiones técnicas y la demostración de `python tools/verify.py` obteniendo 50/50 puntos.

## Incidentes

| Incidente | Qué pasó | Qué cambiaron | Cuánto demoraron |
|-----------|----------|---------------|------------------|
| 1 | _(Se evalúa en la Sesión 2)_ | | |
| 2 | _(Se evalúa en la Sesión 2)_ | | |
| 3 | _(Se evalúa en la Sesión 2)_ | | |

## Uso de IA

Utilizamos un asistente de IA como apoyo para analizar la rúbrica de `tools/verify.py`, estructurar los multi-stage builds y revisar la sintaxis de los healthchecks. Tuvimos que verificar y ajustar tres puntos clave respecto a sugerencias genéricas:
1. En las imágenes Python basadas en Alpine (`catalog` y `worker`), añadimos explícitamente `apk add --no-cache libpq` en la etapa final y `--chown=10001:10001` para evitar errores de librerías dinámicas y permisos con el usuario no-root.
2. En `catalog/.dockerignore` y `worker/.dockerignore`, corregimos un error tipográfico (`__pycache_` -> `__pycache__/`) para excluir efectivamente la caché de bytecode de Python.
3. Ajustamos el orden de instrucciones `COPY` en `orders/Dockerfile` y `catalog/Dockerfile` para que el test automático de caché (`check_cache`) no reinstale dependencias al editar `server.js` o `main.py`.

## Qué haríamos distinto con más tiempo

1. **Gestión de secretos con Docker Secrets:** En lugar de pasar contraseñas por variables de entorno desde `.env`, montaríamos archivos en `/run/secrets/postgres_password` (adaptando las aplicaciones para leer `POSTGRES_PASSWORD_FILE`).
2. **Aislamiento de red aún más estricto (`internal: true`):** Separaríamos la red interna en una red de base de datos (`db-net`) y otra de cola (`redis-net`) con `internal: true` para que `catalog` no tenga visibilidad de red hacia Redis y ningún servicio interno tenga salida a Internet.
3. **Fijación de versiones por digest SHA256 y escaneo de vulnerabilidades:** Fijaríamos los digests inmutables de las imágenes base (`node:20-alpine@sha256:...`) e integraríamos `docker scout` o `trivy` en un pipeline de CI (GitHub Actions) antes de cada merge a `main`.
