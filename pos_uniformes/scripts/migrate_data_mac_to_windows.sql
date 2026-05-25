-- =============================================================
-- Migración de datos Mac → Windows  (2026-05-25)
-- Ejecutar DESPUÉS de: git pull + alembic upgrade head
-- Idempotente: seguro de ejecutar múltiples veces.
-- =============================================================
--
-- Cambios incluidos:
--   1. tipo_pieza.tipo_uniforme  — corrección por si la migración
--      Alembic no ejecutó el UPDATE deportivo
--   2. producto.genero           — Hombre / Mujer / Unisex
--   3. catalog_school_product_link — olan Blanca Verónica, manga corta
-- =============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. tipo_pieza.tipo_uniforme
--    (La columna se crea vía alembic; esto garantiza los datos)
-- ---------------------------------------------------------------
UPDATE tipo_pieza SET tipo_uniforme = 'deportivo'
WHERE nombre IN ('Pants 3pz', 'Pants 2pz', 'Pants Suelto', 'Chamarra', 'Playera');

UPDATE tipo_pieza SET tipo_uniforme = 'oficial'
WHERE tipo_uniforme IS NULL;

-- ---------------------------------------------------------------
-- 2. producto.genero
-- ---------------------------------------------------------------

-- 2a. Productos masculinos
UPDATE producto SET genero = 'Hombre' WHERE nombre_base IN (
    'Camisa Manga Larga H Blanca',
    'Pantalón Escoces',
    'Pantalón Escoces Margarita Paz Paredes',
    'Pantalón Gabardina Negro',
    'Pantalón Gales azul',
    'Pantalón Gales rojo',
    'Pantalón Gales verde',
    'Pantalón Vestir Azul Marino',
    'Pantalón Vestir Azul Rey',
    'Pantalón Vestir Blanco',
    'Pantalón Vestir Café',
    'Pantalón Vestir Caqui',
    'Pantalón Vestir Gris',
    'Pantalón Vestir Gris claro',
    'Pantalón Vestir Gris obscuro',
    'Pantalón Vestir Negro',
    'Pantalón Vestir Pata de gallo',
    'Pantalón Vestir Verde',
    'Pantalón Vestir Verde olivo',
    'Pantalón Vestir Vino',
    'Playera Deportiva H SABES',
    'Suéter Claudia Cuello V H Azul Marino',
    'Suéter Claudia Cuello V H Azul Rey',
    'Suéter Claudia Cuello V H Blanco',
    'Suéter Claudia Cuello V H Negro',
    'Suéter Claudia Cuello V H Rojo',
    'Suéter Claudia Cuello V H Verde',
    'Suéter Claudia Cuello V H Vino',
    'Suéter Cuello V Azul Marino Ignacio Ramírez López',
    'Suéter Cuello V H Azul Adolfo López Mateo',
    'Suéter Cuello V H Azul Albino García Ramos',
    'Suéter Cuello V H Azul Marino Álvaro Obregón El Carretón',
    'Suéter Cuello V H Azul Marino Club Rotario',
    'Suéter Cuello V H Azul Marino Francisco Villa',
    'Suéter Cuello V H Azul Marino Miguel Campuzano',
    'Suéter Cuello V H Azul Marino Miguel Hidalgo',
    'Suéter Cuello V H Azul Marino Telesecundaria 512',
    'Suéter Cuello V H Blanca Verónica Soto Martínez Príncipes',
    'Suéter Cuello V H Frida Kahlo',
    'Suéter Cuello V H Jorge Cantor',
    'Suéter Cuello V H Negro Huizache',
    'Suéter Cuello V H Patria',
    'Suéter Cuello V H Rojo Benito Juárez',
    'Suéter Cuello V H Rojo CBTIS 148',
    'Suéter Cuello V H Rojo Ignacio Allende',
    'Suéter Cuello V H Rojo José María Morelos y Pavón',
    'Suéter Cuello V H Rojo Justo Sierra',
    'Suéter Cuello V H Sor Juana Inés de la Cruz',
    'Suéter Cuello V H Telesecundaria 600',
    'Suéter Cuello V H Verde Bicentenario',
    'Suéter Cuello V H Verde Conalep',
    'Suéter Cuello V H Verde Práxedis Guerrero Secundaria',
    'Suéter Cuello V H Vicente Guerrero',
    'Suéter Cuello V H Vino Práxedis Guerrero',
    'Suéter Cuello V H Vino Vicente Guerrero',
    'Sueter Cuello V Lic. Benito Juárez'
);

-- 2b. Productos femeninos
UPDATE producto SET genero = 'Mujer' WHERE nombre_base IN (
    'Blusa de Dama',
    'Blusa de Dama II',
    'Blusa de Dama III',
    'Camisa Cuello olan Azul',
    'Camisa Cuello olan Blanca',
    'Camisa Cuello olan Rojo',
    'Camisa Cuello olan Vino',
    'Camisa Manga Larga M Blanca',
    'Falda Cuatro tablas Azul Rey',
    'Falda Cuatro tablas Blanca',
    'Falda Cuatro tablas Café',
    'Falda Cuatro tablas Verde',
    'Falda Escoces',
    'Falda Escoces Conalep',
    'Falda Escoces Margarita Paz Paredes',
    'Falda Escolar Azul Marino',
    'Falda Escolar Pata de Gallo Colegio Motolinea',
    'Falda Escolar Pgallo cafe',
    'Falda Gales azul',
    'Falda Gales rojo',
    'Falda Gales verde',
    'Falda Gris claro',
    'Falda Gris obscuro',
    'Falda SABES',
    'Falda Tableada Azul Rey',
    'Falda Tableada Blanca',
    'Falda Tableada Café',
    'Falda Tableada Verde',
    'Falda Vino',
    'Jeans Brillos Adulto',
    'Jumper Azul Marino',
    'Jumper Beige',
    'Jumper Escoces',
    'Licra',
    'Malla Escolar Azul Marino',
    'Malla Escolar Beige',
    'Malla Escolar Blanca',
    'Malla Escolar Negro',
    'Malla Escolar Rojo',
    'Malla Escolar Verde',
    'Malla Escolar Vino',
    'Mascada Verde Conalep',
    'Pantalon vestir Mujer',
    'Playera Deportiva M SABES',
    'Suéter Botones Azul Marino Ignacio Ramírez López',
    'Sueter Botones Lic. Benito Juárez',
    'Suéter Botones M Azul Adolfo López Mateo',
    'Suéter Botones M Azul Albino García Ramos',
    'Suéter Botones M Azul Marino Álvaro Obregón El Carretón',
    'Suéter Botones M Azul Marino Club Rotario',
    'Suéter Botones M Azul Marino Francisco Villa',
    'Suéter Botones M Azul Marino Miguel Campuzano',
    'Suéter Botones M Azul Marino Miguel Hidalgo',
    'Suéter Botones M Azul Marino Telesecundaria 512',
    'Suéter Botones M Blanca Verónica Soto Martínez Príncipes',
    'Suéter Botones M Frida Kahlo',
    'Suéter Botones M Jorge Cantor',
    'Suéter Botones M Negro Huizache',
    'Suéter Botones M Patria',
    'Suéter Botones M Rojo Benito Juárez',
    'Suéter Botones M Rojo CBTIS 148',
    'Suéter Botones M Rojo Ignacio Allende',
    'Suéter Botones M Rojo José María Morelos y Pavón',
    'Suéter Botones M Rojo Justo Sierra',
    'Suéter Botones M Sor Juana Inés de la Cruz',
    'Suéter Botones M Telesecundaria 600',
    'Suéter Botones M Verde Bicentenario',
    'Suéter Botones M Verde Conalep',
    'Suéter Botones M Verde Práxedis Guerrero Secundaria',
    'Suéter Botones M Vicente Guerrero',
    'Suéter Botones M Vino Práxedis Guerrero',
    'Suéter Botones M Vino Vicente Guerrero',
    'Suéter Claudia Botones M Azul Marino',
    'Suéter Claudia Botones M Azul Rey',
    'Suéter Claudia Botones M Blanco',
    'Suéter Claudia Botones M Negro',
    'Suéter Claudia Botones M Rojo',
    'Suéter Claudia Botones M Verde',
    'Suéter Claudia Botones M Vino'
);

-- 2c. Todo lo que quedó sin clasificar → Unisex
UPDATE producto SET genero = 'Unisex' WHERE genero IS NULL;

-- ---------------------------------------------------------------
-- 3. catalog_school_product_link
-- ---------------------------------------------------------------

-- 3a. Olan Blanca → desactivar para Blanca Verónica
UPDATE catalog_school_product_link
SET activo = false
WHERE escuela_id = (SELECT id FROM escuela WHERE nombre = 'Blanca Verónica Soto Martínez Príncipes')
  AND producto_id IN (
      SELECT id FROM producto WHERE nombre_base = 'Camisa Cuello olan Blanca'
  );

-- 3b. Olan Rojo → activar para Blanca Verónica
INSERT INTO catalog_school_product_link (escuela_id, producto_id, activo, created_at)
SELECT
    (SELECT id FROM escuela WHERE nombre = 'Blanca Verónica Soto Martínez Príncipes'),
    (SELECT id FROM producto
     WHERE nombre_base = 'Camisa Cuello olan Rojo'
     ORDER BY (escuela_id IS NULL) DESC, id ASC LIMIT 1),
    true,
    NOW()
ON CONFLICT ON CONSTRAINT uq_school_product_link DO UPDATE SET activo = true;

-- 3c. Manga Corta Blanca → activar para Blanca Verónica
INSERT INTO catalog_school_product_link (escuela_id, producto_id, activo, created_at)
SELECT
    (SELECT id FROM escuela WHERE nombre = 'Blanca Verónica Soto Martínez Príncipes'),
    (SELECT id FROM producto
     WHERE nombre_base = 'Camisa Manga Corta Blanca'
     ORDER BY (escuela_id IS NULL) DESC, id ASC LIMIT 1),
    true,
    NOW()
ON CONFLICT ON CONSTRAINT uq_school_product_link DO UPDATE SET activo = true;

-- 3d. Manga Corta Blanca → activar para Frida Kahlo
INSERT INTO catalog_school_product_link (escuela_id, producto_id, activo, created_at)
SELECT
    (SELECT id FROM escuela WHERE nombre = 'Frida Kahlo'),
    (SELECT id FROM producto
     WHERE nombre_base = 'Camisa Manga Corta Blanca'
     ORDER BY (escuela_id IS NULL) DESC, id ASC LIMIT 1),
    true,
    NOW()
ON CONFLICT ON CONSTRAINT uq_school_product_link DO UPDATE SET activo = true;

-- 3e. Manga Corta Blanca → activar para Margarita Paz Paredes
INSERT INTO catalog_school_product_link (escuela_id, producto_id, activo, created_at)
SELECT
    (SELECT id FROM escuela WHERE nombre = 'Margarita Paz Paredes'),
    (SELECT id FROM producto
     WHERE nombre_base = 'Camisa Manga Corta Blanca'
     ORDER BY (escuela_id IS NULL) DESC, id ASC LIMIT 1),
    true,
    NOW()
ON CONFLICT ON CONSTRAINT uq_school_product_link DO UPDATE SET activo = true;

COMMIT;
