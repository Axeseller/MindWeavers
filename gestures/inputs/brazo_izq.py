"""Brazo izquierdo arriba.

Cómo se hace: Levantar el brazo izquierdo y bajarlo.
Grabación de entrenamiento: brazoizquierdo*.csv
Notas: Muy fácil de detectar. Distinguir izquierdo de derecho es lo más débil del sistema (~92 %).
"""

NAME = "brazo_izq"
RECORDING = "brazoizquierdo*"     # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "brazo"                   # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "izq"
FLIGHT = "BAJAR"                  # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.2                # pausa mínima entre dos detecciones de este gesto
