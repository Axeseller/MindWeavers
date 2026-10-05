"""Cuello a la izquierda.

Cómo se hace: Girar la cabeza a la izquierda y regresar al centro.
Grabación de entrenamiento: cuelloizq*.csv
Notas: El regreso al centro es otro movimiento; la pausa de 2.8 s y la etapa 'gesto vs otro' evitan que cuente doble. Choca con giro_imag_izq: no activar los dos.
"""

NAME = "cuello_izq"
RECORDING = "cuelloizq*"          # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "cuello"                  # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "izq"
FLIGHT = "MOVER_IZQUIERDA"        # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.8                # pausa mínima entre dos detecciones de este gesto
