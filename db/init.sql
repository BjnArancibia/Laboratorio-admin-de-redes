-- Esquema inicial de la tienda. NO modificar.
-- Postgres ejecuta este archivo solo la primera vez que inicializa un volumen vacío.

CREATE TABLE IF NOT EXISTS products (
    id    SERIAL PRIMARY KEY,
    name  TEXT           NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           SERIAL PRIMARY KEY,
    product_id   INT         NOT NULL REFERENCES products (id),
    qty          INT         NOT NULL CHECK (qty > 0),
    status       TEXT        NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

INSERT INTO products (name, price)
SELECT * FROM (VALUES
    ('Teclado mecánico',  49.90),
    ('Mouse inalámbrico', 19.90),
    ('Monitor 24 pulgadas', 129.00)
) AS seed (name, price)
WHERE NOT EXISTS (SELECT 1 FROM products);
