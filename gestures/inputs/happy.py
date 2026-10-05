"""Sonrisa (happy).

Cómo se hace: Sonreír amplio ~1 s y relajar.
Grabación de entrenamiento: happyface*.csv
Notas: Señal clara de músculos de la cara.
"""

NAME = "happy"
RECORDING = "happyface*"          # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "happy"                   # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = ""
FLIGHT = "ADELANTE"               # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.8                # pausa mínima entre dos detecciones de este gesto
