"""Brazo derecho arriba.

Cómo se hace: Levantar el brazo derecho y bajarlo.
Grabación de entrenamiento: brazoarriba*.csv
Notas: Se asume que la grabación 'brazoarriba' es el brazo derecho.
"""

NAME = "brazo_der"
RECORDING = "brazoarriba*"        # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "brazo"                   # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "der"
FLIGHT = "SUBIR"                  # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.2                # pausa mínima entre dos detecciones de este gesto
