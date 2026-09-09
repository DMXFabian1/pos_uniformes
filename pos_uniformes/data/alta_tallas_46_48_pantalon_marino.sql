-- Alta de tallas 46 y 48 — Pantalón Vestir Azul Marino (producto 334)
-- Precio $355, stock 0 (se contará después). 2026-08-11
WITH sig AS (
  SELECT MAX(CAST(SUBSTRING(sku FROM 4) AS int)) AS n
  FROM variante WHERE sku ~ '^SKU[0-9]+$'
)
INSERT INTO variante (producto_id, sku, talla, color, precio_venta, stock_actual, activo, origen_legacy, disponibilidad_oculta)
SELECT 334, 'SKU' || LPAD((n + fila)::text, 6, '0'), talla, 'Azul Marino', 355.00, 0, true, false, false
FROM sig, (VALUES (1, '46'), (2, '48')) AS t(fila, talla)
RETURNING id, sku, talla, precio_venta;
