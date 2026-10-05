"""Cara de enojo.

Cómo se hace: Fruncir el ceño con fuerza ~1 s y relajar.
Grabación de entrenamiento: enojado*.csv
Notas: Señal de músculos de la frente.
"""

NAME = "enojado"
RECORDING = "enojado*"            # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "enojado"                 # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = ""
FLIGHT = "ATRAS"                  # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.5                # pausa mínima entre dos detecciones de este gesto
