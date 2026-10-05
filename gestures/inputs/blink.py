"""Pestañeo.

Cómo se hace: Pestañear fuerte una vez.
Grabación de entrenamiento: blink3sec*.csv
Notas: También se pestañea sin querer, por eso va a una acción inofensiva.
"""

NAME = "blink"
RECORDING = "blink3sec*"          # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "blink"                   # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = ""
FLIGHT = "FOTO"                   # función de vuelo que dispara
USES_EYES = True                  # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 1.5                # pausa mínima entre dos detecciones de este gesto
