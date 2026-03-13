# Plantillas por Patron

Fuente analizada: `/Users/danielfabian/Documents/Playground 2/Gestor_de_Inventarios/data/productos.db`

Fecha de analisis: `2026-03-12`

## Hallazgos

- La base legacy contiene `4034` productos.
- Los patrones fuertes estan en `Uniformes`; la ropa general todavia no domina el catalogo.
- Las plantillas completas actuales pueden reducirse y dividirse por paso del formulario:
  - `Base`
  - `Contexto`
  - `Presentaciones`

## Patrones dominantes

### Contextos mas repetidos

1. `Deportivo / Chamarra / Deportiva / Primaria / Con Escudo`
2. `Deportivo / Pants 2pz / Deportivo / Primaria / Con Escudo`
3. `Deportivo / Pants 3pz / Deportivo / Primaria / Con Escudo`
4. `Deportivo / Playera / Deportiva / Primaria / Con Escudo`
5. `Oficial / Sueter / Botones / Primaria / Mujer / Con Escudo`
6. `Oficial / Sueter / Cuello V / Primaria / Hombre / Con Escudo`
7. `Oficial / Chaleco / Primaria / Con Escudo`
8. `Deportivo / Playera / Deportiva / Secundaria / Con Escudo`
9. `Deportivo / Pants 2pz / Deportivo / Secundaria / Con Escudo`
10. `Deportivo / Playera / Deportiva / Bachillerato / Con Escudo`
11. `Basico / Pantalon / Vestir`
12. `Basico / Falda`
13. `Basico / Pants 2pz / Liso`
14. `Basico / Chamarra / Liso`
15. `Basico / Pants Suelto / Liso`
16. `Basico / Pants 2pz / Punto`
17. `Basico / Chamarra / Punto`
18. `Basico / Pants Suelto / Punto`
19. `Basico / Sueter / Botones / Mujer`
20. `Basico / Sueter / Cuello V / Hombre`
21. `Basico / Chaleco / Unisex`
22. `Accesorio / Malla / Escolar`
23. `Basico / Jumper`

### Tallas mas repetidas

- `4, 6, 8, 10, 12, 14, 16`
- `4, 6, 8, 10, 12, 14, 16, CH, MD, GD`
- `12, 14, 16, CH, MD, GD, EXG`
- `16, CH, MD, GD, EXG`
- `0-0, 0-2, 3-5, 6-8, 9-12, 13-18, CH-MD, GD-EXG, Dama`
- `Uni`

### Colores mas repetidos

- `Ad hoc` para deportivos escolares
- `Azul Marino`
- `Rojo`
- `Blanca`
- `Verde`
- `Vino`
- `Gales rojo / verde / azul`
- `Escoces`

## Propuesta de plantillas por paso

## Paso 1 · Base

Estas plantillas solo afectan:

- categoria
- marca sugerida
- nombre base sugerido
- descripcion corta

### Plantillas base recomendadas

1. `Playera deportiva`
2. `Chamarra deportiva`
3. `Pants 2pz deportivo`
4. `Pants 3pz deportivo`
5. `Sueter botones`
6. `Sueter cuello V`
7. `Chaleco oficial`
8. `Pantalon vestir`
9. `Falda escolar`
10. `Pants 2pz basico`
11. `Pants suelto`
12. `Malla escolar`
13. `Jumper`
14. `Camisa manga corta`
15. `Camisa manga larga`

## Paso 2 · Contexto

Estas plantillas solo afectan:

- escuela
- nivel educativo
- tipo prenda
- tipo pieza
- atributo
- genero
- escudo
- ubicacion

### Plantillas de contexto recomendadas

1. `Primaria deportiva con escudo`
2. `Preescolar deportiva con escudo`
3. `Secundaria deportiva con escudo`
4. `Bachillerato deportiva con escudo`
5. `Primaria oficial mujer`
6. `Primaria oficial hombre`
7. `Secundaria oficial mujer`
8. `Secundaria oficial hombre`
9. `Basico general`
10. `Accesorio escolar`

## Paso 3 · Presentaciones

Estas plantillas solo afectan:

- tallas
- colores
- precio sugerido
- stock inicial opcional

### Plantillas de presentaciones recomendadas

1. `Primaria deportiva`
   - Tallas: `4, 6, 8, 10, 12, 14, 16, CH, MD, GD`
   - Colores: `Ad hoc`

2. `Preescolar deportiva`
   - Tallas: `2, 4, 6, 8` o `4, 6, 8, 10`
   - Colores: `Ad hoc`

3. `Secundaria deportiva`
   - Tallas: `10, 12, 14, 16, CH, MD, GD`
   - Colores: `Ad hoc`

4. `Bachillerato deportiva`
   - Tallas: `12, 14, 16, CH, MD, GD, EXG`
   - Colores: `Ad hoc`

5. `Oficial primaria mujer`
   - Tallas: `6, 8, 10, 12, 14, 16, 34, 36, 38, 40`
   - Colores: `Azul Marino, Rojo, Azul, Vino, Negro`

6. `Oficial primaria hombre`
   - Tallas: `6, 8, 10, 12, 14, 16, 28, 30, 32, 34, 36, 38, 40`
   - Colores: `Azul Marino, Rojo, Azul, Vino, Negro`

7. `Basico infantil`
   - Tallas: `2, 4, 6, 8, 10, 12, 14, 16`
   - Colores: `Rojo, Blanco, Vino, Gris, Azul Marino, Verde, Azul Rey`

8. `Basico mixto`
   - Tallas: `4, 6, 8, 10, 12, 14, 16, 28, 30, 32, 34, 36, 38, 40`
   - Colores: `Azul Marino, Blanco, Negro, Rojo, Verde, Vino`

9. `Malla escolar`
   - Tallas: `0-0, 0-2, 3-5, 6-8, 9-12, 13-18, CH-MD, GD-EXG, Dama`
   - Colores: `Rojo, Beige, Vino, Azul Marino, Negro, Verde`

10. `Unitalla accesorio`
    - Tallas: `Uni`
    - Colores: segun pieza

## Plantillas maestras sugeridas

Estas serian las primeras plantillas combinables a implementar:

1. `Base / Playera deportiva`
2. `Base / Chamarra deportiva`
3. `Base / Pants 2pz deportivo`
4. `Base / Pants 3pz deportivo`
5. `Base / Sueter botones`
6. `Base / Sueter cuello V`
7. `Base / Pantalon vestir`
8. `Base / Falda escolar`

9. `Contexto / Primaria deportiva con escudo`
10. `Contexto / Preescolar deportiva con escudo`
11. `Contexto / Secundaria deportiva con escudo`
12. `Contexto / Bachillerato deportiva con escudo`
13. `Contexto / Primaria oficial mujer`
14. `Contexto / Primaria oficial hombre`
15. `Contexto / Basico general`

16. `Presentaciones / Primaria deportiva`
17. `Presentaciones / Preescolar deportiva`
18. `Presentaciones / Secundaria deportiva`
19. `Presentaciones / Bachillerato deportiva`
20. `Presentaciones / Oficial primaria mujer`
21. `Presentaciones / Oficial primaria hombre`
22. `Presentaciones / Basico infantil`
23. `Presentaciones / Malla escolar`

## Reduccion recomendada

En lugar de muchas plantillas completas, empezar con:

- `8` plantillas base
- `7` plantillas de contexto
- `8` plantillas de presentaciones

Total inicial recomendado: `23`

Eso cubre la mayor parte del catalogo legacy sin saturar la interfaz.

## Implementacion sugerida

### Fase 1

- Mantener la plantilla global actual solo como compatibilidad.
- Agregar un selector de plantilla por paso:
  - `Base`
  - `Contexto`
  - `Presentaciones`

### Fase 2

- Permitir aplicar una plantilla sin tocar las otras secciones.
- Mostrar en el resumen final que plantillas se aplicaron.

### Fase 3

- Guardar plantillas nuevas desde el propio formulario por paso.
- Permitir clonar una plantilla existente y ajustarla.

### Fase 4

- Agregar plantillas separadas por `tipo_catalogo`:
  - `Uniformes`
  - `Ropa general`

