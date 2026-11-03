# INCIDENTE 2 — Vulnerabilidad en imágenes base

**De:** Seguridad de la información  **Prioridad:** crítica  **Tiempo sugerido:** 15 minutos

Se detectó una vulnerabilidad crítica en las versiones antiguas de los runtimes. Política inmediata:

- Toda imagen base de **Python** debe ser **3.13 o superior**.
- Toda imagen base de **Node** debe ser **22 o superior**.
- El tag debe estar escrito de forma **explícita** en cada `FROM` (no sirve una variable, ni `latest`).

Aplica a **todos** los Dockerfiles del proyecto. Después del cambio la tienda debe seguir funcionando
(el flujo de pedidos incluido). Cuida que no se rompan las dependencias al cambiar de versión.

## Cómo comprobar tu solución

```bash
python3 incident2.py
```

Si dice `RESUELTO`, haz commit de tus cambios. Anota en `DECISIONES.md` qué cambiaste y cuánto demoraste.
