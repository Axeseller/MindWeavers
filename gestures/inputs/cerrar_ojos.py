"""Cerrar los ojos 3 s.

Cómo se hace: Cerrar los ojos y mantenerlos cerrados ~3 s.
Grabación de entrenamiento: cerrarojos*.csv
Notas: Gesto tranquilo y deliberado: se le asigna la acción más segura. Abrir los ojos se descarta como 'otro movimiento'.
"""

NAME = "cerrar_ojos"
RECORDING = "cerrarojos*"         # glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "cerrar_ojos"             # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = ""
FLIGHT = "ATERRIZAR"              # función de vuelo que dispara
USES_EYES = True                  # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.5                # pausa mínima entre dos detecciones de este gesto
