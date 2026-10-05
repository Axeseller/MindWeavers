"""Giro imaginario derecha.

Cómo se hace: Imaginar girar la cabeza a la derecha.
Grabación de entrenamiento: girarcabezaimaginariader*.csv
Notas: Igual que el izquierdo. Choca con cuello_der.
"""

NAME = "giro_imag_der"
RECORDING = "girarcabezaimaginariader*"# glob, sin .csv, dentro de la carpeta de grabaciones
GROUP = "giro_imag"               # inputs del mismo grupo se separan en una segunda etapa (izq/der)
SIDE = "der"
FLIGHT = "GIRAR_DERECHA"          # función de vuelo que dispara
USES_EYES = False                 # True: el detector de inicio también escucha la señal de los ojos (EOG)
REFRACTORY_S = 2.5                # pausa mínima entre dos detecciones de este gesto
