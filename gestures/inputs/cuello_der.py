"""Cuello a la derecha.

Cómo se hace: Girar la cabeza a la derecha y regresar al centro.
Grabación de entrenamiento: cuelloderecha*.csv
Notas: Choca con giro_imag_der: no activar los dos.
"""

NAME = "cuello_der"
RECORDING = "cuelloderecha*"      # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "cuello"                  # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "der"
FLIGHT = "MOVER_DERECHA"          # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.8                # pausa mínima entre dos detecciones de este gesto
