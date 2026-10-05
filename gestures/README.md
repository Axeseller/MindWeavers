# Gestos -> funciones de vuelo (puños y brazos)

Archivos (ninguno toca el repo todavía):

| Archivo | Qué hace |
|---|---|
| `pipeline.py` | Parámetros (`Params`) y todo el procesamiento: limpieza, detección de actividad, ventanas, features |
| `train.py` | Entrena por etapas, valida sin fugas y elige el umbral de confianza de cada etapa |
| `live_classifier.py` | Lee el LSL del Unicorn y escribe la función de vuelo de cada gesto |
| `evaluate_replay.py` | Pasa los CSV por el clasificador en vivo para comprobar la mecánica |

```bash
python train.py --data <carpeta con los CSV>       # crea gesture_model.joblib
python live_classifier.py                          # LSL en vivo
python live_classifier.py --replay puño.csv        # probar con una grabación
```

## Pipeline
1. **Limpieza:** se descartan los primeros 5 s, se quita el DC, se aplica referencia promedio (CAR) y notch de 60 Hz.
2. **Inicio del gesto:** la actividad (EMG 30-100 Hz + giroscopio) debe superar `onset_z`, relativo a los últimos 20 s, **y** el piso absoluto medido en reposo.
3. **Ventana:** 1 s alrededor del pico de actividad (0.3 s antes, 0.7 s después).
4. **Features:** potencia por banda (4-8, 8-13, 13-30, 30-60, 60-100 Hz) x 8 canales, asimetrías C3/C4 y Fz/Oz, resumen del IMU y covarianza entre canales (espacio tangente) en 8-30 y 30-100 Hz.
5. **Filtro de novedad:** si la ventana no se parece a ningún gesto entrenado, el resultado es UNSURE.
6. **Etapas:** B brazo vs puño (LDA) -> C lado izq/der (puño: LDA con todo; brazo: IMU + EMG + forma del movimiento, en una ventana de 0.5 s antes / 1.0 s después; `train.py` elige entre LDA y logística).
7. **Umbrales:** si una etapa no supera su umbral, el resultado es UNSURE y no se manda ningún comando.

## Resultados (validación por bloques de tiempo)
| Etapa | Precisión | Con umbral |
|---|---|---|
| Brazo vs puño | 98.6 % | 0 % de error, contesta 99 % |
| Puño izq vs der | 100 % | 0 % de error, contesta 94 % |
| Brazo izq vs der | 91.7 % (antes 83 %) | 8.3 % de error, contesta 100 % |

## Mapa de vuelo (editar `FLIGHT` en live_classifier.py)
puño izq -> GIRAR_IZQUIERDA · puño der -> GIRAR_DERECHA · brazo der -> SUBIR · brazo izq -> BAJAR

## Pasando las grabaciones por el script en vivo
| Archivo | Decisiones |
|---|---|
| puño izq | 13 correctas, 1 UNSURE |
| puño der | 14 correctas, 1 leída como izq (un puño débil que el entrenamiento no contó) |
| brazo izq | 18 correctas |
| brazo der | 16 correctas, 2 UNSURE |
| reposo | 1 disparo, en el segundo 7, cuando se acomodaban el casco |

El modelo se entrenó con estas mismas grabaciones, así que esta tabla comprueba la mecánica, no el error real.
