# INCIDENTE 3 — Servicio caído

**De:** Operaciones  **Prioridad:** crítica  **Tiempo sugerido:** 15 minutos

A las 03:00 el servidor de Redis murió de golpe y nadie estaba de guardia. Cuando alguien despertó,
la tienda llevaba horas sin procesar pedidos. Dirección pide que **esto no vuelva a ocurrir**:
si un servicio cae, el sistema debe recuperarse solo y seguir procesando pedidos, sin intervención humana.

Reproduce la falla y haz que tu despliegue sobreviva a ella.

## Cómo comprobar tu solución

```bash
python3 incident3.py
```

El script levanta tu stack, mata Redis de golpe y comprueba que el sistema se recupera y procesa un pedido nuevo.
Si dice `RESUELTO`, haz commit de tus cambios. Anota en `DECISIONES.md` qué cambiaste y cuánto demoraste.
