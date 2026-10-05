"""Puño derecho.

Cómo se hace: Cerrar el puño derecho con fuerza ~1 s y soltar.
Grabación de entrenamiento: pu*oderecho*.csv
Notas: Igual que el izquierdo: señal débil, la delata el giroscopio.
"""

NAME = "puno_der"
RECORDING = "pu*oderecho*"        # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "puno"                    # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "der"
FLIGHT = "GIRAR_DERECHA"          # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.2                # pausa mínima entre dos detecciones de este gesto
