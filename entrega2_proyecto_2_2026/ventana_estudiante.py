# Ventana del estudiante: ver sus laboratorios, descargarlos y simularlos.
# Esta ventana la abre ventana_login.py cuando entra un estudiante.

from PyQt5.QtCore import *  # Clases base de Qt
from PyQt5.QtGui import *  # Clases gráficas de Qt (QPixmap para la imagen)
from PyQt5.QtWidgets import *  # Widgets de Qt (botones, listas, etc.)
import zipfile  # Para abrir el .zip del laboratorio
from PySpice.Spice.Parser import SpiceParser  # Para leer el circuito (.cir) y simularlo
import virtuallab_client  # Funciones que hablan con el servidor


# Clase de la ventana del estudiante; hereda de QMainWindow
class VentanaEstudiante(QMainWindow):

    # Constructor: recibe la dirección del servidor y el ID del estudiante
    def __init__(self, url, id_estudiante):
        super().__init__()  # Llama al constructor de QMainWindow
        self.url = url  # Guarda la dirección del servidor
        self.id_estudiante = id_estudiante  # Guarda el ID del estudiante que inició sesión
        self.netlist = ""  # Aquí se guardará el texto del circuito cuando se descargue
        self.setWindowTitle("Virtual Lab - Estudiante ID: " + id_estudiante)  # Título de la ventana

        # --- Encabezado de la ventana ---
        titulo = QLabel("Panel del estudiante")  # Texto grande de arriba
        titulo.setObjectName("titulo")  # Nombre que usa estilo.py para darle letra grande y turquesa
        subtitulo = QLabel("ID " + id_estudiante)  # Texto pequeño con el ID del estudiante
        subtitulo.setObjectName("subtitulo")  # Nombre que usa estilo.py para darle letra pequeña y gris

        # --- Etiquetas de título ---
        etiqueta_labs = QLabel("Mis laboratorios")  # Título de la lista
        etiqueta_circuito = QLabel("Circuito")  # Título de la imagen

        # --- Lista con los laboratorios asignados ---
        self.lista_labs = QListWidget()  # Lista donde el estudiante escoge un laboratorio
        # Cada vez que el estudiante escoge otro laboratorio se llama a self.labCambiado
        self.lista_labs.currentItemChanged.connect(self.labCambiado)

        # --- Etiqueta donde se mostrará la imagen del circuito ---
        self.imagen = QLabel("Descargue un laboratorio para ver el circuito")  # Texto mientras no hay imagen
        self.imagen.setAlignment(Qt.AlignCenter)  # Centra la imagen dentro de la etiqueta
        self.imagen.setMinimumSize(350, 220)  # Tamaño mínimo para que la ventana no cambie de tamaño
        self.imagen.setObjectName("imagen")  # estilo.py le pone fondo blanco para que el circuito se vea bien

        # --- Cuadro de texto para mostrar resultados ---
        self.resultados = QTextEdit()  # Caja de texto de varias líneas
        self.resultados.setReadOnly(True)  # El estudiante solo puede leer, no escribir
        self.resultados.setMinimumHeight(110)  # Alto mínimo para que quepan los voltajes sin barra de scroll

        # --- Botones ---
        boton_actualizar = QPushButton("Actualizar lista")  # Botón para volver a pedir los laboratorios
        boton_actualizar.clicked.connect(self.cargarLabs)  # Al hacer clic se llama a self.cargarLabs
        self.boton_descargar = QPushButton("Descargar laboratorio")  # Botón para descargar
        self.boton_descargar.clicked.connect(self.descargarLab)  # Al hacer clic se llama a self.descargarLab
        self.boton_descargar.setObjectName("primario")  # estilo.py lo pinta turquesa (acción principal)
        self.boton_simular = QPushButton("Simular")  # Botón para simular
        self.boton_simular.clicked.connect(self.simularLab)  # Al hacer clic se llama a self.simularLab
        self.boton_simular.setEnabled(False)  # Queda apagado hasta que se descargue un laboratorio
        self.boton_simular.setObjectName("primario")  # estilo.py lo pinta turquesa (acción principal)
        boton_salir = QPushButton("Cerrar sesión")  # Botón para salir
        boton_salir.clicked.connect(self.cerrarSesion)  # Al hacer clic se llama a self.cerrarSesion
        boton_salir.setObjectName("salir")  # estilo.py lo pinta rojizo para que no se confunda

        # --- Layout de cuadrícula: addWidget(widget, fila, columna, filas que ocupa, columnas que ocupa) ---
        layout = QGridLayout()  # Crea la cuadrícula
        layout.setContentsMargins(22, 18, 22, 18)  # Margen interno: izquierda, arriba, derecha, abajo (píxeles)
        layout.setSpacing(10)  # Espacio entre un widget y otro
        layout.addWidget(titulo, 0, 0, 1, 2)  # Fila 0, ocupa 2 columnas
        layout.addWidget(subtitulo, 1, 0, 1, 2)  # Fila 1, ocupa 2 columnas
        layout.addWidget(etiqueta_labs, 2, 0)  # Fila 2, columna 0
        layout.addWidget(etiqueta_circuito, 2, 1)  # Fila 2, columna 1
        layout.addWidget(self.lista_labs, 3, 0)  # Fila 3, columna 0
        layout.addWidget(self.imagen, 3, 1)  # Fila 3, columna 1
        layout.addWidget(boton_actualizar, 4, 0)  # Fila 4, columna 0
        layout.addWidget(self.boton_descargar, 5, 0)  # Fila 5, columna 0
        layout.addWidget(self.boton_simular, 5, 1)  # Fila 5, columna 1
        layout.addWidget(self.resultados, 6, 0, 1, 2)  # Fila 6, ocupa 2 columnas
        layout.addWidget(boton_salir, 7, 0, 1, 2)  # Fila 7, ocupa 2 columnas

        widget_central = QWidget()  # QMainWindow necesita un widget central
        widget_central.setLayout(layout)  # Se le pone la cuadrícula al widget central
        self.setCentralWidget(widget_central)  # Se coloca el widget central en la ventana

        self.cargarLabs()  # Llena la lista apenas se abre la ventana

    # Función que pide al servidor los laboratorios asignados y llena la lista
    def cargarLabs(self):
        self.lista_labs.clear()  # Borra lo que tenía la lista
        labs = virtuallab_client.listStudentLabs(self.url, self.id_estudiante)  # Pide los laboratorios

        if labs == "No labs assigned" or labs == "error":  # Si no tiene laboratorios (o hubo un error)
            # Se explica en la caja de texto por qué no se puede descargar nada
            self.resultados.setText("No tiene laboratorios asignados.\n"
                                    "Pídale a su profesor que le asigne uno y luego presione 'Actualizar lista'.")
            self.boton_descargar.setEnabled(False)  # Se apaga Descargar porque no hay nada que descargar
            return  # Sale de la función

        sin_repetidos = sorted(set(labs.splitlines()))  # set() quita los repetidos y sorted() los ordena
        self.lista_labs.addItems(sin_repetidos)  # Agrega los laboratorios a la lista
        self.lista_labs.setCurrentRow(0)  # Deja escogido el primero para no tener que hacer clic
        self.boton_descargar.setEnabled(True)  # Se enciende Descargar porque sí hay laboratorios
        self.resultados.setText("Escoja un laboratorio y presione 'Descargar laboratorio'.")  # Instrucción

    # Función que se llama cuando el estudiante escoge otro laboratorio de la lista
    def labCambiado(self):
        self.boton_simular.setEnabled(False)  # Se apaga Simular: primero hay que descargar el nuevo
        self.imagen.setText("Descargue un laboratorio para ver el circuito")  # Se quita la imagen anterior

    # Función (slot) del botón "Descargar laboratorio"
    def descargarLab(self):
        lab_escogido = self.lista_labs.currentItem()  # Laboratorio seleccionado (None si no hay)
        if lab_escogido is None:  # Si no escogió ninguno
            QMessageBox.warning(self, "Alerta", "Escoja un laboratorio de la lista")  # Avisa al estudiante
            return  # Sale de la función

        self.nombre_lab = lab_escogido.text()  # Nombre del laboratorio, por ejemplo "rc"
        nombre_zip = self.nombre_lab + ".zip"  # Nombre del archivo, por ejemplo "rc.zip"
        virtuallab_client.downloadLab(self.url, self.id_estudiante, nombre_zip)  # Lo descarga en client/labs
        ruta_zip = "client/labs/" + nombre_zip  # Ruta donde quedó el archivo descargado

        if not zipfile.is_zipfile(ruta_zip):  # Si lo que llegó no es un zip (el servidor respondió "error")
            # Avisa al estudiante; casi siempre es porque el profesor no ha subido ese laboratorio
            QMessageBox.warning(self, "Alerta", "No se pudo descargar el laboratorio " + self.nombre_lab)
            return  # Sale de la función

        with zipfile.ZipFile(ruta_zip, "r") as z:  # Abre el zip para leerlo
            self.netlist = z.read(self.nombre_lab + ".cir").decode("utf-8")  # Lee el circuito como texto
            nombre_png = self.nombre_lab + ".png"  # Nombre de la imagen dentro del zip
            if nombre_png in z.namelist():  # Si el zip trae la imagen del circuito
                pixmap = QPixmap()  # Crea una imagen vacía de Qt
                pixmap.loadFromData(z.read(nombre_png))  # La llena con los bytes de la imagen
                # La achica para que quepa en 350x220 sin deformarla (KeepAspectRatio) y la muestra
                self.imagen.setPixmap(pixmap.scaled(350, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:  # Si el zip no trae imagen
                self.imagen.setText("Este laboratorio no trae imagen")  # Muestra un texto en su lugar

        self.boton_simular.setEnabled(True)  # Ya se puede simular, se enciende el botón
        self.resultados.setText("Laboratorio " + self.nombre_lab + " descargado. Ya puede simular.")  # Avisa

    # Función (slot) del botón "Simular": calcula el punto de operación, igual que en la entrega 1
    def simularLab(self):
        parser = SpiceParser(source=self.netlist)  # Lee el texto del circuito
        circuito = parser.build_circuit()  # Construye el circuito a partir del texto
        simulador = circuito.simulator(temperature=25, nominal_temperature=25)  # Crea el simulador a 25 °C
        analisis = simulador.operating_point()  # Calcula el punto de operación (voltajes en DC)

        texto = "Resultados de " + self.nombre_lab + ":\n"  # Primera línea del resultado
        for nombre, nodo in analisis.nodes.items():  # Recorre cada nodo del circuito
            texto = texto + "Nodo " + nombre + ": " + f"{float(nodo[0]):.4f}" + " V\n"  # Agrega su voltaje
        self.resultados.setText(texto)  # Muestra los voltajes en la caja de texto

    # Función (slot) del botón "Cerrar sesión"
    def cerrarSesion(self):
        virtuallab_client.closeSession(self.url, self.id_estudiante)  # Cierra la sesión en el servidor
        self.close()  # Cierra esta ventana
