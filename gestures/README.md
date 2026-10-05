# Gestos -> funciones de vuelo

Un archivo por input en `inputs/`. Cada uno dice qué grabación usa, qué función de vuelo dispara, si necesita la señal de los ojos y cuánto esperar antes de aceptar otro gesto. Para agregar, quitar o cambiar un gesto solo se toca su archivo.

| Input | Función de vuelo | Grupo |
|---|---|---|
| `puno_izq` / `puno_der` | GIRAR_IZQUIERDA / GIRAR_DERECHA | puño |
| `brazo_izq` / `brazo_der` | BAJAR / SUBIR | brazo |
| `cuello_izq` / `cuello_der` | MOVER_IZQUIERDA / MOVER_DERECHA | cuello |
| `giro_imag_izq` / `giro_imag_der` | GIRAR_IZQUIERDA / GIRAR_DERECHA | giro imaginario |
| `blink` | FOTO | - |
| `happy` | ADELANTE | - |
| `cerrar_ojos` | ATERRIZAR | - |
| `enojado` | ATRAS | - |

## Uso
```bash
python train.py --list                                          # inputs y presets
python train.py --data <carpeta CSV> --preset brazos            # -> models/brazos.joblib
python train.py --data <carpeta CSV> --inputs puno_izq,puno_der,blink,happy
python live_classifier.py --model models/brazos.joblib          # LSL en vivo
python live_classifier.py --model models/brazos.joblib --replay puño.csv
python evaluate_replay.py <carpeta CSV> models/brazos.joblib    # cuenta aciertos/errores
```

Presets validados: `brazos` (puños + brazos), `cabeza` (cuello izq/der, blink, happy) y `mente` (giro imaginario izq/der, cerrar ojos, enojado).

## No actives los 12 a la vez
Probado: con los 12 inputs juntos, 23 de 131 movimientos de regreso se vuelven comandos y los puños casi no se detectan (1-2 de 18). Hay inputs que en la señal son casi lo mismo: `cuello_izq` y `giro_imag_izq` son el mismo movimiento del cuello. Activa 4 o 5 que no choquen. `train.py` avisa si dos de los que elegiste se confunden.

## Pipeline
1. **Limpieza:** se descartan los primeros 5 s, se quita el DC, se aplica referencia promedio (CAR) y notch de 60 Hz.
2. **Inicio del gesto:** la actividad debe superar `onset_z` (relativo a los últimos 20 s) **y** un piso absoluto medido en reposo. Suma EMG 30-100 Hz y giroscopio; si algún input activo tiene `USES_EYES = True`, también la señal de los ojos (EOG frontal 0.5-8 Hz).
3. **Ventanas:** 1 s alrededor del pico de actividad, y otra de 0.5 s antes a 1.0 s después para la forma del movimiento.
4. **Features en dos bloques:**
   - `full`: potencia por banda x 8 canales, asimetrías, IMU y covarianza entre canales.
   - `movement`: IMU, EMG y forma del movimiento.
5. **Rechazos, en orden:**
   - ¿Se parece a algún gesto entrenado? (distancia de novedad)
   - **Etapa A:** ¿es un gesto o solo otro movimiento? (regresar el cuello, bajar el brazo, soltar el puño)
   - Gesto: en una sola etapa, o por grupo y luego izq/der. `train.py` compara los dos diseños y se queda con el que valida mejor. Cada par izq/der elige su bloque de features y tiene su propio umbral.
6. Si algo no supera su umbral, el resultado es UNSURE y no se manda comando. Después de cada gesto se espera el `REFRACTORY_S` de ese input.

## Resultados
Validados por bloques de tiempo:

| Preset | Diseño elegido | Error validado |
|---|---|---|
| brazos | por grupo | 4.5 % (puño izq/der 0 %, brazo izq/der 6.5 %) |
| cabeza | una etapa | 1.7 % |
| mente | una etapa | 1.7 % |

Pasando las grabaciones por el script en vivo:

| Preset | Correctas | Equivocadas | UNSURE | Reposo |
|---|---|---|---|---|
| brazos | 59 | 1 | 12 | 0 comandos |
| cabeza | 47 | 0 | 24 | 0 comandos |
| mente | 44 | 0 | 29 | 0 comandos |

El único error en vivo es la "soltada" de un puño izquierdo en un tramo irregular al final de su grabación, leída como puño derecho con confianza 1.00.

Los UNSURE incluyen los movimientos de regreso, que es correcto descartar, y algunas repeticiones reales que se pierden. Se prefiere no hacer nada a hacer lo equivocado.

El modelo se entrenó con estas mismas grabaciones, así que la tabla en vivo comprueba la mecánica. El error real con otra persona u otro día será mayor. Para bajarlo hace falta grabar los gestos alternados en una misma sesión, con marcas de cuándo empieza cada uno.

## Lo que no se pudo usar
- **`pensamientoadelante`:** la actividad no tiene un ritmo regular, así que sin marcas de cuándo se pensó no se sabe qué ventana es el pensamiento. Hay que regrabarlo con marcas.
- **Giro imaginario:** todavía trae tensión del cuello, así que el modelo lee músculo, no imaginación pura.
- **`baselineojoscerrados`:** es un minuto entero con los ojos cerrados. Sirve de referencia, no como gesto.
- **jaw:** se dejó fuera a propósito. Ya está en el detector del app principal.
