"""Puño izquierdo.

Cómo se hace: Cerrar el puño izquierdo con fuerza ~1 s y soltar.
Grabación de entrenamiento: pu*oizquierdo*.csv
Notas: Casi no deja señal muscular en el casco; se detecta por el leve movimiento de cabeza al apretar. Un puño débil puede pasar desapercibido.
"""

NAME = "puno_izq"
RECORDING = "pu*oizquierdo*"      # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "puno"                    # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "izq"
FLIGHT = "GIRAR_IZQUIERDA"        # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.2                # pausa mínima entre dos detecciones de este gesto
