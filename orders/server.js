// Servicio orders: recibe pedidos, los guarda en PostgreSQL y los encola en Redis.
// NO modificar el código de la app.
//
// Puerto interno: 3000 (variable PORT)
// Variables: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DB_HOST (def. "db"), REDIS_HOST (def. "cache")
'use strict';

const express = require('express');
const { Pool } = require('pg');
const { createClient } = require('redis');

const app = express();
app.use(express.json());

const pool = new Pool({
  host: process.env.DB_HOST || 'db',
  user: process.env.POSTGRES_USER,
  password: process.env.POSTGRES_PASSWORD,
  database: process.env.POSTGRES_DB,
  max: 5,
  connectionTimeoutMillis: 3000,
});
pool.on('error', (err) => console.error('pg pool error:', err.message));

const redis = createClient({
  url: `redis://${process.env.REDIS_HOST || 'cache'}:6379`,
  socket: { reconnectStrategy: (retries) => Math.min(retries * 200, 2000) },
  disableOfflineQueue: true,
});
redis.on('error', (err) => console.error('redis error:', err.message));
redis.connect().catch((err) => console.error('redis connect:', err.message));

app.get('/healthz', (_req, res) => res.json({ status: 'ok' }));

app.post('/api/orders', async (req, res) => {
  const productId = Number.parseInt(req.body && req.body.product_id, 10);
  const qty = Number.parseInt(req.body && req.body.qty, 10);
  if (!Number.isInteger(productId) || !Number.isInteger(qty) || qty < 1) {
    return res.status(400).json({ error: 'product_id y qty (>=1) son obligatorios' });
  }
  try {
    const { rows } = await pool.query(
      'INSERT INTO orders (product_id, qty) VALUES ($1, $2) RETURNING id, status',
      [productId, qty]
    );
    await redis.lPush('orders', String(rows[0].id));
    return res.status(201).json(rows[0]);
  } catch (err) {
    console.error('POST /api/orders:', err.message);
    return res.status(503).json({ error: 'servicio no disponible' });
  }
});

app.get('/api/orders/:id', async (req, res) => {
  const id = Number.parseInt(req.params.id, 10);
  if (!Number.isInteger(id)) return res.status(400).json({ error: 'id inválido' });
  try {
    const { rows } = await pool.query(
      'SELECT id, product_id, qty, status FROM orders WHERE id = $1',
      [id]
    );
    if (rows.length === 0) return res.status(404).json({ error: 'no existe' });
    return res.json(rows[0]);
  } catch (err) {
    console.error('GET /api/orders:', err.message);
    return res.status(503).json({ error: 'servicio no disponible' });
  }
});

const port = Number.parseInt(process.env.PORT || '3000', 10);
app.listen(port, '0.0.0.0', () => console.log(`orders escuchando en ${port}`));
