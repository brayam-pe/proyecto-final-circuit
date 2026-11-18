# Ventana principal del laboratorio virtual: registro e inicio de sesión.


from PyQt5.QtCore import *  # Clases base de Qt 
from PyQt5.QtGui import *  # Clases gráficas de Qt 
from PyQt5.QtWidgets import *  # Widgets de Qt (ventanas, botones, campos de texto)
import requests  # Se usa solo para detectar si el servidor está apagado
import virtuallab_client  
from ventana_profesor import VentanaProfesor  # Ventana que se abre si entra un profesor
from ventana_estudiante import VentanaEstudiante  # Ventana que se abre si entra un estudiante


URL = "http://127.0.0.1:80"


ROLES = {"Profesor": "professor", "Estudiante": "student"}


# Clase de la ventana de login hereda de QMainWindow 
class VentanaLogin(QMainWindow):

    # Constructor: aquí se crean y se acomodan todos los widgets de la ventana
    def __init__(self):
        super().__init__()  # Llama al constructor de QMainWindow
        self.setWindowTitle("Virtual Lab - Login")  # Título de la ventana

        # --- Etiquetas (textos fijos a la izquierda de cada campo) ---
        etiqueta_nombre = QLabel("Nombre:")  
        etiqueta_id = QLabel("ID:") 
        etiqueta_rol = QLabel("Rol:")  
        etiqueta_clave = QLabel("Contraseña:")  

        # --- Campos donde el usuario escribe ---
        self.campo_nombre = QLineEdit()  
        self.campo_id = QLineEdit()  
        self.campo_clave = QLineEdit()  
        self.campo_clave.setEchoMode(QLineEdit.Password)  

        # --- Lista desplegable (combo) para escoger el rol ---
        self.combo_rol = QComboBox()  # Crea la lista desplegable
        self.combo_rol.addItems(["Profesor", "Estudiante"])  # Opciones que puede escoger

        # --- Botones ---
        boton_registrar = QPushButton("Registrarse")  # Botón para crear un usuario nuevo
        boton_registrar.clicked.connect(self.registrar)  # Al hacer clic se llama a self.registrar
        boton_entrar = QPushButton("Iniciar sesión")  # Botón para entrar
        boton_entrar.clicked.connect(self.iniciarSesion)  # Al hacer clic se llama a self.iniciarSesion

        # --- Layout de cuadrícula: addWidget(widget, fila, columna) ---
        layout = QGridLayout()  # Crea la cuadrícula
        layout.addWidget(etiqueta_nombre, 0, 0)  # Fila 0, columna 0
        layout.addWidget(self.campo_nombre, 0, 1)  # Fila 0, columna 1
        layout.addWidget(etiqueta_id, 1, 0)  # Fila 1, columna 0
        layout.addWidget(self.campo_id, 1, 1)  # Fila 1, columna 1
        layout.addWidget(etiqueta_rol, 2, 0)  # Fila 2, columna 0
        layout.addWidget(self.combo_rol, 2, 1)  # Fila 2, columna 1
        layout.addWidget(etiqueta_clave, 3, 0)  # Fila 3, columna 0
        layout.addWidget(self.campo_clave, 3, 1)  # Fila 3, columna 1
        layout.addWidget(boton_registrar, 4, 0)  # Fila 4, columna 0
        layout.addWidget(boton_entrar, 4, 1)  # Fila 4, columna 1

        widget_central = QWidget()  # QMainWindow necesita un widget central
        widget_central.setLayout(layout)  # Se le pone la cuadrícula al widget central
        self.setCentralWidget(widget_central)  # Se coloca el widget central en la ventana

        self.setWindowFlags(Qt.MSWindowsFixedSizeDialogHint)  # Deshabilita el botón de maximizar

    # Función (slot) que se ejecuta al presionar "Registrarse"
    def registrar(self):
        nombre = self.campo_nombre.text().strip()  # Lee el nombre y le quita espacios de los lados
        id_usuario = self.campo_id.text().strip()  # Lee el ID
        clave = self.campo_clave.text().strip()  # Lee la contraseña
        rol = ROLES[self.combo_rol.currentText()]  # Traduce el rol escogido ("Profesor" -> "professor")

        # Si falta algún dato se avisa y no se sigue
        if nombre == "" or id_usuario == "" or clave == "":
            QMessageBox.warning(self, "Alerta", "Por favor ingrese nombre, ID y contraseña")  # Ventana de aviso
            return  # Sale de la función sin registrar

        try:  # Se intenta hablar con el servidor
            respuesta = virtuallab_client.registerUser(URL, nombre, id_usuario, rol, clave)  # Pide el registro
        except requests.exceptions.ConnectionError:  # Si el servidor está apagado cae aquí
            QMessageBox.critical(self, "Error", "No se pudo conectar con el servidor")  # Avisa el problema
            return  # Sale de la función

        QMessageBox.information(self, "Registro", respuesta)  # Muestra lo que respondió el servidor

    # Función (slot) que se ejecuta al presionar "Iniciar sesión"
    def iniciarSesion(self):
        id_usuario = self.campo_id.text().strip()  # Lee el ID
        clave = self.campo_clave.text().strip()  # Lee la contraseña
        rol_escogido = self.combo_rol.currentText()  # Lee el rol escogido ("Profesor" o "Estudiante")

        # Para entrar solo se necesitan el ID y la contraseña
        if id_usuario == "" or clave == "":
            QMessageBox.warning(self, "Alerta", "Por favor ingrese ID y contraseña")  # Ventana de aviso
            return  # Sale de la función

        try:  # Se intenta hablar con el servidor
            respuesta = virtuallab_client.openSession(URL, id_usuario, clave)  # Pide abrir la sesión
        except requests.exceptions.ConnectionError:  # Si el servidor está apagado cae aquí
            QMessageBox.critical(self, "Error", "No se pudo conectar con el servidor")  # Avisa el problema
            return  # Sale de la función

        # El servidor responde "error" si el ID no existe o la contraseña está mal
        if respuesta == "error":
            QMessageBox.warning(self, "Alerta", "ID o contraseña incorrectos")  # Avisa al usuario
            return  # Sale de la función

        # Se comprueba que el usuario sí tenga el rol que escogió.
        # Las funciones de listar devuelven "error" si el rol no coincide.
        if rol_escogido == "Profesor":  # Si escogió entrar como profesor
            prueba = virtuallab_client.listProfessorsLabs(URL, id_usuario)  # Solo funciona para profesores
        else:  # Si escogió entrar como estudiante
            prueba = virtuallab_client.listStudentLabs(URL, id_usuario)  # Solo funciona para estudiantes

        if prueba == "error":  # El usuario no tiene ese rol
            virtuallab_client.closeSession(URL, id_usuario)  # Se cierra la sesión que se acababa de abrir
            QMessageBox.warning(self, "Alerta", "Este usuario no es " + rol_escogido)  # Avisa al usuario
            return  # Sale de la función

        # Todo bien: se abre la ventana que le corresponde al rol
        if rol_escogido == "Profesor":  # Si es profesor
            self.ventana_nueva = VentanaProfesor(URL, id_usuario)  # Crea la ventana del profesor
        else:  # Si es estudiante
            self.ventana_nueva = VentanaEstudiante(URL, id_usuario)  # Crea la ventana del estudiante
        self.ventana_nueva.show()  # Muestra la ventana nueva
        self.campo_clave.clear()  # Borra la contraseña escrita, por seguridad


app = QApplication([])  # Crea la aplicación de Qt 
app.setFont(QFont("Arial", 11))  
ventana = VentanaLogin()  
ventana.show()  
app.exec()  # Arranca el ciclo de eventos 
