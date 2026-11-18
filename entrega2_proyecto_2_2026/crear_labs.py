# Este programa dibuja la imagen de cada circuito y arma el .zip del laboratorio.
# Cada .zip queda con dos archivos: el circuito (.cir) y su dibujo (.png).
# Se corre una sola vez, antes de que el profesor suba los laboratorios.

import zipfile  # Librería para crear archivos .zip
import schemdraw  # Librería para dibujar circuitos eléctricos
import schemdraw.elements as elm  # Elementos del dibujo (resistencias, fuentes, tierra...)


# Función que dibuja el divisor de voltaje y lo guarda como imagen PNG
def dibujarDivisor(ruta_png):
    # Se abre un dibujo nuevo que se guarda en ruta_png sin mostrarse en pantalla (dpi=150: buena resolución)
    with schemdraw.Drawing(file=ruta_png, show=False, dpi=150) as d:
        d.config(fontsize=14)  # Tamaño de la letra del dibujo
        fuente = elm.SourceV().up().label("V1\n9 V")  # Fuente de 9 V dibujada hacia arriba
        elm.Resistor().right().label("R1\n1 kΩ")  # Resistencia R1 hacia la derecha
        elm.Dot().label("Vout", loc="right")  # Punto que marca el nodo de salida Vout
        elm.Resistor().down().label("R2\n2 kΩ")  # Resistencia R2 hacia abajo
        elm.Line().left().tox(fuente.start)  # Línea que regresa hasta la base de la fuente
        elm.Ground()  # Símbolo de tierra (nodo 0)


# Función que dibuja el circuito RC y lo guarda como imagen PNG
def dibujarRC(ruta_png):
    # Se abre un dibujo nuevo que se guarda en ruta_png sin mostrarse en pantalla (dpi=150: buena resolución)
    with schemdraw.Drawing(file=ruta_png, show=False, dpi=150) as d:
        d.config(fontsize=14)  # Tamaño de la letra del dibujo
        fuente = elm.SourceSquare().up().label("V1\npulso 0-5 V")  # Fuente de pulsos hacia arriba
        elm.Resistor().right().label("R1\n1 kΩ")  # Resistencia R1 hacia la derecha
        elm.Dot().label("output", loc="right")  # Punto que marca el nodo de salida
        elm.Capacitor().down().label("C1\n1 µF")  # Condensador C1 hacia abajo
        elm.Line().left().tox(fuente.start)  # Línea que regresa hasta la base de la fuente
        elm.Ground()  # Símbolo de tierra (nodo 0)


# Función que mete el .cir y el .png dentro de un mismo .zip
def crearZip(nombre_lab):
    ruta_zip = "client/" + nombre_lab + ".zip"  # El zip queda en la carpeta client/
    with zipfile.ZipFile(ruta_zip, "w") as z:  # Se crea el zip en modo escritura
        # Se agrega el circuito; arcname es el nombre que tendrá dentro del zip
        z.write("circuitos/" + nombre_lab + ".cir", arcname=nombre_lab + ".cir")
        # Se agrega el dibujo del circuito con su nombre dentro del zip
        z.write("circuitos/" + nombre_lab + ".png", arcname=nombre_lab + ".png")
    print("Creado", ruta_zip)  # Mensaje en consola para saber que funcionó


dibujarDivisor("circuitos/voltage_divider.png")  # Dibuja el divisor de voltaje
dibujarRC("circuitos/rc.png")  # Dibuja el circuito RC
crearZip("voltage_divider")  # Arma el zip del divisor de voltaje
crearZip("rc")  # Arma el zip del circuito RC
