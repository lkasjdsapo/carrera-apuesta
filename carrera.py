import tkinter as tk
from tkinter import ttk
import threading
import random
import time

# Configuración general
NUM_VEHICULOS = 10
CANVAS_WIDTH = 500
LEFT_BOUND = 70          # extremo izquierdo de la pista
RIGHT_BOUND = 420        # extremo derecho de la pista
LANE_HEIGHT = 42         # separación vertical entre carriles
TOP_MARGIN = 30
CANVAS_HEIGHT = TOP_MARGIN + NUM_VEHICULOS * LANE_HEIGHT + 20

ANCHO_CARRO = 34
RECORRIDO = RIGHT_BOUND - LEFT_BOUND - ANCHO_CARRO   # píxeles de ida (o de vuelta)

COLORES = [
    'red', 'blue', 'green', 'yellow', 'purple',
    'aquamarine', 'orange', 'dark blue', 'pink', 'gray',
]


def dibujar_carro(canvas, x, y, color, numero):
    tag = f"carro{numero}"   # todas las piezas del carro comparten el mismo tag
    canvas.create_rectangle(x, y - 8, x + 34, y + 8, fill=color, outline="black", tags=tag)
    canvas.create_rectangle(x + 7, y - 15, x + 25, y - 8, fill=color, outline="black", tags=tag)
    canvas.create_oval(x + 2, y + 5, x + 12, y + 15, fill="black", tags=tag)
    canvas.create_oval(x + 22, y + 5, x + 32, y + 15, fill="black", tags=tag)
    canvas.create_text(x + 17, y, text=str(numero), fill="white", font=("Arial", 9, "bold"), tags=tag)
    canvas.create_text(25, y, text=f"#{numero}", font=("Arial", 9, "bold"))


class InterfazCarrera:

    def __init__(self, root):
        self.root = root
        self.root.title("Carrera de 10 vehículos")
        self.root.resizable(False, False)

        # Estado de la carrera
        self.velocidad = 1.0                       # la actualiza la interfaz, la leen los hilos
        self.posiciones = [0] * NUM_VEHICULOS      # píxeles recorridos por cada carro
        self.x_dibujado = [0] * NUM_VEHICULOS      # posición actual en el canvas (relativa a la salida)
        self.resultados = []                       # (vehiculo, tiempo) en orden de llegada
        self.intervalos = [0.0] * NUM_VEHICULOS    # intervalo actual de cada carro
        self.tramos = [0] * NUM_VEHICULOS          # tramo actual (ida/vuelta) de cada carro
        self.timers = [None] * NUM_VEHICULOS       # el Timer pendiente de cada carro
        self.candado = threading.Lock()
        self.parar = threading.Event()
        self.corriendo = False
        self.rondas = 1

        self._construir_interfaz()
        self._dibujar_vehiculos()

    def _construir_interfaz(self):
        panel_control = tk.Frame(self.root, padx=10, pady=10)
        panel_control.grid(row=0, column=0, sticky="n")

        # Rondas
        tk.Label(panel_control, text="Número de vueltas (ida y vuelta):",
                 font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.spin_rondas = tk.Spinbox(panel_control, from_=1, to=20, width=5)
        self.spin_rondas.grid(row=0, column=1, sticky="w", padx=5)

        # Apuesta
        tk.Label(panel_control, text="Apostar por vehículo:",
                 font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", pady=(8, 0))
        nombres = [f"Auto {i + 1}" for i in range(NUM_VEHICULOS)]
        self.combo_apuesta = ttk.Combobox(panel_control, values=nombres, state="readonly", width=10)
        self.combo_apuesta.current(0)
        self.combo_apuesta.grid(row=1, column=1, sticky="w", padx=5, pady=(8, 0))

        # Slider de velocidad global
        tk.Label(panel_control, text="Velocidad del juego:",
                 font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.slider_velocidad = tk.Scale(panel_control, from_=0.2, to=3.0, resolution=0.1,
                                         orient=tk.HORIZONTAL, length=180)
        self.slider_velocidad.set(1.0)
        self.slider_velocidad.grid(row=2, column=1, sticky="w", padx=5, pady=(8, 0))

        # Botones
        self.btn_iniciar = tk.Button(panel_control, text="Iniciar carrera", bg='green',
                                     font=("Arial", 10, "bold"), command=self.iniciar_carrera)
        self.btn_iniciar.grid(row=3, column=0, columnspan=2, sticky="we", pady=(12, 4))

        self.btn_reiniciar = tk.Button(panel_control, text="Reiniciar carrera", bg='red',
                                       fg="white", font=("Arial", 10, "bold"),
                                       command=self.reiniciar_carrera)
        self.btn_reiniciar.grid(row=4, column=0, columnspan=2, sticky="we", pady=4)

        # Mensaje de estado
        self.label_estado = tk.Label(panel_control, text="Configure la carrera y presione Iniciar.",
                                     wraplength=230, justify="left", font=("Arial", 9))
        self.label_estado.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Canvas de la pista
        self.canvas = tk.Canvas(self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
                                bg='gray', highlightthickness=1, highlightbackground="black")
        self.canvas.grid(row=0, column=1, padx=10, pady=10)

        self.canvas.create_line(LEFT_BOUND, 5, LEFT_BOUND, CANVAS_HEIGHT - 5,
                                fill="green", width=3, dash=(4, 2))
        self.canvas.create_line(RIGHT_BOUND, 5, RIGHT_BOUND, CANVAS_HEIGHT - 5,
                                fill="red", width=3, dash=(4, 2))
        self.canvas.create_text(LEFT_BOUND, 12, text="SALIDA", fill="green", font=("Arial", 8, "bold"))
        self.canvas.create_text(RIGHT_BOUND, 12, text="VUELTA", fill="red", font=("Arial", 8, "bold"))

        # Tabla de resultados
        panel_resultados = tk.Frame(self.root, padx=10, pady=10)
        panel_resultados.grid(row=0, column=2, sticky="n")

        tk.Label(panel_resultados, text="Resultados finales",
                 font=("Arial", 11, "bold")).pack(anchor="w")

        columnas = ("pos", "vehiculo", "tiempo")
        self.tabla = ttk.Treeview(panel_resultados, columns=columnas, show="headings", height=12)
        self.tabla.heading("pos", text="Pos.")
        self.tabla.heading("vehiculo", text="Vehículo")
        self.tabla.heading("tiempo", text="Tiempo (s)")
        self.tabla.column("pos", width=45, anchor="center")
        self.tabla.column("vehiculo", width=90, anchor="center")
        self.tabla.column("tiempo", width=90, anchor="center")
        self.tabla.pack()

    def _dibujar_vehiculos(self):
        for i in range(NUM_VEHICULOS):
            y = TOP_MARGIN + i * LANE_HEIGHT + LANE_HEIGHT // 2
            self.canvas.create_line(LEFT_BOUND, y + 18, RIGHT_BOUND, y + 18, fill='black')
            dibujar_carro(self.canvas, LEFT_BOUND, y, COLORES[i], i + 1)

    # ------------------------------------------------------------------
    # Lógica de la carrera
    # ------------------------------------------------------------------
    def iniciar_carrera(self):
        if self.corriendo:
            return

        self.rondas = int(self.spin_rondas.get())
        self.corriendo = True
        self.btn_iniciar.config(state="disabled")
        self.combo_apuesta.config(state="disabled")
        self.label_estado.config(text="¡Carrera en curso!")

        # Un Event nuevo para esta carrera (sirve para detener los hilos)
        self.parar = threading.Event()
        inicio = time.time()

        # Un temporizador por vehículo (arranca el primer disparo de cada uno)
        for i in range(NUM_VEHICULOS):
            self.intervalos[i] = random.uniform(0.01, 0.05)
            self.tramos[i] = 0
            self._programar(i, inicio, self.parar)

        self._actualizar()

    def _programar(self, i, inicio, parar):
        """Crea y lanza el siguiente Timer del carro i."""
        timer = threading.Timer(self.intervalos[i] / self.velocidad,
                                self._avanzar, args=(i, inicio, parar))
        timer.daemon = True
        self.timers[i] = timer
        timer.start()

    def _avanzar(self, i, inicio, parar):
        """Se ejecuta cada vez que dispara el Timer del carro i."""
        if parar.is_set():
            return

        self.posiciones[i] += 2                                 # avanza 2 píxeles
        distancia_total = self.rondas * 2 * RECORRIDO

        if self.posiciones[i] >= distancia_total:               # llegó a la meta
            self.posiciones[i] = distancia_total
            tiempo = time.time() - inicio
            with self.candado:
                self.resultados.append((i + 1, tiempo))
            return

        # Si llegó a un extremo, cambia el intervalo
        nuevo_tramo = self.posiciones[i] // RECORRIDO
        if nuevo_tramo != self.tramos[i]:
            self.tramos[i] = nuevo_tramo
            self.intervalos[i] = random.uniform(0.01, 0.05)

        self._programar(i, inicio, parar)                       # re-arma el temporizador

    def _actualizar(self):
        """Corre en el hilo principal: lee las posiciones y mueve los carros."""
        if not self.corriendo:
            return

        self.velocidad = self.slider_velocidad.get()

        for i in range(NUM_VEHICULOS):
            # Convertimos la distancia total en una posición de ida y vuelta
            resto = self.posiciones[i] % (2 * RECORRIDO)
            x = resto if resto <= RECORRIDO else 2 * RECORRIDO - resto
            if self.posiciones[i] >= self.rondas * 2 * RECORRIDO:
                x = 0   # terminó: vuelve a la salida
            self.canvas.move(f"carro{i + 1}", x - self.x_dibujado[i], 0)
            self.x_dibujado[i] = x

        if len(self.resultados) == NUM_VEHICULOS:
            self._terminar_carrera()
        else:
            self.root.after(30, self._actualizar)   # se vuelve a llamar en 30 ms

    def _terminar_carrera(self):
        self.corriendo = False

        for pos, (vehiculo, tiempo) in enumerate(self.resultados, start=1):
            self.tabla.insert("", "end", values=(pos, f"Auto {vehiculo}", f"{tiempo:.2f}"))

        ganador = self.resultados[0][0]
        apuesta = self.combo_apuesta.current() + 1

        if apuesta == ganador:
            mensaje = f"¡Ganó el Auto {ganador}! Ganaste la apuesta."
        else:
            mensaje = f"Ganó el Auto {ganador}. Apostaste por el Auto {apuesta}, perdiste."

        self.label_estado.config(text=mensaje)

    def reiniciar_carrera(self):
        self.parar.set()          # avisa a los temporizadores que se detengan
        for t in self.timers:
            if t:
                t.cancel()
        self.corriendo = False

        for i in range(NUM_VEHICULOS):
            self.canvas.move(f"carro{i + 1}", -self.x_dibujado[i], 0)

        self.posiciones = [0] * NUM_VEHICULOS
        self.x_dibujado = [0] * NUM_VEHICULOS
        self.resultados = []
        self.tabla.delete(*self.tabla.get_children())
        self.btn_iniciar.config(state="normal")
        self.combo_apuesta.config(state="readonly")
        self.label_estado.config(text="Configure la carrera y presione Iniciar.")


def main():
    root = tk.Tk()
    InterfazCarrera(root)
    root.mainloop()


if __name__ == "__main__":
    main()