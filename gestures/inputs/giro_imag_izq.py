"""Giro imaginario izquierda.

Cómo se hace: Imaginar girar la cabeza a la izquierda.
Grabación de entrenamiento: girarcabezaimaginariaizq*.csv
Notas: En las grabaciones aún hay tensión del cuello: el modelo lee músculo, no imaginación pura. Choca con cuello_izq.
"""

NAME = "giro_imag_izq"
RECORDING = "girarcabezaimaginariaizq*"# glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "giro_imag"               # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "izq"
FLIGHT = "GIRAR_IZQUIERDA"        # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.5                # pausa mínima entre dos detecciones de este gesto
