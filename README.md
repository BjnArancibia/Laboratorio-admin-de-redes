# Operación Despliegue — repositorio de equipo01

Este es el repositorio de tu equipo. Las instrucciones completas están en la guía del laboratorio (PDF).

## Qué hay aquí

| Ruta | Qué es |
|------|--------|
| `frontend/`, `catalog/`, `orders/`, `worker/` | Los cuatro servicios de la tienda |
| `db/init.sql` | Esquema y datos iniciales de PostgreSQL |
| `docker-compose.yml` | Esqueleto que debes completar |
| `.env` | Variables **únicas de tu equipo** (puerto, claves, identificador) |
| `DECISIONES.md` | Registro de decisiones que debes completar |
| `tools/verify.py` | Verificador: mide lo mismo que usará el docente |

## Reglas rápidas

- No cambies el código de las aplicaciones (`main.py`, `server.js`, `worker.py`, `index.html`, `default.conf`, `init.sql`).
- No modifiques `tools/verify.py`.
- Cada integrante debe tener commits propios en al menos dos servicios distintos.
- Haz commit seguido; el docente evalúa el estado de tu repositorio.

## Verificar tu avance

```bash
python3 tools/verify.py            # construye, levanta el stack y mide todo
python3 tools/verify.py --static   # solo revisiones que no necesitan Docker
python3 tools/verify.py --down     # al terminar, apaga el stack
```
