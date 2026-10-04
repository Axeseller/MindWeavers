# En esta seccion importamos la libreria tiempo y la libreria tello que nos permitira comunicarnos con el dron
import time
from djitellopy import Tello

# Definimos la funcion principal
def principal():
    # 1. Creamos la instancia de la herramienta que se conecta con el dron
    tello = Tello()

    print("Conectando con el dron Tello...")
    
    # 2. Establecer la conexión vía Wi-Fi
    tello.connect()

    # 3. Consultar y mostrar el nivel de batería actual
    # importante comprobar la batería antes de volar!!!!!1
    bateria = tello.get_battery()
    print(f"Nivel de batería: {bateria}%")

    # Regla de seguridad simple: no despegar si la batería es baja
    if bateria < 20:
        print("Batería demasiado baja para un vuelo seguro. Carga el dron e intenta de nuevo.")
        return

    print("\n--- INICIANDO SECUENCIA DE VUELO ---")
    
    # 4. Despegue automático
    # El dron subirá automáticamente y se mantiene suspendido
    print("Despegando...")
    tello.takeoff()

    # 5. Pausa de espera
    # Dejamos que el dron se quede flotando (hovering) en el aire durante 5 segundos
    print("Manteniéndose en el aire por 5 segundos...")
    time.sleep(5)

    # 6. Aterrizaje automático
    # El dron bajara suavemente hasta el suelo y apagara los motores
    print("Aterrizando...")
    tello.land()

    print("Mision accomplished baby!")

# Punto de entrada del programa
if __name__ == "__main__":
    principal()
