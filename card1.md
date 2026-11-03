# INCIDENTE 1 — Cambio de requisito

**De:** Marketing  **Prioridad:** alta  **Tiempo sugerido:** 15 minutos

La tienda sale a otro mercado esta tarde. Necesitamos dos cambios **sin tocar el código de la aplicación**
(solo configuración: `.env`, `docker-compose.yml`, Dockerfiles):

1. La tienda debe publicarse en el puerto **19000 + el número de tu equipo**
   (equipo 07 → puerto 19007).
2. Los precios del catálogo deben mostrarse en la moneda que corresponde a tu equipo
   (la app lee la variable de entorno `CURRENCY`):

   | Número de equipo (resto de dividir por 4) | Moneda |
   |-------------------------------------------|--------|
   | 0 | CLP |
   | 1 | EUR |
   | 2 | BRL |
   | 3 | MXN |

   Ejemplo: equipo 07 → 7 mod 4 = 3 → MXN.

## Cómo comprobar tu solución

```bash
python3 incident1.py
```

Si dice `RESUELTO`, haz commit de tus cambios. Anota en `DECISIONES.md` qué cambiaste y cuánto demoraste.
