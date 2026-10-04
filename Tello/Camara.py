#Importamos las librerias para el tello, tiempo y camara
import cv2
import time
from djitellopy import Tello

#Iniciamos nuestra funcion principal
def principal():
    # 1. Instanciar la herramienta del dron
    tello = Tello()

    print("Conectando con el dron Tello...")
    tello.connect()

    # 2. Encender el módulo de transmisión de video del Tello
    print("Encendiendo transmisión de video (Stream On)...")
    tello.streamon()

    # 3. Obtener el lector de frames (cuadros de video) del dron
    # Esta función nos da acceso al stream en tiempo real
    frame_read = tello.get_frame_read()

    # Pequeña pausa de 2 segundos para dar tiempo a que el sensor de video inicie
    time.sleep(2)

    print("\n--- CÁMARA ACTIVADA ---")
    print("Presiona la tecla 'q' en la ventana del video para salir.\n")

    # 4. Bucle principal para mostrar el video cuadro por cuadro
    while True:
        # Capturar el cuadro (imagen) actual de la cámara
        imagen = frame_read.frame

        # Si por alguna razón la imagen no carga, continuar al siguiente intento
        if imagen is None:
            continue

        # Redimensionar la imagen (opcional, para verla en un tamaño cómodo)
        # Tello transmite nativamente a 960x720
        imagen_redim = cv2.resize(imagen, (640, 480))

        # Mostrar la imagen en una ventana llamada "Camara Tello"
        cv2.imshow("Camara Tello - DroneOps", imagen_redim)

        # 5. Condición de salida:
        # Esperar 1 milisegundo entre cuadros y detectar si el usuario presiona la tecla 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Cerrando la transmisión de video...")
            break

    # 6. Limpieza al finalizar
    # Apagamos el stream de video del dron para liberar recursos y batería
    tello.streamoff()
    
    # Cerramos todas las ventanas creadas por OpenCV en la pantalla
    cv2.destroyAllWindows()
    
    print("Programa finalizado correctamente.")

# Punto de entrada
if __name__ == "__main__":
    principal()
