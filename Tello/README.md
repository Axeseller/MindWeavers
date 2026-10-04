# Fundamentos y Control del Dron Tello

En este módulo aprenderás a comunicarte directamente con el dron DJI Tello a través de código en Python. Pasarás de recibir la transmisión de video en tiempo real a ejecutar secuencias de vuelo autónomas y tomar el control manual desde tu teclado.

Para poder volar el dron y usar su cámara vas a requerir python 3.13.7 y las siguientes instalaciones:
  
```bash
pip install -r Tello/requirements.txt
```

---

## Reglas de Seguridad Antes de Volar

Verifica el espacio: Vuela en un área abierta, sin obstáculos ni personas cerca para cuidar los más posible el dron.

Nivel de batería: El tello no va a volar con 20% de bateria.

Red Wi-Fi: Conéctate a la red Wi-Fi que emite el Tello (ej. TELLO-XXXXXX) desde tu computadora antes de ejecutar cualquier programa.

---

# Guía de ejecución de scripts

Para aprender de forma segura y ordenada, ejecuta los archivos en el siguiente orden:

```text
[ 1. Inicio.py ] ──> [ 2. Camara.py ] ──> [ 3. Mover.py ]
  (Conexión/Batería)   (Transmisión Video)   (Control Manual)
