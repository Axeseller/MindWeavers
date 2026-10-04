import time
import cv2
from djitellopy import Tello


def print_instructions():
    """Imprime el manual de controles directo en la terminal."""
    print("\n" + "=" * 45)
    print("      CONTROL MANUAL TELLO (CONSOLA)")
    print("=" * 45)
    print(" [Q] = Despegar (Takeoff)")
    print(" [E] = Aterrizar (Land)")
    print(" [W] = Adelante")
    print(" [S] = Atras")
    print(" [A] = Izquierda")
    print(" [D] = Derecha")
    print(" [Y / U]   = Subir / Bajar")
    print(" [R / T]   = Girar Izquierda / Derecha")
    print(" [ESC] = Salir")
    print("=" * 45 + "\n")


def get_keyboard_input(key):
    # (Comando, (roll (izquierda/derecha), pitch(adelante/atras), throttle(arriba/abajo), yaw(Rotacion)))

    lr, fb, ud, yv = 0, 0, 0, 0
    speed = 50  

    # Teclas de Despegue y Aterrizaje
    if key == ord("q") or key == ord("Q"):
        return "TAKEOFF", (0, 0, 0, 0)
    if key == ord("e") or key == ord("E"):
        return "LAND", (0, 0, 0, 0)

    # 1. Movimiento Horizontal (A / D)
    if key == ord("a") or key == ord("A"):  # Flecha Izquierda
        lr = -speed
    elif key == ord("d") or key == ord("D"):  # Flecha Derecha
        lr = speed

    # 2. Movimiento Frontal (W / S)
    elif key == ord("w") or key == ord("W"):  # Flecha Arriba
        fb = speed
    elif key == ord("s") or key == ord("S"):  # Flecha Abajo
        fb = -speed

    # 3. Elevación (Y / U)
    elif key == ord("y") or key == ord("Y"):
        ud = speed
    elif key == ord("u") or key == ord("U"):
        ud = -speed

    # 4. Rotación (R / T)
    elif key == ord("r") or key == ord("R"):
        yv = -speed
    elif key == ord("t") or key == ord("T"):
        yv = speed

    return "FLIGHT", (lr, fb, ud, yv)


def main():
    tello = Tello()

    try:
        tello.connect()
        tello.streamon()
        frame_read = tello.get_frame_read()

        print_instructions()
        is_flying = False
        running = True

        while running:
            # Obtener el fotograma actual de la camara
            img = frame_read.frame
            if img is not None:
                # Mostrar el video en una ventana pequeña para enfocar el teclado
                img_resized = cv2.resize(img, (640, 480))
                img_normal = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
                cv2.imshow("Camara Tello - Presiona teclas aqui", img_normal)

            # Esperar captura de tecla (espera 1 ms)
            key = cv2.waitKey(1) & 0xFF

            # Detectar tecla ESC
            if key == 27:
                print("\n[!] Salida de emergencia activada.")
                running = False
                break

            # Si se presiono alguna tecla
            if key != 255:
                command, (lr, fb, ud, yv) = get_keyboard_input(key)

                if command == "TAKEOFF" and not is_flying:
                    print("--> Despegando...")
                    tello.takeoff()
                    is_flying = True

                elif command == "LAND" and is_flying:
                    print("--> Aterrizando...")
                    tello.land()
                    is_flying = False

                elif command == "FLIGHT" and is_flying:
                    tello.send_rc_control(lr, fb, ud, yv)
            else:
                # Si no presiona ninguna tecla y está volando, frenar a (0,0,0,0)
                if is_flying:
                    tello.send_rc_control(0, 0, 0, 0)

            time.sleep(0.01)

    except Exception as e:
        print(f"\nError durante la ejecución: {e}")

    finally:
        print("\nCerrando programa y asegurando el dron...")
        try:
            tello.send_rc_control(0, 0, 0, 0)
            tello.land()
        except:
            pass
        try:
            tello.streamoff()
        except:
            pass
        cv2.destroyAllWindows()
        print("Programa finalizado de forma segura.")


if __name__ == "__main__":
    main()
